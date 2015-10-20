#!/usr/bin/perl

use strict;
use warnings;

BEGIN { push(@INC, "."); }

use Getopt::Long;
use NetMonitor;
use Data::Dumper;
use LWP::Simple;

my $db_filename_arg;

my $help_arg = 0;
my $debug_arg = 0;
my $verbose_arg = 0;

###############################################################################

&Getopt::Long::Configure("bundling");
my $ok = Getopt::Long::GetOptions("database=s", \$db_filename_arg,
                                  "debug!" => \$debug_arg,
                                  "verbose!" => \$verbose_arg,
                                  "help|h" => \$help_arg);
if (!$ok || $help_arg) {
    print "$0 [--database=DB_FILENAME]\n";
    exit($ok);
}

###############################################################################

# Get a LWP object for submitting to Google
my $browser = LWP::UserAgent->new;

###############################################################################

sub submit_results {
    my $submit_url = shift;
    my $fields = shift;
    my $table_name = shift;
    my $name = shift;

    # Get all the un-uploaded data so far
    my $rows = NetMonitor::sql_select("SELECT * FROM $table_name WHERE uploaded=0",
                                      "id");
    my @keys = sort { $a <=> $b } keys(%$rows);

    # Exit if there's nothing to do
    my $count = $#keys + 1;
    if ($count == 0) {
        verbose("No $name results to upload\n");
        return;
    }
    verbose("Uploading $count $name results...\n");

    foreach my $key (@keys) {
        verbose("Uploading $name ID: $key\n");
        submit_result($submit_url, $key, $fields, $rows->{$key});
    }
    verbose("Uploaded $count $name results\n");

    # Use a single UPDATE statement to indicate that all these
    # result IDs have now been uploaded
    my $sql = "UPDATE $table_name SET uploaded=1 WHERE ";
    my $first = 1;
    foreach my $key (@keys) {
        $sql .= " OR "
            if (!$first);
        $sql .= "id=$key";
        $first = 0;
    }
    NetMonitor::sql($sql);
}

# Subroutine to submit an individual result
sub submit_result {
    my $url = shift;
    my $id = shift;
    my $fields = shift;
    my $row = shift;

    debug("ROW for $id\n");
    debug(Dumper($row));

    my $values;
    foreach my $key (sort(keys(%$fields))) {
        my $google_field_name = $fields->{$key};
        $values->{$google_field_name} = $row->{$key};
    }

    debug("Submit URL: $url, key $id\n");
    my $response = $browser->post($url, $values);
    if (!$response->is_success) {
        print "LWP ERROR: " . $response->status_line . "\n";
    }
}

###############################################################################

# Submit all ping results
sub submit_ping_results {
    my $submit_url = "https://docs.google.com/forms/d/1sg5giGdFUJUet92pcxY0M5YZ9BLiyeIGDZZ8av0VBRE/formResponse";
    my $fields = {
        id => "entry.902417770",
        timestamp => "entry.663777382",
        target => "entry.1792207709",
        reachable => "entry.2088523712",
        sent => "entry.1507539175",
        received => "entry.861314488",
        min => "entry.1665894311",
        avg => "entry.530438212",
        max => "entry.657687463",
        stddev => "entry.1738735812",
    };

    submit_results($submit_url, $fields, "ping_results", "ping test");
}

###############################################################################

sub submit_bandwidth_results {
    my $submit_url = "https://docs.google.com/forms/d/19DU6EFRfha3CqhNkZhOT4x3zVuDbYkdVUeKiCCR9_Hc/formResponse";
    my $fields = {
        id => "entry.1483026486",
        timestamp => "entry.171835645",
        url => "entry.2029331697",
        reachable => "entry.1101766613",
        num_bytes => "entry.1814414357",
        seconds => "entry.274384252",
    };

    submit_results($submit_url, $fields, "download_results", "download test");
}

###############################################################################
# Main
###############################################################################

# Connect and make sure no other uploader is running right now
NetMonitor::setup($verbose_arg, $debug_arg, $db_filename_arg);
NetMonitor::connect();
NetMonitor::get_lock("upload-results");

# Ping test results
submit_ping_results();

# Bandwidth tests
submit_bandwidth_results();

# Wifi ests
#submit_wifi_results();

# Release the lock and disconnect
NetMonitor::release_lock("upload-results");
