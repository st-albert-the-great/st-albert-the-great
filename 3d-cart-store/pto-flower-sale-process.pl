#!/usr/bin/env perl

# This helper script takes a CSV export of sales from the 3d cart
# store and parsed out the "options" from the itemname column and add
# extra rows at the end with those options (in this case, the only
# option is the color of some of the flowers).
#
# The script is currently hard-coded to look for item ID's with
# "1368.81" in the name.  This should probably be turned into a
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
my $all_columns;
$all_columns = $csv->getline($fh);
my $col = 0;
my $itemname_column = 0;
my $itemid_column = 0;
foreach my $field (@$all_columns) {
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
        if ($row->[$itemid_column] =~ /1368\.81/);
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
my $all_itemname_columns;
foreach my $row (@rows) {
    my $item = $$row[$itemname_column];
    my @columns = parse_itemname($item);

    foreach my $c (@columns) {
        $all_itemname_columns->{$c->{name}} = 1;
    }
}

# Open the output CSV
open(OUT, ">processed.csv") ||
    die "Can't write to processed.csv";

# Write the first line of the output CSV: the union of all the column
# names.
print OUT join(",", @{$all_columns}) . "," .
    join(",", sort(keys(%{$all_itemname_columns}))) . "\n";

# Now write all the values
foreach my $row (@rows) {
    my $item = $$row[$itemname_column];
    my @columns = parse_itemname($item);

    print OUT join(',', @{$row}) . ",";

    # Output all the values.  Must go in the same order that we output
    # the first line.  If we don't have that value, output an empty
    # column.  :-(
    foreach my $column (sort(keys(%{$all_itemname_columns}))) {
        foreach my $c (@columns) {
            if ($c->{name} eq $column) {
                my $value = $c->{value};
                if ($value =~ /,/) {
                    print OUT "\"$value\"";
                } else {
                    print OUT "$value";
                }
            }
            print OUT ",";
        }
    }
    print OUT "\n";
}

close($fh);
