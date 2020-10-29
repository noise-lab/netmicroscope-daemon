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
import imp
import os

from dotenv import load_dotenv

class AppMonitor:
  """AppMonitor"""

  FILESTATUS = "processedfiles.pickle" #TODO: TBD
  thread_ctrl = None
  filestatus = {}
  influxdb = None 
  logger = None
  listener = None
  pluginfolder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")
  mainmodule = "module"
  plugins = []

  def printF (self, m):
    if self.logger:
      self.logger.info(m)
    else:
      print(m)

  def __init__(self, thread_ctrl, logger = None):
    load_dotenv(verbose=True)
    self.thread_ctrl = thread_ctrl
    self.influxdb = self.InfluxDB(self.printF, self.thread_ctrl)
    self.logger = logger
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
  
    for p in self.getPlugins():
       self.printF("Loading plugin " + p["name"])
       plugin = self.loadPlugin(p)
       priority, errmsg = plugin.init(self.printF, {'deployment': self.influxdb.deployment})
       if priority < 0:
         self.printF(errmsg)
         sys.exit(1)
       self.plugins.append({'plugin':plugin, 'priority':priority})
    self.plugins = sorted(self.plugins, key = lambda i: i['priority']) #,reverse=True

  def getPlugins(self):
    plugins = []
    pluginsdir = os.listdir(self.pluginfolder)
    for p in pluginsdir:
        location = os.path.join(self.pluginfolder, p)
        if not os.path.isdir(location) or not p + ".py" in os.listdir(location):
            continue
        info = imp.find_module(p, [location])
        plugins.append({"name": p, "info": info})
    return plugins

  def loadPlugin(self, plugin):
    return imp.load_module(plugin["name"], *plugin["info"])

  def pluginPreProcess(self, insertData):
    for p in self.plugins:
      insertData = p['plugin'].preprocess(insertData)
    return insertData

  class InfluxDB(object):
    host = None
    port = 0
    db = None
    userw = None
    passw = None
    deployment = None
    database = None
    thread_ctrl = None
    insert_memory = None

    #var built at runtime
    url = None
    header = None

    printFunc = None

    #insert = None #inser queue
    influxdb_queue = None

    def __init__(self, printF, thread_ctrl):
      self.influxdb_queue = queue.Queue()
      self.printFunc = printF
      self.thread_ctrl = thread_ctrl

    def printF(self, m):
      self.printFunc(m)

    def influxdb_updater_thread(self, pluginPreProcess):
      while self.thread_ctrl['continue']:
          if self.url == None:
            self.url = "https://" + self.host + ":" + self.port + "/api/v2/write?bucket=" +\
              self.database + "/rp&precision=ns"
          if self.header == None:
            self.header = {'Authorization': 'Token ' + self.userw + ":" + self.passw}
          summary = pluginPreProcess(self.influxdb_queue.get())
          if summary is None:
            continue
          if 'std' not in summary.keys():
            self.printF("WARNING: malformed summary/insert data {0}".format(summary))
            continue
          else:
            insert = summary['std']
            extend = None
            if 'ext' in summary.keys():
              if 'insert' in summary['ext'].keys():
                extend = summary['ext']['insert']
            #self.printF("EXTINFO: {}".format(summary['ext']))
          for dev in insert.keys():
            if insert[dev] is not None:
              for app in insert[dev]:
                 self.printF(app + "-" + dev + " " + str(insert[dev][app]))
          try:
            data = ''
            TsEnd = None
            TsEndMemory = None
            for dev in insert.keys():
              for app in insert[dev]:
                data = data + 'network_traffic_application_kbpsdw'+\
                  ',deployment=' + self.deployment +\
                  ',device=' + dev +\
                  ',application=' + app +\
                  ' value=' + str(insert[dev][app]['KbpsDw']) +\
                  ' ' + str(insert[dev][app]['TsEnd']) + '000000000' + '\n'
                data = data + 'network_traffic_application_kbpsup'+\
                  ',deployment=' + self.deployment +\
                  ',device=' + dev +\
                  ',application=' + app +\
                  ' value=' + str(insert[dev][app]['KbpsUp']) +\
                  ' ' + str(insert[dev][app]['TsEnd']) + '000000000' + '\n'
                if TsEnd is None:
                  TsEnd = str(insert[dev][app]['TsEnd'])
            # there's no future data point for some of the devices, better to fill in w zero
            # otherwise grafana will connect data points directly 
            if self.insert_memory is not None:              
              for dev in self.insert_memory.keys():
                for app in self.insert_memory[dev]:
                  if TsEndMemory is None:
                    TsEndMemory = self.insert_memory[dev][app]['TsEnd']
                  try:
                    insert[dev][app]['KbpsDw'] #force key error if not present
                    insert[dev][app]['KbpsUp']
                  except KeyError:
                    data = data + 'network_traffic_application_kbpsdw'+\
                      ',deployment=' + self.deployment +\
                      ',device=' + dev +\
                      ',application=' + app +\
                      ' value=0' +\
                      ' ' + TsEnd + '000000000' + '\n'
                    data = data + 'network_traffic_application_kbpsup'+\
                      ',deployment=' + self.deployment +\
                      ',device=' + dev +\
                      ',application=' + app +\
                      ' value=0' +\
                      ' ' + TsEnd + '000000000' + '\n'
              #there's no past data point for some of the devices, better to fill in w zero
              #otherwise grafana will create a "long" ramp in the ts
              for dev in insert.keys():
                for app in insert[dev]:
                  try:
                      self.insert_memory[dev][app]['KbpsDw'] #force key error if not present
                      self.insert_memory[dev][app]['KbpsUp']
                  except KeyError:
                    data = data + 'network_traffic_application_kbpsdw'+\
                      ',deployment=' + self.deployment +\
                      ',device=' + dev +\
                      ',application=' + app +\
                      ' value=0' +\
                      ' ' + TsEndMemory + '000000000' + '\n'
                    data = data + 'network_traffic_application_kbpsup'+\
                      ',deployment=' + self.deployment +\
                      ',device=' + dev +\
                      ',application=' + app +\
                      ' value=0' +\
                      ' ' + TsEndMemory + '000000000' + '\n'
            self.insert_memory = insert

            if extend is not None:
              for insertLine in extend:
                data = data + insertLine + "\n"
                #print(insertLine)
            data = data.encode()
            req = urllib.request.Request(self.url, data, self.header)
            with urllib.request.urlopen(req) as response:
               self.printF('OK' if response.getcode()==204 else 'Unexpected:'+str(response.getcode()))
          except Exception as e:
              self.printF("EXCEPTION: influxdb_updater_thread {0} {1}".format(e, dev))
          self.influxdb_queue.task_done()

  class TAHandler():
      process_tmp_ta = None
      filestatus = None
      thread_ctrl = None
      worker = None
      printFunc = None
      running = True
      filename = None
      def __init__(self, process_tmp_ta, printF, filestatus, thread_ctrl):
        self.process_tmp_ta = process_tmp_ta
        self.filestatus = filestatus
        self.printFunc = printF
        self.thread_ctrl = thread_ctrl

      def printF(self, m):
        self.printFunc(m)
      
      def fsreader(self):
        while self.thread_ctrl['continue'] and self.running:
          files=glob.glob("/tmp/tmp.ta.*")
          if len(files) > 1:
            self.printF("WARNING: multiple tmp.ta.* files found.")
          for f in files:
            try:
              if self.filestatus[f]['running']:
                self.printF("TAHandler {0} is running.".format(f))
                continue
              self.printF("TAHandler ignoring {0}.".format(f))
            except KeyError as ke:
              if self.worker is not None:
                self.filestatus[self.filename]['running'] = False
                self.filestatus[self.filename]['tail'].kill()
                self.worker.join()
                self.printF("TAHandler terminating {0}:{1}.".format(f, ke))
              else:
                self.printF("TAHandler initializing {0}:{1}.".format(f, ke))
              self.worker = threading.Thread(target=self.process_tmp_ta, args=(f,))
              self.filestatus[f] = {}
              self.filestatus[f]['thread'] = self.worker
              self.filename = f
              self.worker.start()
            except Exception as e:
              self.printF("ERROR: {0}".format(e))
          time.sleep(10)
  
      def start(self):
        self.thread = threading.Thread(target=self.fsreader)
        self.thread.start()
      
      def stop(self):
        self.running = False

      def join(self):
        self.thread.join()


  def process_tmp_ta(self, filename=""):
      if filename == "":
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
              summary = {'std' : {}, 'ext': {}} #std == standard, ext == extended (rDNS. GeoIP, etc)
              if 'TrafficData' not in j.keys():
                continue
              if 'Data' not in j['TrafficData'].keys():
                continue
              if j['TrafficData']['Data'] is None:
                continue
              for d in j['TrafficData']['Data']:
                device = 'Device'
                if 'HwAddr' in d:
                    device = 'HwAddr'
                if d[device] not in summary['std']:
                  summary['std'][d[device]] = {}
                  summary['ext'][d[device]] = {}
                if d['Meta'] not in summary['std'][d[device]]:
                    summary['std'][d[device]][d['Meta']] = { 'KbpsDw': 0.0, 'KbpsUp': 0.0, 'TsEnd': 0 }
                    summary['ext'][d[device]][d['Meta']] = { 'Domain': None, 'SIP': None }
  
                summary['std'][d[device]][d['Meta']]['TsEnd'] = j['Info']['TsEnd']
                summary['std'][d[device]][d['Meta']]['KbpsDw'] =\
                    summary['std'][d[device]][d['Meta']]['KbpsDw'] + d['KbpsDw']
                summary['std'][d[device]][d['Meta']]['KbpsUp'] =\
                    summary['std'][d[device]][d['Meta']]['KbpsUp'] + d['KbpsUp']
                summary['std'][d[device]][d['Meta']]['Domain'] = d['Domain']
                summary['std'][d[device]][d['Meta']]['SIP'] = d['SIP']
                #self.printF("DOMAIN:" + d['Domain'] + "," + d['SIP'])
              self.influxdb.influxdb_queue.put(summary)

              #for dev in summary.keys():
              #  for app in summary[dev]:
              #    self.printF(app + "-" + dev + " " + str(summary[dev][app]))
          except sh.ErrorReturnCode_1: # as e:
              self.printF("process_tmp_ta: tail terminated {0}, (permission denied ?) ".format(filename))
              break
          except sh.SignalException_SIGKILL as e:
              self.printF("process_tmp_ta: tail terminated {0}".format(filename))
              break
          except Exception as e:
              exc_type, _, exc_tb = sys.exc_info()
              fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
              self.printF("process_tmp_ta: {0} {1} {2}".format(exc_type, fname, exc_tb.tb_lineno))

        self.printF('process_tmp_ta: exiting ' + filename)
        #with open(FILESTATUS, 'wb') as handle:
        #  pickle.dump(filestatus, handle, protocol=pickle.HIGHEST_PROTOCOL)
        return True

  def run(self):
    self.listener = self.TAHandler(self.process_tmp_ta, self.printF, self.filestatus, self.thread_ctrl)
    self.listener.start()
    if os.getenv('INFLUXDB_ENABLE') == 'true':
       self.printF("INFO: running thread.")
       threading.Thread(target=self.influxdb.influxdb_updater_thread, 
          args=(self.pluginPreProcess,),
          daemon=True).start()
       self.printF("INFO: Done")
    #try:
    #  with open(self.FILESTATUS, 'rb') as handle:
    #     filestatus = pickle.load(handle)
    #except FileNotFoundError as e:
    #  pass 

    #self.process_tmp_ta()
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
    self.printF("MAIN: listener join")
    self.listener.join()
    self.influxdb.influxdb_queue.join()

  def stop(self):
    for k in self.filestatus.keys():
      try: 
          self.filestatus[k]['tail'].kill()
      except ProcessLookupError: # as ple:
          pass
    self.listener.stop()

#if __name__ == "__main__":
#  app = AppMonitor()
#  app.run()
