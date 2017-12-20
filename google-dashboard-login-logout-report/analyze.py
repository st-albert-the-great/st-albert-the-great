#!/usr/bin/env python3.6

import datetime
import csv
import re

# "Close enough" estimation of Chromebook usage based on login records
# from Google of 2, 3, 4, and 5th graders.

#-----------------------------------------------------------------

'''
August 16, 2017: first day of SY 2017-18
December 18, 2017: last full day of 1st semester SY 2017-18
'''

def setup_dates():
    holidays = [
        datetime.date(2017,  9,  4), # Labor Day
        datetime.date(2017,  9, 19), # 1pm dismissal
        datetime.date(2017, 10,  5), # In service
        datetime.date(2017, 10,  6), # In service
        datetime.date(2017, 11,  7), # 1pm dismissal
        datetime.date(2017, 11, 20), # Thanksgiving week
        datetime.date(2017, 11, 21), # Thanksgiving week
        datetime.date(2017, 11, 22), # Thanksgiving week
        datetime.date(2017, 11, 23), # Thanksgiving week
        datetime.date(2017, 11, 24)  # Thanksgiving week
    ]

    start   = datetime.date(2017, 8, 16)
    end     = datetime.date(2017, 12, 18)
    one_day = datetime.timedelta(days=1)

    dates = list()
    d = start
    while d <= end:
        school_day = True

        # Skip weekends (Monday = 0, Sunday = 6)
        if d.weekday() >= 5:
            school_day = False

        # Skip school holidays
        found = False
        for holiday in holidays:
            if d == holiday:
                found = True
                school_day = False
                break

        # If this is not a holiday, save it!
        if school_day:
            dates.append(d)

        # Move on to the next date
        d = d + one_day

    print("Found {num} school days"
          .format(num=len(dates)))
    return dates

#-----------------------------------------------------------------

'''classes:

mon-wed,fri
1:  7:55
2:  8:40
3:  9:25
4: 10:10
5: 10:55
6: 11:35
7: 12:20
8:  1:05
9:  1:50
10: 2:35 end

thu:
1:  7:55
2:  8:35 x
3:  9:15 x
4: 10:15 x
5: 10:55
6: 11:35
7: 12:20
8:  1:05
9:  1:50
10: 2:34 end

The indexes are the same, even if the class times differ a little.
'''

def setup_class_periods():
    class_periods = dict()

    # Monday, according to datetime.weekday()
    class_periods['0'] = [
        datetime.time( 7, 30, 0),
        datetime.time( 8, 38, 0),
        datetime.time( 9, 23, 0),
        datetime.time(10,  8, 0),
        datetime.time(10, 53, 0),
        datetime.time(11, 32, 0),
        datetime.time(12, 18, 0),
        datetime.time(13,  3, 0),
        datetime.time(13, 48, 0)
        ]

    # Tuesday, Wednesday, and Friday are just like Monday
    class_periods['1'] = class_periods['0']
    class_periods['2'] = class_periods['0']
    class_periods['4'] = class_periods['0']

    # Thursdays are different
    class_periods['3'] = [
        datetime.time( 7, 30, 0),
        datetime.time( 8, 33, 0),
        datetime.time( 9, 12, 0),
        datetime.time(10, 13, 0),
        datetime.time(10, 53, 0),
        datetime.time(11, 32, 0),
        datetime.time(12, 18, 0),
        datetime.time(13,  3, 0),
        datetime.time(13, 48, 0)
        ]

    return class_periods

#-----------------------------------------------------------------

def read_grade(filename):
    grade = list()

    with open(filename, 'r', newline='') as csvfile:
        fieldnames = ['Email address', 'First name', 'Last name',
                      'Last Login', 'Agreed to terms', 'Status',
                      'Email usage', 'Drive usage', 'Total storage',
                      'Organization name',
                      '2-step verification enrollment',
                      '2-step verification enforcement']
        reader = csv.DictReader(csvfile, fieldnames=fieldnames)

        first = True
        for row in reader:
            # Skip first row -- it's the headers
            if first:
                first = False
                continue

            row['Full name'] = '{first} {last}'.format(first=row['First name'],
                                                       last=row['Last name'])
            grade.append(row)

    print("Found {num} students in {file}"
          .format(num=len(grade), file=filename))
    return grade

#-----------------------------------------------------------------

def parse_description(row):
    if 'logged in' in row:
        match = re.search('^(.+)\s+logged in', row)
        name = match[1]
        action = 'login'

    elif 'logged out' in row:
        match = re.search('^(.+)\s+logged out', row)
        name = match[1]
        action = 'logout'

    else:
        # We don't care about the others
        return None, None

    return name, action

#-----------------------------------------------------------------

def read_log_events(filename, grades, ip, school_dates):
    events = list()
    with open(filename, 'r', newline='') as csvfile:
        fieldnames = ['Event Description', 'IP Address', 'Date']
        reader = csv.DictReader(csvfile, fieldnames=fieldnames)

        first = True
        for row in reader:
            # Skip first row -- it's the headers
            if first:
                first = False
                continue

            # If this wasn't a login from the target IP address, skip
            # it
            if row['IP Address'] != ip:
                continue

            # Parse the date.  It may end in "EST" or "EDT", so strip
            # that off the end before parsing the time.
            match = re.match('^(.+) E[SD]T', row['Date'])
            dt = datetime.datetime.strptime(match[1],
                                            '%B %d %Y %I:%M:%S %p')

            # See if this is a school day
            d = dt.date()
            if d not in school_dates:
                continue

            # We only care about between 7:30am and 3pm.
            t = (dt.hour * 100) + dt.minute
            if t < 730 or t > 1500:
                continue

            # Get the name and action of this event from the log
            # (Google puts this one field in the form of "FIRST LAST
            # ACTION", so we have to split it apart).  We'll get
            # "None" if this was not a successful login or logout.
            name, action = parse_description(row['Event Description'])
            if not name or not action:
                continue

            found = False
            for grade in grades:
                for student in grades[grade]:
                    if student['Full name'] == name:
                        found = True
                        break

            # If this wasn't a relevant student, skip it
            if not found:
                continue

            # If we got here, we are logging in from the StA campus,
            # on a weekday, and we have a valid name and action.

            # Save it all!
            event = {
                'name'     : name,
                'action'   : action,
                'datetime' : dt
            }
            events.append(event)

    print("Found {num} relevant events"
          .format(num=len(events)))
    return events

#-----------------------------------------------------------------

def find_class(class_periods, dt):
    d = dt.date()
    t = dt.time()
    day = str(d.weekday())
    for i in range(0, len(class_periods[day]) - 1):
        if t >= class_periods[day][i] and t < class_periods[day][i + 1]:
            return i

    return None

#-----------------------------------------------------------------

def analyze(class_periods, grades, events):
    # All the events we get here are already "good".  I.e., they're
    # from the right IP, they're from a student, they're on a school
    # day, and they're in school hours.

    usage = dict()

    # Find all login events, and put them in buckets of:
    # usage[date][class number][grade] = count
    for event in events:
        if event['action'] != 'login':
            continue

        # Find which class we're in
        dt = event['datetime']
        c = find_class(class_periods, dt)

        # Find which grade the student is in
        found = None
        for grade in grades:
            g = grades[grade]

            for student in g:
                if student['Full name'] == event['name']:
                    found = grade
                    break

            if found:
                break

        if not found:
            print("THIS SHOULDN'T HAPPEN")
            exit(1)

        d = dt.date()
        if d not in usage:
            usage[d] = dict()
        if c not in usage[d]:
            usage[d][c] = dict()
        if grade not in usage[d][c]:
            usage[d][c][grade] = 0

        usage[d][c][grade] += 1

    return usage

#-----------------------------------------------------------------

# Usage is in the form of usage[date][class number][grade].
def print_usage(threshhold, total_class_periods, usage):
    print("Threshhold: {}".format(threshhold))
    used_count = dict()
    for d in usage:
        for class_number in usage[d]:
            for grade in usage[d][class_number]:

                if grade not in used_count:
                    used_count[grade] = 0

                if usage[d][class_number][grade] > threshhold:
                    used_count[grade] += 1

    # Print some percentages
    for grade in used_count:
        u = used_count[grade]

        print("Grade {grade}: cart was used {used} out of {total} class periods ({percent:.1%})"
              .format(grade=grade, used=u, total=total_class_periods,
                      percent=u / total_class_periods))

#-----------------------------------------------------------------

# Usage is in the form of usage[date][class number][grade].
def write_usage(school_dates, class_periods, grades, usage):
    # Write to a CSV
    filename = 'usage.csv'

    fieldnames = ['Grade', 'Class period']
    for d in school_dates:
        fieldnames.append(str(d))

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile,# fieldnames=fieldnames,
                                quoting=csv.QUOTE_ALL)

        # Write out the header row
        writer.writerow(fieldnames)

        # Write out all the grades
        for grade in grades:
            # For each grade, write out a class time
            for class_num, class_time in enumerate(class_periods['0']):
                row = [ grade, class_num + 1 ]
                for d in usage:
                    found = False
                    if class_num in usage[d]:
                        if grade in usage[d][class_num]:
                            found = True
                            row.append(usage[d][class_num][grade])
                    if not found:
                        row.append(0)
                writer.writerow(row)

            # Write a blank line between grades
            row = []
            writer.writerow(row)

    print("Wrote to {}".format(filename))

##################################################################
# Main

school_dates = setup_dates()
class_periods = setup_class_periods()

# Read students by class
grades = dict()
grades['5'] = read_grade('class-of-2021-5th.csv')
grades['4'] = read_grade('class-of-2022-4th.csv')
grades['3'] = read_grade('class-of-2023-3rd.csv')
grades['2'] = read_grade('class-of-2024-2nd.csv')

# Read the event log, looking for student logins from the target IP
# address (i.e., St. Albert campus IP)
log_filename = 'stalbert-login-logout-report.csv'
ip = '74.142.175.226'
events = read_log_events(log_filename, grades, ip, school_dates)

# Now analyze the logs and find all student logins by class
usage = analyze(class_periods, grades, events)

# Total number of class periods.  Note that we do not add 1 to the len
# of class_periods() because we need to "subtract" one period for lunch.
total_class_periods = (len(school_dates) + 1) * len(class_periods['0'])
print("Found {} total class periods".format(total_class_periods))

# Print usage with different threshholds
print_usage(10, total_class_periods, usage)
print_usage(15, total_class_periods, usage)
print_usage(20, total_class_periods, usage)

write_usage(school_dates, class_periods, grades, usage)
