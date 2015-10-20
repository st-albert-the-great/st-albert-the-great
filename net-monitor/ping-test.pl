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
my $verbose_arg = 0;

###############################################################################

&Getopt::Long::Configure("bundling");
my $ok = Getopt::Long::GetOptions("database=s", \$db_filename_arg,
                                  "target=s", \$target_arg,
                                  "debug!" => \$debug_arg,
                                  "verbose!" => \$verbose_arg,
                                  "help|h" => \$help_arg);
if (!$ok || $help_arg) {
    print "$0 [--database=DB_FILENAME] [--target=IP_OR_NAME]\n";
    exit($ok);
}

###############################################################################

NetMonitor::setup($verbose_arg, $debug_arg, $db_filename_arg);

# See if anyone else is running the test right now
NetMonitor::connect();
NetMonitor::get_lock("ping-test");

my $file = "/tmp/ping-test.tmp";
unlink($file);

debug("Running ping test to $target_arg...\n");
my $rc = system("ping -c 3 $target_arg > $file");
$rc = ($rc >> 8);
if (0 != $rc) {
    debug("ping test failed: exit result: $rc\n");
    NetMonitor::save_ping_fail($target_arg);
} else {
    debug("ping test suceeded -- reading results...\n");
    if (open(FILE, $file)) {
        my $contents;

        $contents .= $_
            while (<FILE>);
        close(FILE);

        debug "Got ping test results:\n$contents";

        $contents =~ m/^(\d+) packets transmitted, (\d+) received,/m;
        my $sent = $1;
        my $received = $2;

        $contents =~ m@min/avg/max/mdev = ([\d\.]+?)/([\d\.]+?)/([\d\.]+?)/([\d\.]+?) ms@;
        my $min = $1;
        my $avg = $2;
        my $max = $3;
        my $stddev = $4;

        NetMonitor::save_ping_result($target_arg, 1, $sent, $received,
                                     $min, $avg, $max, $stddev);
    } else {
        debug("ping test unable to read results!\n");
    }
}
unlink($file);

NetMonitor::release_lock("ping-test");
