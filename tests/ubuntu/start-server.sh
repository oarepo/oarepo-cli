#!/bin/bash

set -e

PID_FILE='/tmp/invenio-server.pid'
LOG_FILE='/tmp/invenio-server.log'

if [ -f $PID_FILE ] ; then
    echo "Server already running or not stopped correctly"
    exit 1
fi

cd repo

echo "----- Starting server at $(date)" >$LOG_FILE
./nrp-cli run &>>$LOG_FILE &

pid=$!

echo "$pid" >$PID_FILE

sleep 10

if kill -0 $pid 2>/dev/null ; then
  echo "Invenio server running"
else
  echo "Invenio server down after start up"
  exit 1
fi