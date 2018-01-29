#!/usr/bin/env python3.6
#
# Split a big Rediker file up into individual PDFs.  Put them in
# directories:
#
# <graduation year>/<name>/<grade>.pdf


import argparse
import os
import re

# From https://pypi.python.org/pypi/PyPDF2
import PyPDF2

#====================================================================

parser = argparse.ArgumentParser(description='Rediker sux!')
parser.add_argument('--file', action='append',
                    required=True,
                    help='Rediker PDF file to process')
parser.add_argument('--sy',
                    required=True,
                    help='School year (syXXXX-XX)')

args = parser.parse_args()

#====================================================================

# Make sure the school year argument matches the right form
results = re.match('^sy(\d\d\d\d)-(\d\d)$', args.sy)
if not results:
    print('--sy argument must be of the form "syXXXX-XX"')
    exit(1)

sy_first = int(results.group(1))
sy_second = int(results.group(1)) + 2000

#====================================================================

def extract_from_pdf(page):
    # The first line of the page will be:
    #
    # <student name> #<x> Grade <grade> Homeroom: <hr> <mm-dd-yyyy>
    #
    # page.extractText() returns all of this one character at
    # a time, so just read in a bunch and then parse it out.
    line = ''
    for text in page.extractText():
        line += text
        if line.endswith('Homeroom:'):
            break

    # We got a line up to to "Homeroom:", so parse out the
    # info we want.
    result = search.match(line)
    if not result:
        print("Sad panda did not match; going to go cry quietly, in the snow")
        exit(1)

    name = result.group(1)
    grade = result.group(2)

    return name, grade

#====================================================================

def make_folder(grad_year, student_name):
    gy_name = 'class-of-{grad_year}'.format(grad_year=grad_year)
    if not os.path.exists(gy_name):
        os.mkdir(gy_name)

    full = os.path.join(gy_name, student_name)
    if not os.path.exists(full):
        os.mkdir(full)

    return full

#====================================================================

# JMS How does K and preK show up?
grad_suffix = {
    '01' : 'st',
    '02' : 'nd',
    '03' : 'rd',
    '04' : 'th',
    '05' : 'th',
    '06' : 'th',
    '07' : 'th',
    '08' : 'th'
}

def write_pdf(folder_name, grad_year, name, grade, page):
    pdf = PyPDF2.PdfFileWriter()
    pdf.addPage(page)

    filename = ('{grad_year}-{name}-{grade}{grade_suffix}-grade.pdf'
                .format(grad_year=grad_year,
                        grade=grade,
                        grade_suffix=grad_suffix[grade],
                        name=name))
    full_filename = os.path.join(folder_name, filename)

    with open(full_filename, 'wb') as out:
        pdf.write(out)

    print("Wrote: {f}".format(f=full_filename))

#====================================================================

# Now go through each of the files
search = re.compile('^(.+)#\d+.Grade.(\d+)Homeroom:')
for f in args.file:
    print("=== Processing file: {f}".format(f=f))

    if not os.path.exists(f):
        print("File {f} is not readable".format(f=f))
        exit(1)

    # Open each file passed in to the command line
    with open(f, 'rb') as fp:
        # Read in the PDF
        pdf = PyPDF2.PdfFileReader(fp)

        # For each page in that massive Rediker PDF...
        for p in range(pdf.getNumPages()):
            page = pdf.getPage(p)

            name, grade = extract_from_pdf(page)
            grad_year = str(sy_first - int(grade) + 8)

            # Make the folder
            folder_name = make_folder(grad_year, name)

            # Make a new output PDF
            write_pdf(folder_name, grad_year, name, grade, page)

# That's it!
