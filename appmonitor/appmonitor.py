#!/usr/bin/python
import os, sys
import sh
import time
import glob
import json
import pickle
import traceback
import threading
import queue
import urllib
import urllib.parse
import urllib.request

from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class AppMonitor:
  """AppMonitor"""

  FILESTATUS = "processedfiles.pickle" #TODO: TBD
  thread_ctrl = None
  filestatus = {}
  influxdb = None 
  event_handler = None
  observer = None
  logger = None

  def __init__(self, thread_ctrl, logger = None):
    load_dotenv(verbose=True)
    self.thread_ctrl = thread_ctrl
    self.influxdb = self.InfluxDB(self.printF, self.thread_ctrl)
    self.event_handler = self.TMPHandler(self.process_tmp_ta, 
      self.filestatus,
      self.printF)
    self.observer = Observer()
    self.logger = logger

  def printF (self, m):
    if self.logger:
      self.logger.info(m)
    else:
      print(m)

  class InfluxDB(object):
    host = None
    port = 0
    db = None
    userw = None
    passw = None
    deployment = None
    database = None
    thread_ctrl = None 

    #var built at runtime
    url = None
    header = None

    printF = None

    #insert = None #inser queue
    influxdb_queue = None

    def __init__(self, printF, thread_ctrl):
      self.influxdb_queue = queue.Queue()
      self.printF = printF
      self.thread_ctrl = thread_ctrl
    
    def printF(self, m):
      self.printF(m)

    def influxdb_updater_thread(self):
      while self.thread_ctrl['continue']:
          if self.url == None:
            self.url = "https://" + self.host + ":" + self.port + "/api/v2/write?bucket=" +\
              self.database + "/rp&precision=ns"
          if self.header == None:
            self.header = {'Authorization': 'Token ' + self.userw + ":" + self.passw}
          insert = self.influxdb_queue.get()
          #TODO: bundle up insert queries
          #self.printF(f'influxdb queue working on {insert}')
          data = ''
          for dev in insert.keys():
            for app in insert[dev]:
              data = data + 'network_traffic_application_kbpsdw'+\
                  ',deployment=' + self.deployment +\
                  ',device=' + dev +\
                  ',application=' + app +\
                  ' value=' + str(insert[dev][app]['KbpsDw']) +\
                  ' ' + str(insert[dev][app]['TsEnd']) + '000000000' + '\n'
          for dev in insert.keys():
            for app in insert[dev]:
              data = data + 'network_traffic_application_kbpsup'+\
                  ',deployment=' + self.deployment +\
                  ',device=' + dev +\
                  ',application=' + app +\
                  ' value=' + str(insert[dev][app]['KbpsUp']) +\
                  ' ' + str(insert[dev][app]['TsEnd']) + '000000000' + '\n'
          data = data.encode()
          req = urllib.request.Request(self.url, data, self.header)
          with urllib.request.urlopen(req) as response:
            self.printF('OK' if response.getcode()==204 else 'Unexpected:'+str(response.getcode()))

          self.influxdb_queue.task_done()

  class TMPHandler(FileSystemEventHandler):
      process_tmp_ta = None
      filestatus = None
      printF = None
      def __init__(self, process_tmp_ta, filestatus, printF):
        self.process_tmp_ta = process_tmp_ta
        self.filestatus = filestatus
        self.printF = printF

      def printF(self, m):
        self.printF(m)

      def on_modified(self, event):
        #self.printF(f'INFO: event type: {event.event_type} path: {event.src_path}')
        if event.src_path.startswith("/tmp/tmp.ta."):
          if not os.path.isfile(event.src_path):
            #file moved
            self.printF("INFO: disabling tail " + event.src_path)
            self.filestatus[event.src_path]['running'] = False
            try:
              tail = self.filestatus[event.src_path]['tail']
              tail.kill()
            except Exception as e:
              self.printF("TMPHandler: {0}".format(e))
          else:
            self.printF("WARNING, ramaining data in "+ event.src_path)
            sys.exit(0)
        #else:
        #  self.printF("does not match: "+event.src_path)
  
      def on_created(self, event):
        if event.src_path.startswith("/tmp/tmp.ta."):
            self.printF("threading {0}...".format(event.src_path))
            t = threading.Thread(target=self.process_tmp_ta, args=(event.src_path,))
            self.filestatus[event.src_path] = {}
            self.filestatus[event.src_path]['thread'] = t
            t.start()

      #def on_deleted(self, event):
      #   self.printF(f"INFO: {event.src_path} deleted")

      def on_moved(self, event):
        self.printF("moved {0} to {1}".format(event.src_path, event.dest_path))
        self.filestatus[event.src_path]['running'] = False

  def process_tmp_ta(self, filename=""):
      if filename == "":
        files=glob.glob("/tmp/tmp.ta.*")
        if len(files) > 1:
          for f in files:
            if f not in self.filestatus.keys():
                self.printF("WARNING: multiple tmp.ta.* files found.")
                t = threading.Thread(target=self.process_tmp_ta, args=(f,))
                self.filestatus[f] = {}
                self.filestatus[f]['thread'] = t
                t.start()
        elif len(files) > 0:
          t = threading.Thread(target=self.process_tmp_ta, args=(files[0],))
          self.filestatus[files[0]] = {}
          self.filestatus[files[0]]['thread'] = t
          t.start()
        else:
          self.printF("INFO: No files to process now.")  
      else:
      
        if not os.path.isfile(filename):
          self.printF("ERROR: filename "+filename+" is not a file.")
          return False
        else:
          self.printF("Processing: " + filename)
          self.filestatus[filename]['running'] = True
          self.filestatus[filename]['tail'] = sh.tail("-F", filename, _iter=True, _bg_exc=False)
  
        while self.filestatus[filename]['running'] and self.thread_ctrl['continue']:
          try:
              line = self.filestatus[filename]['tail'].next()
              j=json.loads(line)
              summary = {}
              if 'TrafficData' not in j.keys():
                continue
              if 'Data' not in j['TrafficData'].keys():
                continue
              if j['TrafficData']['Data'] is None:
                continue
              for d in j['TrafficData']['Data']:
                #self.printF(d['Device']+' '+d['Meta']+' KbpsDw:'+str(d['KbpsDw']))
                #self.printF(d['Device']+' '+d['Meta']+' KbpsUp:'+str(d['KbpsUp']))
                if d['Device'] not in summary:
                  summary[d['Device']] = {}
                if d['Meta'] not in summary[d['Device']]:
                    summary[d['Device']][d['Meta']] = { 'KbpsDw': 0.0, 'KbpsUp': 0.0, 'TsEnd': 0 }
  
                summary[d['Device']][d['Meta']]['TsEnd'] = j['Info']['TsEnd']
                summary[d['Device']][d['Meta']]['KbpsDw'] =\
                    summary[d['Device']][d['Meta']]['KbpsDw'] + d['KbpsDw']
                summary[d['Device']][d['Meta']]['KbpsUp'] =\
                    summary[d['Device']][d['Meta']]['KbpsUp'] + d['KbpsUp']
              self.influxdb.influxdb_queue.put(summary)

              for dev in summary.keys():
                for app in summary[dev]:
                  self.printF(app + "-" + dev + " " + str(summary[dev][app]))

          except sh.SignalException_SIGKILL as e:
              self.printF("process_tmp_ta: tail terminated " + filename)
              break
          except Exception as e:
              self.printF("TMPHandler: {0}".format(e))

        self.printF('process_tmp_ta: exiting ' + filename)
        #with open(FILESTATUS, 'wb') as handle:
        #  pickle.dump(filestatus, handle, protocol=pickle.HIGHEST_PROTOCOL)
        return True

  def run(self):
    self.observer.schedule(self.event_handler, path='/tmp/', recursive=False)
    self.observer.start()
    if os.getenv('INFLUXDB_ENABLE') == 'true':
       self.printF("INFO: influxdb enabled, checking environment variables...")
       if os.getenv('INFLUXDB_HOST') is not None:
         self.influxdb.host = os.getenv('INFLUXDB_HOST')
       else:
         self.printF("ERROR: INFLUXDB_HOST not set, Exiting...")
         sys.exit(1)
       if os.getenv('INFLUXDB_PORT') != 0:
         self.influxdb.port = os.getenv('INFLUXDB_PORT')
       else:
         self.printF("ERROR: INFLUXDB_PORT not set, Exiting...")
         sys.exit(1)
       if os.getenv('INFLUXDB_WRITE_USER') is not None:
         self.influxdb.userw = os.getenv('INFLUXDB_WRITE_USER')
       else:
         self.printF("ERROR: INFLUXDB_WRITE_USER not set, Exiting...")
         sys.exit(1)
       if os.getenv('INFLUXDB_WRITE_USER_PASSWORD') is not None:
         self.influxdb.passw = os.getenv('INFLUXDB_WRITE_USER_PASSWORD')
       else:
         self.printF("ERROR: INFLUXDB_WRITE_USER_PASSWORD not set, Exiting...")
         sys.exit(1)
       if os.getenv('INFLUXDB_DEPLOYMENT') is not None:
         self.influxdb.deployment = os.getenv('INFLUXDB_DEPLOYMENT')
       else:
         self.printF("ERROR: INFLUXDB_DEPLOYMENT not set, Exiting...")
         sys.exit(1)
       if os.getenv('INFLUXDB_DB') is not None:
         self.influxdb.database = os.getenv('INFLUXDB_DB')
       else:
         self.printF("ERROR: INFLUXDB_DB not set, Exiting...")
         sys.exit(1)

       threading.Thread(target=self.influxdb.influxdb_updater_thread, daemon=True).start()
       self.printF("INFO: Done")
    #try:
    #  with open(self.FILESTATUS, 'rb') as handle:
    #     filestatus = pickle.load(handle)
    #except FileNotFoundError as e:
    #  pass 

    self.process_tmp_ta()
    self.printF("MAIN: joining threads")

    try:
        while self.thread_ctrl['continue']:
          time.sleep(1)
          try:
            for k in self.filestatus.keys():
              if 'running' in self.filestatus[k].keys():
                if self.filestatus[k]['running']:
                  if 'thread' in self.filestatus[k].keys():
                    self.printF("MAIN: waiting for " + k)
                    self.filestatus[k]['thread'].join()
                    self.filestatus[k]['running'] = False
                    self.printF("MAIN: " +k + " joined")
          except RuntimeError as re:
            self.printF("WARNING: " + str(re))
            pass 
    except KeyboardInterrupt:
      self.stop()
    self.printF("MAIN: observer join")
    self.observer.join()
    self.influxdb.influxdb_queue.join()

  def stop(self):
    for k in self.filestatus.keys():
      try: 
          self.filestatus[k]['tail'].kill()
      except ProcessLookupError: # as ple:
          pass
    self.observer.stop()

#if __name__ == "__main__":
#  app = AppMonitor()
#  app.run()
