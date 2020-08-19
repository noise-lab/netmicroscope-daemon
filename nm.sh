#!/bin/bash

cd nm/src/github.com/noise-lab/netmicroscope/cmd/netmicroscope
./nm.sh
cd -
cd nm/netmicroscope-daemon/
. venv/bin/activate
./nmd start
