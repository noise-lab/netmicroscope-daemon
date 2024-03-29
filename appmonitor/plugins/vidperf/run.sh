#!/bin/bash

#SUPPORTED_APP=youtube
SUPPORTED_APP=netflix
#SUPPORTED_APP=amazon
#SUPPORTED_APP=twitch
#SUPPORTED_APP=spotify

NMPATH="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

. $NMPATH/nm_analysis/venv/bin/activate
cd $NMPATH/nm_analysis/

test_input=/home/gmartins/nm/netmicroscope-daemon/appmonitor/plugins/vidperf/data/20210405-163000/ta_10.out

#BM=c_rebufferings_us_rf_youtube_FINAL_MODEL_NMM_time10_model.pkl
#BM=c_rebufferings_us_rf_youtube_FINAL_MODEL_time10_model.pkl
#BM=c_rebufferings_us_rf_youtube_L3_L7_time10_model.pkl
#BM=c_resolution_switches_rf_all_FINAL_MODEL_NMM_time10_model.pkl
#BM=c_resolution_switches_rf_all_FINAL_MODEL_time10_model.pkl
#BM=c_resolution_switches_rf_all_L3_L7_time10_model.pkl
#BM=c_resolution_switches_rf_amazon_FINAL_MODEL_NMM_time10_model.pkl
#BM=c_resolution_switches_rf_amazon_FINAL_MODEL_time10_model.pkl
#BM=c_resolution_switches_rf_amazon_L3_L7_time10_model.pkl
#BM=c_resolution_switches_rf_netflix_FINAL_MODEL_NMM_time10_model.pkl
#BM=c_resolution_switches_rf_netflix_FINAL_MODEL_time10_model.pkl
#BM=c_resolution_switches_rf_netflix_L3_L7_time10_model.pkl
#BM=c_resolution_switches_rf_twitch_FINAL_MODEL_NMM_time10_model.pkl
#BM=c_resolution_switches_rf_twitch_FINAL_MODEL_time10_model.pkl
#BM=c_resolution_switches_rf_twitch_L3_L7_time10_model.pkl
#BM=c_resolution_switches_rf_youtube_FINAL_MODEL_NMM_time10_model.pkl
#BM=c_resolution_switches_rf_youtube_FINAL_MODEL_time10_model.pkl
#BM=c_resolution_switches_rf_youtube_L3_L7_time10_model.pkl
#RM=resolution_rf_all_FINAL_MODEL_FUZZY_time10_model.pkl
#RM=resolution_rf_all_FINAL_MODEL_NMM_NP_time10_model.pkl
#RM=resolution_rf_all_FINAL_MODEL_NMM_time10_model.pkl
#RM=resolution_rf_all_FINAL_MODEL_time10_model.pkl
RM=resolution_rf_all_L7_time10_model.pkl
#RM=resolution_rf_all_L3_L7_time10_model.pkl
#RM=resolution_rf_amazon_FINAL_MODEL_FUZZY_time10_model.pkl
#RM=resolution_rf_amazon_FINAL_MODEL_NMM_NP_time10_model.pkl
#RM=resolution_rf_amazon_FINAL_MODEL_NMM_time10_model.pkl
#RM=resolution_rf_amazon_FINAL_MODEL_time10_model.pkl
#RM=resolution_rf_amazon_L3_L7_time10_model.pkl
#RM=resolution_rf_netflix_FINAL_MODEL_FUZZY_time10_model.pkl
#RM=resolution_rf_netflix_FINAL_MODEL_NMM_NP_time10_model.pkl
#RM=resolution_rf_netflix_FINAL_MODEL_NMM_time10_model.pkl
#RM=resolution_rf_netflix_FINAL_MODEL_time10_model.pkl
#RM=resolution_rf_netflix_L3_L7_time10_model.pkl
#RM=resolution_rf_twitch_FINAL_MODEL_FUZZY_time10_model.pkl
#RM=resolution_rf_twitch_FINAL_MODEL_NMM_NP_time10_model.pkl
#RM=resolution_rf_twitch_FINAL_MODEL_NMM_time10_model.pkl
#RM=resolution_rf_twitch_FINAL_MODEL_time10_model.pkl
#RM=resolution_rf_twitch_L3_L7_time10_model.pkl
#RM=resolution_rf_youtube_FINAL_MODEL_FUZZY_time10_model.pkl
#RM=resolution_rf_youtube_FINAL_MODEL_NMM_NP_time10_model.pkl
#RM=resolution_rf_youtube_FINAL_MODEL_NMM_time10_model.pkl
#RM=resolution_rf_youtube_FINAL_MODEL_time10_model.pkl
#RM=resolution_rf_youtube_L3_L7_time10_model.pkl
#SM=startup_time_rfr_all_FINAL_MODEL_FUZZY_time10_model.pkl
#SM=startup_time_rfr_all_FINAL_MODEL_NMM_NP_time10_model.pkl
#SM=startup_time_rfr_all_FINAL_MODEL_NMM_time10_model.pkl
#SM=startup_time_rfr_all_FINAL_MODEL_NMM_time60_model.pkl
#SM=startup_time_rfr_all_FINAL_MODEL_time10_model.pkl
SM=startup_time_rfr_all_L7_time10_model.pkl
#SM=startup_time_rfr_all_FINAL_MODEL_time60_model.pkl
#SM=startup_time_rfr_all_L3_L7_time10_model.pkl
#SM=startup_time_rfr_amazon_FINAL_MODEL_FUZZY_time10_model.pkl
#SM=startup_time_rfr_amazon_FINAL_MODEL_NMM_NP_time10_model.pkl
#SM=startup_time_rfr_amazon_FINAL_MODEL_NMM_time10_model.pkl
#SM=startup_time_rfr_amazon_FINAL_MODEL_NMM_time60_model.pkl
#SM=startup_time_rfr_amazon_FINAL_MODEL_time10_model.pkl
#SM=startup_time_rfr_amazon_FINAL_MODEL_time60_model.pkl
#SM=startup_time_rfr_amazon_L3_L7_time10_model.pkl
#SM=startup_time_rfr_netflix_FINAL_MODEL_FUZZY_time10_model.pkl
#SM=startup_time_rfr_netflix_FINAL_MODEL_NMM_NP_time10_model.pkl
#SM=startup_time_rfr_netflix_FINAL_MODEL_NMM_time10_model.pkl
#SM=startup_time_rfr_netflix_FINAL_MODEL_NMM_time60_model.pkl
#SM=startup_time_rfr_netflix_FINAL_MODEL_time10_model.pkl
#SM=startup_time_rfr_netflix_FINAL_MODEL_time60_model.pkl
#SM=startup_time_rfr_netflix_L3_L7_time10_model.pkl
#SM=startup_time_rfr_twitch_FINAL_MODEL_FUZZY_time10_model.pkl
#SM=startup_time_rfr_twitch_FINAL_MODEL_NMM_NP_time10_model.pkl
#SM=startup_time_rfr_twitch_FINAL_MODEL_NMM_time10_model.pkl
#SM=startup_time_rfr_twitch_FINAL_MODEL_NMM_time60_model.pkl
#SM=startup_time_rfr_twitch_FINAL_MODEL_time10_model.pkl
#SM=startup_time_rfr_twitch_FINAL_MODEL_time60_model.pkl
#SM=startup_time_rfr_twitch_L3_L7_time10_model.pkl
#SM=startup_time_rfr_youtube_FINAL_MODEL_FUZZY_time10_model.pkl
#SM=startup_time_rfr_youtube_FINAL_MODEL_NMM_NP_time10_model.pkl
#SM=startup_time_rfr_youtube_FINAL_MODEL_NMM_time10_model.pkl
#SM=startup_time_rfr_youtube_FINAL_MODEL_NMM_time60_model.pkl
#SM=startup_time_rfr_youtube_FINAL_MODEL_time10_model.pkl
#SM=startup_time_rfr_youtube_FINAL_MODEL_time60_model.pkl
#SM=startup_time_rfr_youtube_L3_L7_time10_model.pkl

INPUT=$(readlink -f $NMPATH/$1)
if [ ! -f "${INPUT}" ]; then
  INPUT=$1
fi

#TEST DATA
#python3 -m nm_analysis.video.run -n $NMPATH/data/test_data/ta_10.out -i models/$SM  -r models/$RM  -s $SUPPORTED_APP 2>$NMPATH/nm_analysis.debug.txt
python3 -m nm_analysis.video.run -n $INPUT -i models/$SM  -r models/$RM  -s $SUPPORTED_APP --fts "L7" 2>$NMPATH/nm_analysis.debug.txt 2>$NMPATH/nm_analysis.debug.txt >$NMPATH/nm_analysis.output.txt
#python3 -m nm_analysis.video.run -n $test_input -i models/$SM -r models/$RM -s $SUPPORTED_APP --fts "L7" 2>$NMPATH/nm_analysis.debug.txt 2>$NMPATH/nm_analysis.debug.txt >$NMPATH/nm_analysis.output.txt
cat $NMPATH/nm_analysis.debug.txt >> $NMPATH/nm_analysis.debug.log.txt
cat $NMPATH/nm_analysis.output.txt >> $NMPATH/nm_analysis.output.log.txt
cat $NMPATH/nm_analysis.output.txt
