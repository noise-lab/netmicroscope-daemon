import logging
import sched, time, os
from datetime import datetime, timedelta
import asyncio, threading
"""appmonitor plugin template"""
PLUGIN_PRIORITY = 3

config = None
ta_file = None
ta_file_name = 'ta_10.out'
log = logging.getLogger(__name__)

schedule = sched.scheduler(time.time, time.sleep)

datapath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
nmapath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nm_analysis")

# lift from https://stackoverflow.com/questions/32723150/rounding-up-to-nearest-30-minutes-in-python
def ceil_dt(dt, delta):
    return dt + (datetime.min - dt) % delta

first_run = True

def run_yellow(sc):
    log.info("nm_analysis: {0} YELLOW".format(datetime.now()))

def run_red(sc):
    global ta_file
    log.info("nm_analysis: {0} RED".format(datetime.now()))
    #TODO: mutex/lock
    ta_file.close()
    ta_file = None

def main_run(sc):
    sc.run();

def run_clock(sc): 
    global first_run
    global ta_file
    global ta_file_name
    global datapath
    now = datetime.now()
    log.info("nm_analysis {0} GREEN".format(now.strftime("%Y%m%d-%H%M%S")))
    wait_minutes = 1
    if now.minute % 2 == 0:
        wait_minutes = 2
    fut = ceil_dt(now, timedelta(minutes=wait_minutes)) 
    delta = (fut - now).total_seconds()
    schedule.enter(delta, 1, run_clock, (sc,))
    if not first_run:
      schedule.enter(delta - 10, 1, run_yellow, (sc,)) 
      schedule.enter(delta / 2, 1, run_red, (sc,)) 
    else: 
      first_run = False
      return
    ta_path = os.path.join(datapath, now.strftime("%Y%m%d-%H%M%S"))
    ta_data = os.path.join(ta_path, ta_file_name)
    os.mkdir(ta_path)
    ta_file = open(ta_data, 'w')

def init(conf = None):
  global schedule
  config = None
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
    print("vidperf plugin test")
    init()

if __name__ == "__main__":
    test1()
