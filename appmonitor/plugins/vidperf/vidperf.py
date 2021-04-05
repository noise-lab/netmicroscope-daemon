import logging
import sched, time, os, io
from datetime import datetime, timedelta
import asyncio #TODO: mutex/lock
import threading
from subprocess import Popen, PIPE
import json
import urllib
import urllib.request
"""appmonitor plugin template"""
PLUGIN_PRIORITY = 3

config = None
ta_data = None
ta_file = None
ta_file_name = 'ta_10.out'
header = None
log = logging.getLogger(__name__)

schedule = sched.scheduler(time.time, time.sleep)

datapath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
nmapath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nm_analysis")
runpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.sh")

# lift from https://stackoverflow.com/questions/32723150/rounding-up-to-nearest-30-minutes-in-python
def ceil_dt(dt, delta):
    return dt + (datetime.min - dt) % delta

first_run = True

def run_yellow_alert(sc):
    global config
    global header
    db = config['conf_influxdb']
    log.info("nm_analysis: {0} YELLOW".format(datetime.now()))
    tnow = round(time.time())
    insertData = 'network_traffic_vidperf_startup'+\
                  ',deployment=' + config['deployment'] +\
                  ',device=' + 'demo' +\
                  ',color=' + 'yellow' +\
                  ',application=' + 'demo' +\
                  ' value=0' +\
                  ' ' + str(tnow) + '000000000' + '\n'
    if insertData != '':
      data = insertData.encode()
      req = urllib.request.Request(db['url'], data, header)
      with urllib.request.urlopen(req) as response:
        log.info('OK (Startup)' if response.getcode()==204 else 'Unexpected:'+str(response.getcode()))

def run_red_inference(sc):
    global ta_file
    global config
    global header
    #print ("run_red_inference")
    db = config['conf_influxdb']
    log.info("nm_analysis: {0} RED".format(datetime.now()))
    #TODO: mutex/lock
    ta_file.close()
    ta_file = None
    tnow = round(time.time())
    cmd = "{0} {1}".format(runpath, ta_data)
    run_output = Popen(cmd, shell=True, stdout=PIPE).stdout.read().decode('utf-8')
    #print(run_output)
    color = 'orange'
    log.info(cmd)
    log.info(run_output)

    j = None
    buf=io.StringIO(run_output)
    for l in buf.readlines():
        try:
          #print("|{0}|\n".format(l))
          j = json.loads(l)
          if 'sessions' in j.keys():
              color = 'orange'
              break
        except:
            pass
            color = 'red'

    if j is None:
        color = 'red'
    elif 'sessions' not in j.keys():
        log.error("No sessions in nm_analysis output")
        color = 'red'

    insertData = 'network_traffic_vidperf_startup'+\
                  ',deployment=' + config['deployment'] +\
                  ',device=' + 'demo' +\
                  ',color=' + color +\
                  ',application=' + 'demo' +\
                  ' value=0' +\
                  ' ' + str(tnow) + '000000000' + '\n'

    if insertData != '':
      data = insertData.encode()
      req = urllib.request.Request(db['url'], data, header)
      with urllib.request.urlopen(req) as response:
        log.info('OK (Startup)' if response.getcode()==204 else 'Unexpected:'+str(response.getcode()))

    if color == 'red':
        return

    insertData = '' 
    for i in j['sessions']:
        tnow = round(time.time())
        log.info("Startup time: {0}:{1}".format(i['startup time']["startup"], config['deployment']))
        insertData = insertData + 'network_traffic_vidperf_startup'+\
                  ',deployment=' + config['deployment'] +\
                  ',device=' + 'demo' +\
                  ',color=' + 'blue' +\
                  ',application=' + 'demo' +\
                  ' value=' + str(i['startup time']["startup"]) +\
                  ' ' + str(tnow) + '000000000' + '\n'

        t = tnow
        resolutions = i['resolutions']['predictions']
        t = t - len(resolutions)
        for k in resolutions:
          insertData = insertData + 'network_traffic_vidperf_resolution'+\
                  ',deployment=' + config['deployment'] +\
                  ',device=' + 'demo' +\
                  ',color=' + 'blue' +\
                  ',application=' + 'demo' +\
                  ' value=' + str(k) +\
                  ' ' + str(t) + '000000000' + '\n'
          t += 1

    if insertData != '':
      data = insertData.encode()
      req = urllib.request.Request(db['url'], data, header)
      with urllib.request.urlopen(req) as response:
        log.info('OK (Startup)' if response.getcode()==204 else 'Unexpected:'+str(response.getcode()))

def main_run(sc):
    sc.run();

def run_clock(sc):
    #TODO: move this to class
    global header
    global ta_data
    global first_run
    global ta_path
    global ta_file
    global ta_file_name
    global datapath
    global config
    db = config['conf_influxdb']
    now = datetime.now()
    log.info("nm_analysis {0} GREEN".format(now.strftime("%Y%m%d-%H%M%S")))
    wait_minutes = 10
    #wait_minutes = 1
    #if now.minute % 2 == 0:
    #    wait_minutes = 2
    fut = ceil_dt(now, timedelta(minutes=wait_minutes)) 
    delta = (fut - now).total_seconds()
    schedule.enter(delta, 1, run_clock, (sc,))
    if not first_run:
      schedule.enter(delta - 10, 1, run_yellow_alert, (sc,)) 
      schedule.enter(delta - 20, 1, run_red_inference, (sc,)) 
      print ("YELLOW/RED")
    else: 
      first_run = False
      print ("FIRST")
      return
    ta_path = os.path.join(datapath, now.strftime("%Y%m%d-%H%M%S"))
    ta_data = os.path.join(ta_path, ta_file_name)
    os.mkdir(ta_path)
    ta_file = open(ta_data, 'w')
    tnow = round(time.time())
    insertData = 'network_traffic_vidperf_startup'+\
                  ',deployment=' + config['deployment'] +\
                  ',device=' + 'demo' +\
                  ',color=' + 'green' +\
                  ',application=' + 'demo' +\
                  ' value=0' +\
                  ' ' + str(tnow) + '000000000' + '\n'
    if insertData != '':
      data = insertData.encode()
      req = urllib.request.Request(db['url'], data, header)
      with urllib.request.urlopen(req) as response:
        log.info('OK (Startup)' if response.getcode()==204 else 'Unexpected:'+str(response.getcode()))

def init(conf = None):
  global header
  global config 
  global schedule
  config = conf
  header = {'Authorization': 'Token ' + config['conf_influxdb']['userw'] + ":" + config['conf_influxdb']['passw']}
  if os.path.exists(nmapath):
    log.info("vidperf plugin init with {0}".format(config))
    schedule.enter(1, 1, run_clock, (schedule,))
    threading.Thread(target=main_run, args=[schedule], daemon=True).start()
  else:
      log.info("vidperf plugin: nm_analysis DISABLED")
  return PLUGIN_PRIORITY, "ok"

def preprocess(data):
  global ta_file
  #log.info("vidperf plugin preprocess")
  #log.info(data['json'])
  if os.path.exists(nmapath):
    if ta_file is not None:
      ta_file.write(data['json'].decode("utf-8")+"\n")
      os.sync()

  return data


def test1():
    global ta_data
    print("vidperf plugin test")
    init()
    ta_path = os.path.join(datapath, "20210214-093600/ta_10.out")
    cmd = "{0} {1}".format(runpath, ta_path)
    print(cmd)
    run_output = Popen(cmd, shell=True, stdout=PIPE).stdout.read().decode('utf-8')
    print("OUTPUT: {0}",format(run_output))

#if __name__ == "__main__":
#    test1()
