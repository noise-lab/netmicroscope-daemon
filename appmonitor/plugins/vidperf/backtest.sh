#!/bin/bash 

datatest=/home/gmartins/nm/netmicroscope-daemon/appmonitor/plugins/vidperf/datatest/

testset_yt="
$datatest/youtube/20210221-004000/ta_10.out
$datatest/youtube/20210221-005000/ta_10.out
$datatest/youtube/20210221-010000/ta_10.out
$datatest/youtube/20210221-011000/ta_10.out
$datatest/youtube/20210221-012000/ta_10.out
"

testset_nf="
$datatest/netflix/20210220-232000/ta_10.out
$datatest/netflix/20210220-233000/ta_10.out
$datatest/netflix/20210220-235000/ta_10.out
$datatest/netflix/20210221-000000/ta_10.out
$datatest/netflix/20210221-001000/ta_10.out
$datatest/netflix/20210221-002000/ta_10.out
$datatest/netflix/20210221-003000/ta_10.out
"

#home/gmartins/nm/netmicroscope-daemon/appmonitor/plugins/vidperf/data/test_data/ta_10.out"

for t in $testset_yt; do
  python3 -m nm_analysis.video.run -n $t -i models/startup_time_rfr_all_L7_time10_model.pkl  -r models/resolution_rf_all_L7_time10_model.pkl  -s youtube --fts L7
done

for t in $testset_nf; do
  python3 -m nm_analysis.video.run -n $t -i models/startup_time_rfr_all_L7_time10_model.pkl  -r models/resolution_rf_all_L7_time10_model.pkl  -s netflix --fts L7
done
