#!/bin/bash

PID_FILE='/tmp/invenio-server.pid'

killall invenio
sleep 10
killall -9 invenio

rm -rf $PID_FILE