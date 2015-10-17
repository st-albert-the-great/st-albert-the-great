package NetMonitor;

use strict;
use warnings;

use DBI;
use Exporter;
use vars qw/@EXPORT @ISA/;

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

    debug("Getting DB lock for \"$name\"\n");

    debug("Got DB lock for \"$name\"\n");
}

sub release_lock {
    my $name = shift;

    debug("Releasing DB lock for \"$name\"\n");

    debug("Released DB lock for \"$name\"\n");
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

    sql("INSERT INTO ping_results VALUES (\"$timestamp\", \"$target\", $reachable, $sent, $received, $min, $max, $avg, $stddev, 0)");

    debug("Saved ping result\n");
}

1;
