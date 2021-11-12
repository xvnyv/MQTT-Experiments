#!/usr/bin/env bash

clientType=$1
if [[ $clientType == "pub" || $clientType == "sub" ]]; then
    shift 1
    echo "Running: python -u $clientType-client.py $@"
    python -u $clientType-client.py $@
else
    echo "Please specify 'pub' or 'sub' to run respective clients"
fi