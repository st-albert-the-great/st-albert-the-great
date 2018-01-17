#!/usr/bin/env python3.6

import datetime
import csv
import re

# A Google Form was used to ask parents which date(s) would work for
# them for a parent internet safety seminar.  In the resulting CSV,
# columns B through G represent different dates.  This script finds
# the 2 columns which, when you take the union of the 2, maximizes the
# total number of attendees.

#-------------------------------------------------------------------------

# Helper function

def check(results, x, y, old_best):
    attendees = dict()
    col_x = x - ord('A')
    col_y = y - ord('A')

    for row_num, row in enumerate(results):
        if row[col_x].startswith('Yes'):
            attendees[row_num] = True
        if row[col_y].startswith('Yes'):
            attendees[row_num] = True

    # Total number of attendees
    total = len(attendees.keys())
    print("Column 1:{x}->{xname}, Column 2:{y}->{yname}, total: {total}"
          .format(x=col_x, xname=chr(x),
                  y=col_y, yname=chr(y),
                  total=total))

    current = {
        'total' : total,
        'x'     : x,
        'y'     : y
    }

    # Is this the best result so far?
    new_best = old_best
    if old_best is None:
        new_best = [ current ]
    else:
        b = old_best[0]
        if total > b['total']:
            new_best = [ current ]
        if total == b['total']:
            new_best = old_best
            new_best.append(current)

    return new_best

#-------------------------------------------------------------------------

filename = 'results.csv'

results = list()
with open(filename, 'r', newline='') as csvfile:
    reader = csv.reader(csvfile)
    for row in reader:
        results.append(row)

# Delete the first row -- it's the headers
results.pop(0)

# We know that we want to check columns B through G (i.e., columns 1
# through 6)
best = None
for x in range(ord('B'), ord('G') + 1):
    for y in range(x + 1, ord('G') + 1):
        best = check(results, x, y, best)

# For convenience, convert x and y back to column letters
print("Best attendance:")
for b in best:
    print("{total}, first column {first}, second column {second}"
          .format(total=b['total'], first=chr(b['x']), second=chr(b['y'])))
