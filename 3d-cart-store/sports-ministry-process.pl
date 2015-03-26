#!/usr/bin/env perl

# This helper script takes a CSV export of sales from the 3d cart
# store and parsed out the "options" from the itemname column and put
# them into a new CSV consisting of just these values.
#
# Specifically, when someone registers for a sport on the 3d cart
# store, there's a series of questions that must be answered before
# the item (i.e., registration) can be added to the cart, such as:
# athlete name, uniform size, ...etc.  All of these questions get
# mushed into a single column in the CSV sales report that you can
# download from the store, making it fairly unintelligible for a human
# to read.  Plus, the sports ministry doesn't need all the billing
# information that comes in the CSV sales report -- all they need is
# the answers to the questions that accompanied the purchase of the
# sports registration.  This script simply parses out those answers
# and outputs them into a new CSV that can be easily used by the
# Sports Ministry to list all the athletes who have registered, etc.
#
# The script is currently hard-coded to look for item ID's with
# "2015-SPR" in the name.  This should probably be turned into a
# command line option.

###################################################################

use strict;
use warnings;

use Text::CSV;
use Data::Dumper;

die "Must specify file"
    if (!defined($ARGV[0]));

###################################################################

my $csv = Text::CSV->new();

my $fh;
open($fh, $ARGV[0]) ||
    die("Can't open file $ARGV[0]");

# Find the "itemname" column
my $fields;
$fields = $csv->getline($fh);
my $col = 0;
my $itemname_column = 0;
my $itemid_column = 0;
foreach my $field (@$fields) {
    $itemname_column = $col
        if ($field eq "itemname");
    $itemid_column = $col
        if ($field eq "itemid");
    ++$col;
}

# Read in the rest of the input
my @rows;
while (my $row = $csv->getline($fh)) {
    push(@rows, $row)
        if ($row->[$itemid_column] =~ /2015-SPR/);
}
close($fh);

###################################################################

sub parse_itemname {
    my $item = shift;

    # The fields in the itemname are delimited by <br>.
    my @fields;
    @fields = split(/<br>/i, $item);

    # The first one is the name of the form, and can be ignored
    shift(@fields);

    my @columns;
    # There are two forms
    foreach my $field (@fields) {
        # First form: <b>Field name</b>&nbsp;Label:value
        if ($field =~ m@<b>(.+?)</b>&nbsp;(.+?):(.+?)$@) {
            push(@columns, {
                name => $1,
                label => $2,
                value => $3,
                });
        }
        # Second form: <b>Field name:</b>&nbsp;value
        elsif ($field =~ m@<b>(.+?):</b>&nbsp;(.+?)$@) {
            push(@columns, {
                name => $1,
                value => $2,
                });
        }
    }

    return @columns;
}

###################################################################

# If someone didn't fill in a field in a given row, then it's not
# reported in that row (i.e., that column isn't blank -- it isn't even
# reported).  Sigh.  So scan through *all* the rows and find the
# union of *all* the column names.
my $all_columns;
foreach my $row (@rows) {
    my $item = $$row[$itemname_column];
    my @columns = parse_itemname($item);

    foreach my $c (@columns) {
        $all_columns->{$c->{name}} = 1;
    }
}

# Open the output CSV
open(OUT, ">processed.csv") ||
    die "Can't write to processed.csv";

# Write the first line of the output CSV: the union of all the column
# names.
print OUT join(",", sort(keys(%{$all_columns}))) . "\n";

# Now write all the values
foreach my $row (@rows) {
    my $item = $$row[$itemname_column];
    my @columns = parse_itemname($item);

    # Output all the values.  Must go in the same order that we output
    # the first line.  If we don't have that value, output an empty
    # column.  :-(
    my $first = 1;
    foreach my $column (sort(keys(%{$all_columns}))) {
        print OUT ","
            if (!$first);
        $first = 0;

        foreach my $c (@columns) {
            if ($c->{name} eq $column) {
                my $value = $c->{value};
                if ($value =~ /,/) {
                    print OUT "\"$value\"";
                } else {
                    print OUT "$value";
                }
            }
        }
    }
    print OUT "\n";
}

close($fh);
