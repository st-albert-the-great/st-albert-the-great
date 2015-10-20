#!/usr/bin/perl

use strict;
use warnings;

BEGIN { push(@INC, "."); }

use Getopt::Long;
use File::Basename;
use NetMonitor;
use Time::HiRes qw( clock_gettime CLOCK_MONOTONIC );

my $db_filename_arg;

my $help_arg = 0;
my $debug_arg = 0;
my $verbose_arg = 0;

# Hardcoded for simplicity
my $url = "http://www.open-mpi.org/~jsquyres/test/download.tar.gz";
my $expected_md5sum = "10e097bfaca8ed625781af0314797b90";
my $expected_size = 19808618;

###############################################################################

&Getopt::Long::Configure("bundling");
my $ok = Getopt::Long::GetOptions("database=s", \$db_filename_arg,
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
NetMonitor::get_lock("download-test");

my $file = basename($url);
unlink($file);

debug("Running download test from $url...\n");
my $start = clock_gettime(CLOCK_MONOTONIC);
my $rc = system("curl $url -o $file");
my $stop = clock_gettime(CLOCK_MONOTONIC);

$rc = ($rc >> 8);

my $happy = 1;

if ($rc != 0) {
    verbose("Curl of $url failed\n");
    $happy = 0;
}

my $size;
if (1 == $happy) {
    my ($dev,$ino,$mode,$nlink,$uid,$gid,$rdev,$size_file,
        $atime,$mtime,$ctime,$blksize,$blocks)
        = stat($file);
    $size = $size_file;
    if ($size != $expected_size) {
        verbose("File size is wrong (got $size, expected $expected_size)\n");
        $happy = 0;
    }
}

if (1 == $happy) {
    my $out = `md5sum $file`;
    debug("Got md5sum: $out\n");
    $out =~ m/^(\S+)\s/;
    my $md5sum = $1;
    if ($md5sum ne $expected_md5sum) {
        verbose("Md5sum of downloaded file is wrong (got $md5sum, expcted $expected_md5sum)\n");
        $happy = 0;
    }
}

if (0 == $happy) {
    debug("donwload test failed\n");
    NetMonitor::save_download_fail($url);
} else {
    my $elapsed = $stop - $start;
    my $Bps = $expected_size / $elapsed;

    debug("download test suceeded: $elapsed seconds, $Bps bytes/sec\n");
    NetMonitor::save_download_result($url, $size, $elapsed);
}
unlink($file);

NetMonitor::release_lock("download-test");
