#!/bin/sh
# 5.5.2005 18:50 binsh
# mysql backup script
WEBAPP=~/app/valuenetwork
BASEDIR=~/app/backups/latest
TIMESTAMP=`date +%Y%m%d%H%M%S`
#TIMESTAMP=`date +%u`
DB=ocpdb

mkdir -p $BASEDIR

DUMPFILE=$BASEDIR/$DB.dump.$TIMESTAMP.sql.gz

echo "Dumping $DB to $DUMPFILE ..."
# assumes you have ~/.pgpass with the following format:
#   hostname:port:database:username:password
# and chmod 0644 ~/.pgpass
pg_dump --clean $DB | gzip > $DUMPFILE
tar czf $BASEDIR/app-valuenetwork.$TIMESTAMP.tar.gz $WEBAPP
