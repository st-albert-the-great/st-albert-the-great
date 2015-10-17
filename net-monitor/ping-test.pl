#!/usr/bin/perl

use strict;
use warnings;

BEGIN { push(@INC, "."); }

use Getopt::Long;
use NetMonitor;

my $target_arg = "google.com";
my $db_filename_arg;

my $help_arg = 0;
my $debug_arg = 0;

###############################################################################

&Getopt::Long::Configure("bundling");
my $ok = Getopt::Long::GetOptions("database=s", \$db_filename_arg,
                                  "target=s", \$target_arg,
                                  "debug" => \$debug_arg,
                                  "help|h" => \$help_arg);
if (!$ok || $help_arg) {
    print "$0 [--sqlite3=SQLITE3_BIN] [--database=DB_FILENAME] [--target=IP_OR_NAME]\n";
    exit($ok);
}

###############################################################################

NetMonitor::setup(1, $debug_arg, $db_filename_arg);

# See if anyone else is running the ping test right now
NetMonitor::connect();
NetMonitor::get_lock("ping-test");

#NetMonitor::sql("INSERT INTO mytable VALUES (1, ?)");

NetMonitor::release_lock("ping-test");
