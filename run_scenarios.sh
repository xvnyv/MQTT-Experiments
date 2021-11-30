#!/usr/bin/env bash


for yaml_file in *.yaml; do
    echo "## Going to run Scenario: $yaml_file"
    echo "## Running Sub-Client & Waiting for Handshake.."
    for i in {1..5}; do
        screen -S sub-screen -d -m python3 sub-client.py -f "$yaml_file"
        sleep 180
        echo "## Going to run Pub-Client"
        python3 pub-client.py -f "$yaml_file"
        echo "## Pub-Client Finished.. Waiting for a while"
        screen -S sub-screen -p 0 -X stuff $'\003'
        sleep 180
    done
done

