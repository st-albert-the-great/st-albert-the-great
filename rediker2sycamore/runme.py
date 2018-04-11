#!/usr/bin/env python3.6

import csv
import os

student_family_file = "StudentFamily.csv"
student_data_file   = "StudentData.csv"
title_id_file       = "TitleID.csv"

#--------------------------------------------------------------

def read_family_data():
    account_order = list()
    family_data = dict()

    with open(student_family_file, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        # Skip the first 5 rows (i.e., rows 2, 3, 4, 5, 6 from the
        # spreadsheet)
        for i, row in enumerate(reader):
            if i < 5:
                print("Skipping row: {}".format(row['First Name']))
                continue

            account = row['External ID']
            account_order.append(account)
            family_data[account] = row

    return account_order, family_data

#--------------------------------------------------------------

def read_student_data():
    student_data = dict()
    with open(student_data_file, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            account = row['Account Number']
            student_data[account] = row

    return student_data

#--------------------------------------------------------------

def read_title_data():
    title_data = dict()
    with open(title_id_file, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            title = row['Title']
            id    = row['ID']
            title_data[title] = id

    return title_data

#--------------------------------------------------------------

def load_grades():
    grades = {
        "P3" : "-2",
        "P4" : "-1",
        "0K" : "0",
        "1"  : "1",
        "2"  : "2",
        "3"  : "3",
        "4"  : "4",
        "5"  : "5",
        "6"  : "6",
        "7"  : "7",
        "8"  : "8"
    }

    return grades

#--------------------------------------------------------------

def load_relationships():
    rels = {
        "Father"           : "1",
        "Mother"           : "2",
        "Grandfather"      : "3",
        "Grandmother"      : "4",
        "Stepfather"       : "5",
        "Stepmother"       : "6",
        "Step Mother"      : "6",
        "Guardian"         : "7",
        "Legal Guardian"   : "8",
        "Not Defined"      : "9",
        "Relative"         : "10",
        "Foster Father"    : "11",
        "Foster Mother"    : "12",
        "Grandparents"     : "13",
        "DayCare Provider" : "14",
        "Close Friend"     : "15",
        "Parents"          : "16",
        "Student"          : "17",
        "Sibling"          : "18",
        "Colleague"        : "19",
        "Helper"           : "20",

        # Map these generics to "Parents" (16)
        ""                 : "16",
        "Parent 1"         : "16",
        "Parent 2"         : "16"
    }

    return rels

#--------------------------------------------------------------

# Main

# Read in the student data
account_order, family_data = read_family_data()
student_data               = read_student_data()

# Read in / load up the translations
title_translations         = read_title_data()
grade_translations         = load_grades()
relationship_translations  = load_relationships()

# Do the translations
# For each row in the family data, map the following:
# 1. Grade (from the student data: "GRADE LEVEL")
# 2. Parent 1 Title (student data "CONTACT1.SALULATION")
# 3. Parent 1 Relationship (student data "CONTACT1.RELATIONSHIP")
# 4. Parent 2 Title (student data "CONTACT2.SALULATION")
# 5. Parent 2 Relationship (student data "CONTACT2.RELATIONSHIP")

new_data = dict()
for account in account_order:
    family  = family_data[account]
    student = student_data[account]

    new_row = dict()
    # Include the student first and last name, just so that it's
    # easier for a human to read the output CSV and verify that it
    # lines up properly.
    new_row['first'] = family['First Name']
    new_row['last']  = family['Last Name']

    new_row['grade']           = grade_translations[student["GRADE LEVEL"]]
    new_row['p1 title']        = title_translations[student["CONTACT1.SALUTATION"]]
    new_row['p1 relationship'] = relationship_translations[student["CONTACT1.RELATIONSHIP"]]
    new_row['p2 title']        = title_translations[student["CONTACT2.SALUTATION"]]
    new_row['p2 relationship'] = relationship_translations[student["CONTACT2.RELATIONSHIP"]]

    new_data[account] = new_row

# Write out the output CSV
with open("output.csv", "w") as csvfile:
    fieldnames = [
        'first', 'last',
        'grade',
        'p1 title', 'p1 relationship',
        'p2 title', 'p2 relationship'
    ]
    writer = csv.DictWriter(csvfile, fieldnames)
    writer.writeheader()

    for account in account_order:
        row = new_data[account]
        writer.writerow(row)

# Done!
