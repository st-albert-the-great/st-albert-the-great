package NetMonitor;

use strict;
use warnings;

use DBI;

my $db;
my $verbose = 1;
my $debug = 0;
my $db_filename = "net-monitor-data.sqlite3";

sub setup {
    my $arg;

    $arg = shift;
    $verbose = $arg
        if (defined($arg));

    $arg = shift;
    $debug = $arg
        if (defined($arg));

    $arg = shift;
    $db_filename = $arg
        if (defined($arg));
}

sub verbose {
    print @_
        if ($verbose);
}

sub debug {
    print @_
        if ($debug);
}

sub connect {
    my $ok_to_not_exist = shift;

    die "Cannot find database \"$db_filename\""
        if (! -f $db_filename && defined($ok_to_not_exist) && !$ok_to_not_exist);

    debug "Opening SQLite3 database: $db_filename\n";
    $db = DBI->connect("dbi:SQLite:dbname=$db_filename","","");
    die "Could not open filename \"$db_filename\""
        if (!$db);

    debug "Successfully opened SQLite3 database: $db_filename\n";
}

sub disconnect {
    debug "Disconnecting from database...\n";
    $db->disconnect();
    debug "Disconneted from database\n";
}

sub get_lock {
    my $name = shift;

    debug "Getting DB lock for \"$name\"\n";

    debug "Got DB lock for \"$name\"\n";
}

sub release_lock {
    my $name = shift;

    debug "Releasing DB lock for \"$name\"\n";

    debug "Released DB lock for \"$name\"\n";
}

sub sql {
    my $sql = shift;

    debug "Running SQL: $sql\n";

    my $ret = $db->do($sql);
    if (0 != $ret) {
        print "SQL failure:
  SQL: $sql
  Error: $ret\n";
        die "Cannot continue";
    }

    debug "Ran SQL: $sql\n";
}

1;
