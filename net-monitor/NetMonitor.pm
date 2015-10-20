package NetMonitor;

use strict;
use warnings;

use DBI;
use Exporter;
use vars qw/@EXPORT @ISA/;
use Data::Dumper;

@ISA = qw/Exporter/;
@EXPORT = qw/debug verbose/;

my $db;
my $verbose_val = 1;
my $debug_val = 0;
my $db_filename = "net-monitor-data.sqlite3";

###############################################################################

sub setup {
    my $arg;

    $arg = shift;
    $verbose_val = $arg
        if (defined($arg));

    $arg = shift;
    $debug_val = $arg
        if (defined($arg));

    $arg = shift;
    $db_filename = $arg
        if (defined($arg));
}

###############################################################################

sub verbose {
    print @_
        if ($verbose_val || $debug_val);
}

sub debug {
    print @_
        if ($debug_val);
}

###############################################################################

sub connect {
    my $ok_to_not_exist = shift;

    die "Cannot find database \"$db_filename\""
        if (! -f $db_filename && defined($ok_to_not_exist) && !$ok_to_not_exist);

    debug("Opening SQLite3 database: $db_filename\n");
    $db = DBI->connect("dbi:SQLite:dbname=$db_filename","","");
    die "Could not open filename \"$db_filename\""
        if (!$db);

    debug("Successfully opened SQLite3 database: $db_filename\n");
}

sub disconnect {
    debug("Disconnecting from database...\n");
    $db->disconnect();
    debug("Disconneted from database\n");
}

###############################################################################

sub get_lock {
    my $name = shift;

    my $pid = $$;
    debug("Getting DB lock for \"$name\": pid $pid\n");

    sql("BEGIN TRANSACTION");
    my $rows = sql_select("SELECT pid FROM locks WHERE target=\"$name\"");

    # How many rows did we get back?
    my @keys = keys(%$rows);
    my $num_locks = $#keys;
    if ($num_locks >= 0) {
        # Someone else has a lock -- just exit
        verbose("Someone else has a lock -- I'll lie here, quietly, in the snow...\n");
        exit(0);
    }

    my $timestamp = time();
    my $human_timestamp = localtime($timestamp);
    sql("INSERT INTO locks (timestamp, target, pid) VALUES ($timestamp, \"$name\", $pid)");
    sql("COMMIT TRANSACTION");

    debug("Got DB lock for \"$name\": pid $pid\n");
}

sub release_lock {
    my $name = shift;

    my $pid = $$;
    debug("Releasing DB lock for \"$name\": $pid\n");

    sql("DELETE FROM locks WHERE pid=$pid");

    debug("Released DB lock for \"$name\": $pid\n");
}

###############################################################################

sub sql {
    my $sql = shift;

    debug("Running SQL: $sql\n");

    my $ret = $db->do($sql);
    if (!defined($ret) || $ret < 0) {
        print "SQL failure:
  SQL: $sql
  Error: " . $db->err . "\n";
        die "Cannot continue";
    }

    debug("Ran SQL: $sql\n");
}

sub sql_select {
    my $sql = shift;
    my @keys = @_;

    debug("Running select SQL: $sql, keys: @keys\n");

    my $ret = $db->selectall_hashref($sql, \@keys);
    if (!defined($ret)) {
        print "SQL select failure:
  SQL: $sql
  Error: " . $db->err . "\n";
        die "Cannot continue";
    }

    debug("Ran select SQL: $sql\n");

    return $ret;
}

###############################################################################

sub save_ping_result {
    my $target = shift;
    my $reachable = shift;
    my $sent = shift;
    my $received = shift;
    my $min = shift;
    my $avg = shift;
    my $max = shift;
    my $stddev = shift;

    my $timestamp = time();
    my $human_timestamp = localtime($timestamp);
    verbose("Saving ping result:\n");
    verbose("  timestamp:$human_timestamp ($timestamp)\n");
    verbose("  target:$target, reachable:$reachable, sent:$sent, received:$received\n");
    verbose("  min:$min, avg:$avg, max:$max , stddev:$stddev\n");

    sql("INSERT INTO ping_results (timestamp, target, reachable, sent, received, min, avg, max, stddev, uploaded) VALUES (\"$timestamp\", \"$target\", $reachable, $sent, $received, $min, $avg, $max, $stddev, 0)");

    debug("Saved ping result\n");
}

sub save_ping_fail {
    my $target = shift;

    NetMonitor::save_ping_result($target, 0, 0, 0, 0, 0, 0, 0);
}

###############################################################################

sub save_download_result {
    my $url = shift;
    my $size = shift;
    my $elapsed = shift;

    my $timestamp = time();
    my $human_timestamp = localtime($timestamp);
    verbose("Saving download result:\n");
    verbose("  timestamp:$human_timestamp ($timestamp)\n");
    verbose("  url:$url\n");
    verbose("  size:$size, elapsed:$elapsed\n");

    sql("INSERT INTO download_results (timestamp, url, reachable, num_bytes, seconds,uploaded) VALUES (\"$timestamp\", \"$url\", 1, $size, $elapsed, 0)");

    debug("Saved ping result\n");
}

sub save_download_fail {
    my $url = shift;

    NetMonitor::save_download_result($url, );
}

###############################################################################

1;
