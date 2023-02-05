#!/bin/bash

set -e

response=$(curl -k -I https://localhost:5000/)

# Extract the HTTP status code from the response
status=$(echo "$response" | head -n 1 | cut -d ' ' -f 2)

if [ "$status" == "404" ] || [ "$status" == "200" ] ; then
    echo "Homepage found"
else
    echo "No homepage, got response ${response}"
    exit 1
fi