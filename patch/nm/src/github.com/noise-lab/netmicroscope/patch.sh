#!/bin/bash
#use this command below to generate diff file
#git diff --no-prefix -u . > nm_iotlab.diff
patch -p0 -i nm_iotlab.diff 
