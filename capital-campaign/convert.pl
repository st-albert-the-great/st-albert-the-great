#!/opt/local/bin/perl

use strict;
use warnings;

use Data::Dumper;
use Text::CSV_XS;

my $fh;
open($fh, "Contact Report for B Families.csv") || die "Can't open file";
my $csv = Text::CSV_XS->new ({ binary => 1, auto_diag => 1 });

# Read the first 5 header lines
<$fh>;
<$fh>;
<$fh>;
<$fh>;
<$fh>;

my $families;
my $fam;
my @phones;
my $record_line = 0;

while (<$fh>) {
    next
        if (!$csv->parse($_));
    my @fields = $csv->fields();
#    print Dumper(@fields);

    # If we get a first field, we have started a new name/record
    my $name = 0;
    my $email;
    if ($fields[0] ne "") {
        if ($fields[0] =~ /\@/) {
            $name = 0;
            $email = $fields[0];
        } else {
            $name = 1;
        }
    }

    if ($fields[0] ne "" && $name) {
        $record_line = 1;

        if (defined($fam)) {
            $families->{$fam->{name}} = $fam;

            # Sigh.  Sometimes the city contains the zip.
            if (!defined($fam->{zip}) &&
                $fam->{city} =~ m/(.+)(\d\d\d\d\d)$/) {
                $fam->{city} = $1;
                $fam->{zip} = $2;
            }

            # Sanity checks
            if (!defined($fam->{city})) {
                print "WARNING: No city for $fam->{name}\n";
            }
            if (!defined($fam->{zip})) {
                print "WARNING: No city for $fam->{name}\n";
            }

            # Ok, it's all good.  Reset for the next loop.
            $fam = undef;
        }

        $fam->{name} = $fields[0];
        $fam->{street} = $fields[2];
        push(@{$fam->{phones}}, $fields[8]);
    } else {
        ++$record_line;
        if (defined($email)) {
            $fam->{email} = $email;
            $email = undef;
        }

        # Records will have at least 4 lines
        # Line 2 may have an email address
        if (2 == $record_line) {
            if ($fields[0] ne "") {
                $fam->{email} = $fields[0];
            }
            if ($fields[2] ne "") {
                # Arrgh.  Sometimes it's Louisville, prospect, or
                # masonic
                if ($fields[2] =~ /louisville/i ||
                    $fields[2] =~ /prospect/i ||
                    $fields[2] =~ /masonic/i) {
                    $fam->{city} = $fields[2];
                    $record_line = 3;
                } else {
                    $fam->{street} .= " $fields[2]";
                }
            }
        } elsif (3 == $record_line) {
            if ($fields[2] ne "") {
                $fam->{city} = $fields[2];
            }
        } elsif (4 == $record_line) {
            if ($fields[2] ne "") {
                $fam->{zip} = $fields[2];
            }
        }

        if ($fields[8] ne "") {
            push(@{$fam->{phones}}, $fields[8]);
        }
    }
}
close($fh);

# Save the last one
$families->{$fam->{name}} = $fam;
$fam = undef;

#print Dumper($families);

my $file = "output.csv";
unlink($file);
open(OUT, ">$file") || die "Can't open $file";
print OUT "name,street,\"city/state\",zip,phone1,phone2,phone3,phone4,phone5,phone6,phone7,phone8,phone9,phone10,phone11,phone12\n";
foreach my $f (sort(keys(%{$families}))) {
    my $line;
    my $fam = $families->{$f};
    $line = "\"$fam->{name}\",";
    $line .= "\"$fam->{street}\",";
    $line .= "\"$fam->{city}\",";
    $line .= "\"$fam->{zip}\",";
    print OUT $line;
    foreach my $p (@{$fam->{phones}}) {
        print OUT "$p,";
    }
    print OUT "\n";
}
close(OUT);

exit(0);
