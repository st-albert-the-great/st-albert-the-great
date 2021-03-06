#!/usr/bin/env python

"""Script to scan a source google folder and:

- look for files with multiple parents (that can't be migrated to a
  Team Drive)

- report all file owners (so that you can know who to give permissions
  in the target team drive, so that we can move files in there
  [vs. copying])

Pre-requisites:
- A client_id.json file downloaded from the Google Dashboard
  (presumably of the owning organization of the destination Team
  Drive: https://console.developers.google.com/apis/credentials)
- A Google Account who is both authorized to read everything in the
  source folder tree and authorized to write into the destination Team
  Drive folder.
- pip install --upgrade google-api-python-client
- pip install --upgrade recordclass

Input:
- Source folder ID

"""

import json
import sys
import os
import re
import time
import httplib2
import calendar
import uuid
import logging
import logging.handlers
import traceback
import csv

from pprint import pprint
from pprint import pformat

from recordclass import recordclass

from apiclient.discovery import build
from apiclient.http import MediaFileUpload
from apiclient.errors import HttpError
from oauth2client import tools
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow

# Globals
app_cred_file = 'client_id.json'
admin_cred_file = 'admin-credentials.json'
user_agent = 'gxcopy'
doc_mime_type = 'application/vnd.google-apps.document';
sheet_mime_type = 'application/vnd.google-apps.spreadsheet';
folder_mime_type = 'application/vnd.google-apps.folder'
args = None
log = None
# JMS this is probably a lie, but it's useful for comparisons
team_drive_mime_type = 'application/vnd.google-apps.team_drive'
# Scopes documented here:
# https://developers.google.com/drive/v3/web/about-auth
scope = 'https://www.googleapis.com/auth/drive'

#-------------------------------------------------------------------

# Recordclasses are effecitvely namedtuples that are mutable (i.e.,
# support assignment). These are the recordclasses that are used in
# the rest of the script.

GFile = recordclass('GFile',
                   ['id',           # string
                    'webViewLink',  # string (URL)
                    'mimeType',     # string
                    'name',         # string
                    'owners',       # array of hashes: 'displayName', 'emailAddress', 'kind', 'me', 'permissionId'
                    'parents',      # list of strings (each an ID)
                    'team_file',    # GFile or None
                    ])
Tree = recordclass('Tree',
                  ['root_folder',   # See comment in read_source_tree()
                   'contents'])
ContentEntry = recordclass('ContentEntry',
                          ['gfile',      # GFile
                           'is_folder',  # boolean
                           'traverse',   # boolean
                           'contents',   # list of ContentEntry's
                           'tree'        # Tree
                           ])
AllFiles = recordclass('AllFiles',
                      ['name',           # string
                       'webViewLink',    # string (URL)
                       'parents',        # array of Parent records
                       'is_folder',      # boolean
                       'owners',         # array of hashes: 'displayName', 'emailAddress', 'kind', 'me', 'permissionId'
                       ])
Parent = recordclass('Parent',
                     ['id',              # string
                      'name',            # string
                      'name_abs',        # string
                      'webViewLink'      # string (URL)
                      ])

#-------------------------------------------------------------------

def diediedie(msg):
    global log

    log.error(msg)
    log.error("Aborting")

    exit(1)

#-------------------------------------------------------------------

def setup_logging(args):
    level=logging.ERROR

    if args.debug:
        level="DEBUG"
    elif args.verbose:
        level="INFO"

    global log
    log = logging.getLogger('FToTD')
    log.setLevel(level)

    # Make sure to include the timestamp in each message
    f = logging.Formatter('%(asctime)s %(levelname)-8s: %(message)s')

    # Default log output to stdout
    s = logging.StreamHandler()
    s.setFormatter(f)
    log.addHandler(s)

    # Optionally save to a rotating logfile
    if args.logfile:
        s = logging.FileHandler(filename=args.logfile)
        s.setFormatter(f)
        log.addHandler(s)

    log.info('Starting')

#-------------------------------------------------------------------

def load_app_credentials(app_cred_file):
    # Read in the JSON file to get the client ID and client secret
    cwd  = os.getcwd()
    file = os.path.join(cwd, app_cred_file)
    if not os.path.isfile(file):
        diediedie("Error: JSON file {0} does not exist".format(file))
    if not os.access(file, os.R_OK):
        diediedie("Error: JSON file {0} is not readable".format(file))

    with open(file) as data_file:
        app_cred = json.load(data_file)

    log.debug('Loaded application credentials from {0}'
                  .format(file))
    return app_cred

def load_user_credentials(filename, scope, app_cred):
    # Get user consent
    client_id       = app_cred['installed']['client_id']
    client_secret   = app_cred['installed']['client_secret']
    flow            = OAuth2WebServerFlow(client_id, client_secret, scope)
    flow.user_agent = user_agent

    cwd       = os.getcwd()
    file      = os.path.join(cwd, filename)
    storage   = Storage(file)
    user_cred = storage.get()

    # If no credentials are able to be loaded, fire up a web
    # browser to get a user login, etc.  Then save those
    # credentials in the file listed above so that next time we
    # run, those credentials are available.
    if user_cred is None or user_cred.invalid:
        user_cred = tools.run_flow(flow, storage,
                                        tools.argparser.parse_args())

    log.debug('Loaded user credentials from {0}'
              .format(file))
    return user_cred

def authorize(user_cred):
    http    = httplib2.Http()
    http    = user_cred.authorize(http)
    service = build('drive', 'v3', http=http)

    log.debug('Authorized to Google')
    return service

####################################################################

# If the Google API call fails, try again...
def doit(httpref, can_fail=False):
    count = 0
    while count < 3:
        try:
            ret = httpref.execute()
            return ret

        except HttpError as err:
            log.debug("*** Got HttpError:")
            pprint(err)
            if err.resp.status in [500, 503]:
                log.debug("*** Seems recoverable; let's sleep and try again...")
                time.sleep(5)
                count = count + 1
                continue
            elif err.resp.status == 403 and can_fail:
                log.debug("*** Got a 403, but we're allowed to fail this call")
                # Need to return None to indicate failure
                return None
            else:
                log.debug("*** Doesn't seem recoverable (status {0}) -- aborting".format(err.resp.status))
                log.debug(err)
                raise

        except:
            log.error("*** Some unknown error occurred")
            log.error(sys.exc_info()[0])
            raise

    # If we get here, it's failed multiple times -- time to bail...
    log.error("Error: we failed this 3 times; there's no reason to believe it'll work if we do it again...")
    exit(1)

####################################################################

def print_owners(all_files, csvfile):
    print('')
    print("Gathering owners of files from source folder...")
    print('')

    owners = dict()
    for id, allfile in all_files.items():
        # Skip folders
        if allfile.is_folder:
            continue

        for owner in allfile.owners:
            owner_name  = owner['displayName']
            owner_email = owner['emailAddress']

            if owner_email not in owners:
                owners[owner_email] = {
                    'name'  : owner_name,
                    'files' : dict(),
                }

            owners[owner_email]['files'][id] = allfile

    # Setup for CSV output, if desired
    writer = None
    if csvfile:
        fieldnames = [ 'Owner name', 'Owner email',
                       'Filename', 'File link' ]
        writer     = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                    quoting=csv.QUOTE_ALL)
        writer.writeheader()

    # Display all the found owners
    for email, entry in owners.items():
        row = dict()
        row['Owner name']  = entry['name']
        row['Owner email'] = email

        print("{name} <{email}> owns {num} files:"
              .format(name=entry['name'], email=email,
                      num=len(entry['files'])))
        for id, gfile in entry['files'].items():
            row['Filename']  = gfile.name
            row['File link'] = gfile.webViewLink

            print("   File: {filename}\n   URL:  {wvl}"
                  .format(filename=gfile.name, wvl=gfile.webViewLink))

            if writer:
                writer.writerow(row)

#-------------------------------------------------------------------

def print_multiparents(service, root, all_files, csvfile):
    print('')
    print('Files/folders with multiple parents:')
    print('')

    multiparents = dict()
    for id, allfile in all_files.items():
        # Skip folders
        if allfile.is_folder:
            continue

        if len(allfile.parents) > 1:
            multiparents[id] = allfile

    # Setup for CSV output, if desired
    writer = None
    if csvfile:
        fieldnames = [ 'File name', 'File link',
                       'Folder name', 'Folder path', 'Folder link' ]
        writer     = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                    quoting=csv.QUOTE_ALL)
        writer.writeheader()

    # Display all the found multiparents
    for id, allfile in multiparents.items():
        row = dict()
        row['File name'] = allfile.name
        row['File link'] = allfile.webViewLink

        print("File: {filename}\nURL:  {wvl}"
              .format(filename=allfile.name,
                      wvl=allfile.webViewLink))
        print("      Appears in:")
        for parent in allfile.parents:
            row['Folder name'] = parent.name
            row['Folder path'] = parent.name_abs
            row['Folder link'] = parent.webViewLink

            print('        Folder: "{foldername}"'
                  .format(foldername=parent.name_abs))
            print('           URL: {wvl}'
                  .format(wvl=parent.webViewLink))

            if writer:
                writer.writerow(row)

#-------------------------------------------------------------------

# Find a list of contents of a particular root folder (GFile), and
# recursively call down into each folder.  Make a somewhat complicated
# data structure to represent the tree (remember that both files and
# folders can have multiple parents).
#
# tree:
#   .root_folder, a GFile instance:
#      .id
#      .mimeType: folder mime type
#      .name
#      .parents: list
#      .owners: JMS ???list
#      .team_id: None (will be populated later)
#   .contents: list, each entry is an instance of ContentEntry, representing an item in this folder
#      .gfile, a GFile instance:
#         .id
#         .mimeType
#         .name
#         .parents
#         .owners: JMS ???list
#         .team_id: None (will never be populated)
#      .is_folder: boolean, True if folder
#      .traverse: boolean, True if this is 1st time we've seen this folder
#      .tree: if traverse==True, a tree, otherwise None
#
# all_files: hash indexed by ID, each entry is:
#    .name
#    .webViewLink
#    .parents: list, each entry dictionary with these keys:
#       .parent_folder_name
#       .parent_folder_name_abs (contains entire name since root)
#       .parent_folder_id
#       .parent_folder_url: None (*may* be populated later)
#    .team_file: None (will be populated later)
#
def read_source_tree(service, prefix, root_folder, all_files = dict()):
    log.info('Discovering contents of folder: "{0}" (ID: {1})'
             .format(root_folder.name, root_folder.id))

    parent_folder_name_abs = '{0}/{1}'.format(prefix, root_folder.name)
    log.debug('parent folder name abs: {0}=={1}'
              .format(prefix, root_folder.name))
    tree = Tree(root_folder=root_folder, contents=[])

    # Iterate through everything in this root folder
    page_token = None
    query = "'{0}' in parents and trashed=false".format(root_folder.id)
    log.debug("Query: {0}".format(query))
    while True:
        response = doit(service.files()
                        .list(q=query,
                              spaces='drive',
                              corpora='user',
                              fields='nextPageToken,files(name,id,mimeType,parents,owners,webViewLink)',
                              pageToken=page_token,
                              supportsTeamDrives=True))
        for file in response.get('files', []):
            log.info('Found: "{0}"'.format(file['name']))
            id = file['id']
            traverse = False
            is_folder = False
            if file['mimeType'] == folder_mime_type:
                is_folder = True

            # We have already seen this file before
            if id in all_files:
                log.debug('--- We already know this file; cross-referencing...')

                # If this is a folder that we already know, then do
                # not traverse down into it (again).
                if is_folder:
                    log.debug('--- Is a folder, but we already know it; NOT adding to pending traversal list')
                    traverse = False

            # We have *NOT* already seen this file before
            else:
                log.debug('--- We do not already know this file; saving...')
                log.debug("Parents: {p}".format(p=file['parents']))
                all_files[id] = AllFiles(name=file['name'],
                                         webViewLink=file['webViewLink'],
                                         parents=[], # Filled in below
                                         is_folder=is_folder,
                                         owners=file['owners'])

                # If it's a folder, add it to the pending traversal list
                if is_folder:
                    traverse = True
                    log.debug("--- Is a folder; adding to pending traversal list")

            # Save this content entry in the list of contents for this
            # folder
            gfile = GFile(id=id,
                          mimeType=file['mimeType'],
                          webViewLink=file['webViewLink'],
                          name=file['name'],
                          parents=file['parents'],
                          owners=file['owners'],
                          team_file=None)
            content_entry = ContentEntry(gfile=gfile,
                                         is_folder=is_folder,
                                         traverse=traverse,
                                         contents=[],
                                         tree=None)
            tree.contents.append(content_entry)

            # JMS delete me
            log.debug("Created gfile for content entry: {0}"
                      .format(gfile))

            # Save this file in the master list of *all* files found.
            # Basically, add a parent listing to this ID in the
            # all_files index.
            parent_wvl = '<Unknown>'
            if root_folder.id in all_files:
                parent_wvl = all_files[root_folder.id].webViewLink

            parent = Parent(id=root_folder.id, name=root_folder.name,
                            name_abs=parent_folder_name_abs,
                            webViewLink=parent_wvl)
            all_files[id].parents.append(parent)

        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    # Traverse all the sub folders
    for entry in tree.contents:
        if entry.traverse:
            new_prefix = '{0}/{1}'.format(parent_folder_name_abs,
                                          entry.gfile.name)
            log.debug("== Traversing down into {0}"
                          .format(new_prefix))
            (t, all_files) = read_source_tree(service,
                                              parent_folder_name_abs,
                                              entry.gfile, all_files)
            entry.tree = t

    # Done!
    return (tree, all_files)

#-------------------------------------------------------------------

# Given a folder ID, verify that it is a valid folder.
# If valid, return a GFile instance of the folder.
def verify_folder_id(service, id):
    folder = doit(service.files().get(fileId=id,
                                      fields='id,mimeType,name,webViewLink,owners,parents',
                                      supportsTeamDrives=True))

    if folder is None or folder['mimeType'] != folder_mime_type:
        log.error("Error: Could not find any contents of folder ID: {0}"
                  .format(id))
        exit(1)

    log.info("Valid folder ID: {0} ({1})"
             .format(id, folder['name']))
    log.info("Folder: {0}".format(folder))
    if not 'parents' in folder:
        folder['parents']=None

    gfile = GFile(id=folder['id'], mimeType=folder['mimeType'],
                  webViewLink=folder['webViewLink'],
                  name=folder['name'],
                  parents=folder['parents'],
                  owners=folder['owners'],
                  team_file=None)

    return gfile

#-------------------------------------------------------------------

def add_cli_args():
    tools.argparser.add_argument('--source-folder-id',
                                 required=True,
                                 help='Source folder ID')

    tools.argparser.add_argument('--app-id',
                                 default=app_cred_file,
                                 help='Filename containing Google application credentials')

    tools.argparser.add_argument('--admin-credentials',
                                 default=admin_cred_file,
                                 help='Filename containing Google credentials for a domain superadmin.  This user must be able to read the entire source folder.')

    tools.argparser.add_argument('--csv',
                                 help='Output CSV file (optional)')

    tools.argparser.add_argument('--verbose',
                                 action='store_true',
                                 help='Be a bit verbose in what the script is doing')
    tools.argparser.add_argument('--debug',
                                 action='store_true',
                                 help='Be incredibly verbose in what the script is doing')
    tools.argparser.add_argument('--logfile',
                                 required=False,
                                 help='Store verbose/debug logging to the specified file')

    global args
    args = tools.argparser.parse_args()

#-------------------------------------------------------------------

def main():
    add_cli_args()

    # Setup logging
    setup_logging(args)

    # Authorize the app and provide user consent to Google
    app_cred = load_app_credentials(args.app_id)

    log.info("Authtenticating as administrator...")
    admin_cred = load_user_credentials(args.admin_credentials,
                                       scope, app_cred)
    admin_service = authorize(admin_cred)

    # Verify source folder ID.  Do this up front, before doing
    # expensive / slow things.
    source_folder = verify_folder_id(admin_service,
                                     id=args.source_folder_id)

    log.debug("Source folder is: {0}".format(source_folder))

    # Read the source tree
    (source_root, all_files) = read_source_tree(admin_service, '',
                                                source_folder)

    csvfile = None
    if args.csv:
        csvfile = open(args.csv, 'w', newline='')

    # Print the list of files with multiple parents
    print_multiparents(admin_service, source_root, all_files, csvfile)

    # Print a list of all file owners
    print_owners(all_files, csvfile)

    log.debug("END OF MAIN")

    if csvfile:
        csvfile.close()

if __name__ == '__main__':
    exit(main())
