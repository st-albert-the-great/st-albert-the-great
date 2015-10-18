#!/usr/bin/env perl

use strict;
use warnings;

BEGIN { push(@INC, "."); }

use Getopt::Long;
use NetMonitor;

my $db_filename_arg = "net-monitor-data.sqlite3";

my $help_arg = 0;
my $debug_arg = 0;

###############################################################################

&Getopt::Long::Configure("bundling");
my $ok = Getopt::Long::GetOptions("database=s", \$db_filename_arg,
                                  "debug" => \$debug_arg,
                                  "help|h" => \$help_arg);
if (!$ok || $help_arg) {
    print "$0 [--sqlite3=SQLITE3_BIN] [--database=DB_FILENAME]\n";
    exit($ok);
}

###############################################################################

if (-f $db_filename_arg) {
    print "WARNING: Database already exists!
Are you sure you want to delete / re-create it (y/N)? ";
    my $answer = <STDIN>;
    chomp($answer);
    if (lc($answer) eq "y") {
        print "Ok, deleting the existing database...\n";
        unlink($db_filename_arg);
    } else {
        print "Not touching existing database\n";
        exit(1);
    }
}

###############################################################################

NetMonitor::setup(1, $debug_arg, $db_filename_arg);

NetMonitor::connect(1);

NetMonitor::sql("CREATE TABLE locks (timestamp INTEGER PRIMARY KEY, target TEXT, pid INTEGER)");

NetMonitor::sql("CREATE TABLE ping_results (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp INTEGER, target TEXT, reachable INTEGER, sent INTEGER, received INTEGER, min REAL, avg REAL, max REAL, stddev REAL, uploaded INTEGER)");

NetMonitor::sql("CREATE TABLE download_results (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp INTEGER, url TEXT, reachable INTEGER, num_bytes INTEGER, seconds REAL, uploaded INTEGER)");

NetMonitor::sql("CREATE TABLE wifi_results (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp INTEGER, ssid TEXT, joined INTEGER, seconds REAL, uploaded INTEGER)");

NetMonitor::disconnect();

exit(0);
