#!/usr/bin/env python

"""Script to "xcopy" a Google Drive folder to a Team Drive.

This script developed and tested with Python 3.6.x.  It has not been
tested with other versions (e.g., Python 2.7.x).

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

from pprint import pprint

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
                       'team_file',      # GFile
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

#-------------------------------------------------------------------

# parent_folder: gfile
# new_folder_name: string
def create_folder(service, parent_folder, new_folder_name):
    log.debug("Creating new folder {0}, parent {1} (ID: {2})"
              .format(new_folder_name, parent_folder.name, parent_folder.id))
    metadata = {
        'name' : new_folder_name,
        'mimeType' : folder_mime_type,
        'parents' : [ parent_folder.id ]
        }

    folder = doit(service.files().create(body=metadata,
                                         supportsTeamDrives=True,
                                         fields='id,name,mimeType,parents,webViewLink'))
    log.debug('Created folder: "{0}" (ID: {1})'
              .format(folder['name'], folder['id']))

    file = GFile(id=folder['id'],
                 mimeType=folder['mimeType'],
                 name=folder['name'],
                 parents=folder['parents'],
                 owners=list(),
                 webViewLink=folder['webViewLink'],
                 team_file=None)
    file.team_file = file

    return file

#-------------------------------------------------------------------

# Migrate an entire folder (and all of its contents) to the team
# drive.
#
# Traverse the source tree.  For each entry:
#
# - If it's a folder, make the corresponding folder in the Team Drive
# - If it's a file, copy it to the Team Drive
#
# Keep in mind the distinction between the *source* values (i.e.,
# values from the source tree) and the *team* values (i.e., values
# From the newly-created Team Drive tree).
#
# service: team drive API service
# source_root: tree (created by read_source_tree())
# team_root: gfile
# all_files: hash indexed by ID (created by read_source_tree())
#
# This routine will not be called if this is a dry run, so no need for
# such protection inside this function.
def migrate_folder_to_team_drive(admin_service, user_services, owning_domain,
                                 source_root, team_root, all_files):
    log.debug('Migrating folder to Team Drive: "{folder}"'
              .format(folder=source_root.root_folder.name))

    # Now go through all the entries and find all the sub-folders.
    # Copy them one-by-one to the target team drive.
    for source_entry in source_root.contents:
        # Folder
        if source_entry.is_folder:
            # Make the corresponding folder in the team drive
            make_folder_in_team_drive(admin_service,
                                      source_root, team_root,
                                      all_files, source_entry)

            # Traverse into the source subfolder
            if source_entry.traverse:
                source_id = source_entry.gfile.id
                migrate_folder_to_team_drive(admin_service, user_services,
                                             owning_domain,
                                             source_entry.tree,
                                             all_files[source_id].team_file,
                                             all_files)

        # File
        else:
            migrate_file_to_team_drive(admin_service, user_services,
                                       owning_domain,
                                       source_root, team_root,
                                       all_files, source_entry)

#-------------------------------------------------------------------

# Migrate a single file to the team drive.
#
# admin_service: team drive API service with admin creds
# user_services: hash of email address + corresponding service/creds
# owning_domain: domain name that owns the target team drive
# source_root: Tree (created by read_source_tree())
# team_root: GFile
# all_files: hash indexed by ID (created by read_source_tree())
# source_file_entry: ContentEntry of file to move
def migrate_file_to_team_drive(admin_service, user_services,
                               owning_domain,
                               source_root, team_root,
                               all_files, source_file_entry):
    log.info('- Migrating "{file}" from "{source}" to Team drive'
             .format(source=source_root.root_folder.name,
                     file=source_file_entry.gfile.name))

    # 0. If the file has multiple parents, Google will not let us move
    #    it to the team drive.  Copy it instead, but put a "MULTIFILE"
    #    prefix on the destination filenames in the Team Drive so that
    #    the owners know that there's multiple copies.
    # 1. If the file is owned by a user in the same domain as the
    #    admin, move it with the admin service.
    # 2. If the file is owned by any of the user credentials, move
    #    it with the corresponding user service.
    # 3. Otherwise, copy the file.

    service  = None
    rename   = None
    can_move = False

    if len(source_file_entry.gfile.parents) > 1:
        log.info("  This file has multiple parents.")
        log.info('  It will be copied to the Team Drive with a "MULTIFILE" prefix')
        service = admin_service
        rename  = 'MULTIFILE ' + source_file_entry.gfile.name

    # Check to see if the owner of the file is in the owning domain.
    # I think it's an anachronism that there can be multiple owners
    # for a file (i.e., I don't think Google supports this any more),
    # but cover our bases.
    if service is None:
        owners  = source_file_entry.gfile.owners
        for owner in owners:
            owner_name = owner['displayName']
            owner_email = owner['emailAddress']

            # Is this file owned by someone in the target domain?
            if owner_email.endswith(owning_domain):
                log.info("  This file is owned by {name} <{email}> in the target domain.  WE CAN MOVE IT."
                         .format(name=owner_name,
                                 email=owner_email))
                service  = admin_service
                can_move = True
                break

            # If this file owned by someone for whom we have user
            # credentials?
            else:
                for us in user_services:
                    if owner_email == us['address']:
                        log.info("  This file is owned by {name} <{email}>, for whom we have user credentials.  WE CAN MOVE IT."
                                 .format(name=owner_name,
                                         email=owner_email))
                        service  = us['service']
                        can_move = True
                        break

                # If we found a winnner, we're done
                if can_move:
                    break

    # Ok, we're ready: move or copy it
    moved = False
    if can_move:
        moved = move_file_to_team_drive(service,
                                        source_root, team_root,
                                        all_files, source_file_entry)

    if not moved:
        log.info("  Looks like we have to COPY this file")
        copy_file_to_team_drive(admin_service, source_root, team_root,
                                all_files, source_file_entry,
                                rename=rename)

#-------------------------------------------------------------------

def move_file_to_team_drive(service, source_root, team_root,
                            all_files, source_file_entry):
    migrated_file = doit(service
			 .files()
			 .update(fileId=source_file_entry.gfile.id,
				 addParents=team_root.id,
				 removeParents=source_file_entry.gfile.parents[0],
                                 supportsTeamDrives=True,
				 fields='id'),
                         can_fail=True)
    if migrated_file is not None:
        log.debug("--> Moved!")
        return True
    else:
        log.debug("--> Failed to move file")
        return False

#-------------------------------------------------------------------

def copy_file_to_team_drive(service, source_root, team_root,
                            all_files, source_file_entry,
                            rename=None):
    new_name = rename or source_file_entry.gfile.name
    copied_file = doit(service
                       .files()
                       .copy(fileId=source_file_entry.gfile.id,
                             body={ 'parents' : [team_root.id],
                                    'name' : new_name },
                             supportsTeamDrives=True,
                             fields='id'),
                       can_fail=True)
    if copied_file is None:
        print("ERROR: Failed to copy file!")
        exit(1)
    else:
        log.debug("--> Copied")

#-------------------------------------------------------------------

def make_folder_in_team_drive(service, source_root, team_root,
                              all_files, source_folder_entry):
    log.debug('- Making sub folder: "{new}" in "{old}"'
                  .format(old=source_root.root_folder.name,
                          new=source_folder_entry.gfile.name))

    # Make the folder in the Team Drive
    source_id = source_folder_entry.gfile.id
    team_folder = create_folder(service, team_root,
                                source_folder_entry.gfile.name)
    all_files[source_id].team_file = team_folder

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
                all_files[id] = AllFiles(name=file['name'],
                                         webViewLink=file['webViewLink'],
                                         parents=list(),
                                         team_file=None)

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

# This routine will not be called if this is a dry run, so no need for
# such protection inside this function.
def create_team_drive(service, source_folder):
    log.debug('Creating Team Drive: "{0}"'
          .format(source_folder.name))
    metadata = {
        'name' : source_folder.name,
        }
    u = uuid.uuid4()
    tdrive = doit(service.teamdrives().create(body=metadata,
                                              requestId=u))
    log.info('Created Team Drive: "{0}" (ID: {1})'
          .format(source_folder.name, tdrive['id']))

    file = GFile(id=tdrive['id'], mimeType=team_drive_mime_type,
                 webViewLink=None,
                 name=tdrive['name'],
                 parents=['root'],
                 owners=list(),
                 team_file=None)
    return file

#-------------------------------------------------------------------

# Ensure there is no Team Drive of the same folder name
def verify_no_team_drive_name(service, args, source_folder, name):
    page_token = None
    while True:
        response = doit(service.teamdrives()
                        .list(pageToken=page_token))
        str = ("Looking for a Team Drive named '{name}'"
               .format(name=source_folder.name))
        if name:
            str = str + (" or '{name}'"
                         .format(name=name))
        log.info(str)

        for team_drive in response.get('teamDrives', []):
            log.debug("Checking existing team drive: {name}"
                      .format(name=team_drive['name']))
            found = False
            if name and team_drive['name'] == name:
                found = True
            elif team_drive['name'] == source_folder.name:
                found = True

            if found:
                # By default, abort if a Team Drive of the same name
                # already exists.  But if the user said it was ok,
                # keep going if it already exists.
                if args.debug_team_drive_already_exists_ok:
                    log.info('Team Drive "{name}" already exists, but proceeding anyway...'
                                 .format(name=source_folder.name))
                    file = GFile(id=team_drive['id'],
                                 mimeType=team_drive_mime_type,
                                 webViewLink=None,
                                 name=team_drive['name'],
                                 owners=list(),
                                 parents=['root'],
                                 team_file=None)
                    return file
                else:
                    log.error('Found existing Team Drive of same name as source folder: "{0}" (ID: {1})'
                                  .format(source_folder.name, team_drive['id']))
                    log.error("There cannot be an existing Team Drive with the same name as the source folder")
                    exit(1)

        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    # If we get here, we didn't find a team drive with the same name.
    # Yay!
    log.info("Verified: no existing Team Drives with same name as source folder ({0})"
             .format(source_folder.name))
    return

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
    tools.argparser.add_argument('--dest-team-drive',
                                 help='Destinaton Team Drive name')
    tools.argparser.add_argument('--owning-domain',
                                 required=True,
                                 help='Name of the domain that will own this team drive (and domain of the --admin-credentials superadmin)')

    tools.argparser.add_argument('--app-id',
                                 default=app_cred_file,
                                 help='Filename containing Google application credentials')

    tools.argparser.add_argument('--admin-credentials',
                                 default=admin_cred_file,
                                 help='Filename containing Google credentials for a domain superadmin.  This user must be able to read the entire source folder.')

    tools.argparser.add_argument('--user-credentials',
                                 action='append',
                                 nargs=2,
                                 help='Google email address and filename containing Google credentials for a non-domain user (optional)')

    tools.argparser.add_argument('--dry-run',
                                 action='store_true',
                                 help='Go through the motions but make no actual changes')

    tools.argparser.add_argument('--copy-all',
                                 action='store_true',
                                 help='Instead of moving files that are capable of being moved to the new Team Drive, *copy* all files to the new Team Drive')

    tools.argparser.add_argument('--verbose',
                                 action='store_true',
                                 help='Be a bit verbose in what the script is doing')
    tools.argparser.add_argument('--debug',
                                 action='store_true',
                                 help='Be incredibly verbose in what the script is doing')
    tools.argparser.add_argument('--logfile',
                                 required=False,
                                 help='Store verbose/debug logging to the specified file')
    tools.argparser.add_argument('--debug-team-drive-already-exists-ok',
                                 action='store_true',
                                 help='For debugging only: don\'t abort if the team drive already exists')

    global args
    args = tools.argparser.parse_args()

    if args.dest_team_drive:
        args.debug_team_drive_already_exists_ok = True

    # Put a "@" on the owning domain, just to make comparisons easier
    # later
    args.owning_domain = '@' + args.owning_domain

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

    user_services = list()
    if args.user_credentials:
        for vals in args.user_credentials:
            email    = vals[0]
            filename = vals[1]
            log.info("Authenticating as user: {filename}"
                     .format(filename=filename))
            user_cred = load_user_credentials(filename,
                                              scope, app_cred)
            user_services.append({
                'service' : authorize(user_cred),
                'address' : email,
            })

    # Verify source folder ID.  Do this up front, before doing
    # expensive / slow things.
    source_folder = verify_folder_id(admin_service,
                                     id=args.source_folder_id)

    log.debug("Source folder is: {0}".format(source_folder))

    # If this is not a dry run, do some checks before we read the
    # source tree.
    team_drive = None
    if not args.dry_run:
        # Otherwise, find the Team Drive, if it already exists
        team_drive = verify_no_team_drive_name(admin_service, args,
                                               source_folder,
                                               name=args.dest_team_drive)

    # Read the source tree
    (source_root, all_files) = read_source_tree(admin_service, '',
                                                source_folder)

    # If dry run, we're done
    if args.dry_run:
        log.info("DRY RUN -- done!")
        return 0

    #------------------------------------------------------------------
    # If we get here, it means we're good to go to create the new Team
    # Drive and move/copy all the files to it.
    #------------------------------------------------------------------

    # Make a Team Drive of the same folder name
    if team_drive is None:
        team_drive = create_team_drive(admin_service, source_folder)

    # Do it
    migrate_folder_to_team_drive(admin_service, user_services,
                                 args.owning_domain,
                                 source_root, team_drive, all_files)

    log.debug("END OF MAIN")

if __name__ == '__main__':
    exit(main())
