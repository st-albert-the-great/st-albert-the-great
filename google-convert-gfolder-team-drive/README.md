# Notes

The scripts in this directory are not polished.  They were written for
one-time uses to convert several specific shared Google Folders to
Google Team Drives.  Each of the scripts has some hard-coded
assupmtions that are certainly not true for everyone's particular
setups of shared folders / team drives.  Additionally, since they were
intended for one-time use, they really aren't polished, or, in some
cases, complete (e.g., sometimes it was easier/faster to leave the
script incomplete and then just manually use the Google Drive web UI
to fix up what the script didn't do).

# Making a Google Account client_id.json file:

1. Make a project in the Google APIs dashboard:

    https://console.developers.google.com/apis/dashboard

2. Click "Enable API"

3. Select "Google Drive API"

4. It says "A project is needed to enable APIs".  Click on the "Create
Project" button.

5. Takes you to another page with another "Create" button to create a
project.

6. Name the project: "Python Drive access", and create it.

7. Enable the Google Drive API on this project.

8. Now create some credentials:
   - Google Drive API
   - Other UI (CLI tool)
   - User data

9. Click "What credentials do I need?"

10. Name the client "Python CLI client"

11. Click "Create client ID"

12. Pick any email address (e.g., the default is fine), and type in
"Python CLI Client" in the product name field.  Click continue.

13. Click "Download" to download client_id.json file.  Save the
client_id.json file somewhere safe.

14. Click "Done"

---------------

# Checklist to migrate from a StA Google Shared Folder to a Team Drive

Need to do this for each folder tree that is converted to a Team
Drive:

1.  Surf to the folder
2.  Copy the folder ID to both scripts
3.  mkdir NAME
4.  ./run-scan-and-report.zsh |& tee NAME/search-out.txt
5.  mv report.csv NAME
6.  If jsquyres@gmail.com owns any files, make sure jsq@gmail.com has
    access to the source folder
7.  Make a new team drive
8.  Copy-n-paste the name to the script
9.  Assign full permissions to:
    itadmingroup
    team-drive-permissions-to-be-deleted...
10. Remove jsquyres@stalbert.org
11. Assign full permissions to:
    everyone else on the source google folder
12. ./run-gxcopy.zsh |& tee NAME/gxcopy-out.txt
13. Eyeball the target team drive -- did it copy over ok?
14. Remove the "team-drive-permissions-to-be-deleted..." group
15. Go to the google sheet
16. Paste in the team drive link
17. Put "DONE" in column E
18. Navigate back to the source folder
19. Rename to "DEFUNCT AND UNSHARED -- ..."
20. Remove all permissions except to itadmingroup
