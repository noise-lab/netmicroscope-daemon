#!/usr/bin/python
import os, sys
import sh
import pika #aiopika
import ssl
import certifi
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
import logging

from dotenv import load_dotenv

log = logging.getLogger(__name__)

def f(s):
  if s is None:
      return ''
  else:
      return str(s).replace(',', '\,').replace(' ', '\ ')

class AppMonitor:
  """AppMonitor"""

  FILESTATUS = "processedfiles.pickle" #TODO: TBD
  thread_ctrl = None
  iostatus = {}
  influxdb = None
  rabbitmq = None
  listener = None
  pluginfolder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")
  mainmodule = "module"
  plugins = []
  mode = None

  def initInfluxdb(self):
    if os.getenv('INFLUXDB_ENABLE') == 'true':
      log.info("INFO: influxdb enabled, checking environment variables...")
      if os.getenv('INFLUXDB_HOST') is not None:
        self.influxdb.host = os.getenv('INFLUXDB_HOST')
      else:
        log.error("ERROR: INFLUXDB_HOST not set, Exiting...")
        sys.exit(1)
      if os.getenv('INFLUXDB_PORT') != 0:
        self.influxdb.port = os.getenv('INFLUXDB_PORT')
      else:
        log.error("ERROR: INFLUXDB_PORT not set, Exiting...")
        sys.exit(1)
      if os.getenv('INFLUXDB_WRITE_USER') is not None:
        self.influxdb.userw = os.getenv('INFLUXDB_WRITE_USER')
      else:
        log.error("ERROR: INFLUXDB_WRITE_USER not set, Exiting...")
        sys.exit(1)
      if os.getenv('INFLUXDB_WRITE_USER_PASSWORD') is not None:
        self.influxdb.passw = os.getenv('INFLUXDB_WRITE_USER_PASSWORD')
      else:
        log.error("ERROR: INFLUXDB_WRITE_USER_PASSWORD not set, Exiting...")
        sys.exit(1)
      if os.getenv('INFLUXDB_DEPLOYMENT') is not None:
        self.influxdb.deployment = os.getenv('INFLUXDB_DEPLOYMENT')
      else:
        log.error("ERROR: INFLUXDB_DEPLOYMENT not set, Exiting...")
        sys.exit(1)
      if os.getenv('INFLUXDB_DB') is not None:
        self.influxdb.database = os.getenv('INFLUXDB_DB')
      else:
        log.error("ERROR: INFLUXDB_DB not set, Exiting...")
        sys.exit(1)

  def initRabbitMQ(self):
      if os.getenv('RABBITMQ_SSL_USER') is not None:
        self.rabbitmq.user = os.getenv('RABBITMQ_SSL_USER')
      else:
        log.error("ERROR: RABBITMQ_SSL_USER not set, Exiting...")
        sys.exit(1)
      if os.getenv('RABBITMQ_SSL_PASS') is not None:
        self.rabbitmq.password = os.getenv('RABBITMQ_SSL_PASS')
      else:
        log.error("ERROR: RABBITMQ_SSL_PASS not set, Exiting...")
        sys.exit(1)
      if os.getenv('RABBITMQ_SSL_HOST') is not None:
        self.rabbitmq.host = os.getenv('RABBITMQ_SSL_HOST')
      else:
        log.error("ERROR: RABBITMQ_SSL_HOST not set, Exiting...")
        sys.exit(1)
      if os.getenv('RABBITMQ_SSL_PORT') is not None:
        self.rabbitmq.port = os.getenv('RABBITMQ_SSL_PORT')
      else:
        log.error("ERROR: RABBITMQ_SSL_PORT not set, Exiting...")
        sys.exit(1)
      if os.getenv('RABBITMQ_SSL_CERTFILE') is not None:
        self.rabbitmq.cert = os.getenv('RABBITMQ_SSL_CERTFILE')
      else:
        log.error("ERROR: RABBITMQ_SSL_CERTFILE not set, Exiting...")
        sys.exit(1)
      if os.getenv('RABBITMQ_SSL_PKEYFILE') is not None:
        self.rabbitmq.keyf = os.getenv('RABBITMQ_SSL_PKEYFILE')
      else:
        log.error("ERROR: RABBITMQ_SSL_PKEYFILE not set, Exiting...")
        sys.exit(1)
      if os.getenv('RABBITMQ_SSL_CERTPASS') is not None:
        self.rabbitmq.certpass = os.getenv('RABBITMQ_SSL_CERTPASS')
      else:
        log.error("ERROR: RABBITMQ_SSL_CERTPASS not set, Exiting...")
        sys.exit(1)
      if os.getenv('RABBITMQ_SSL_TOPIC') is not None:
        self.rabbitmq.topic = os.getenv('RABBITMQ_SSL_TOPIC')
      else:
        log.error("ERROR: RABBITMQ_SSL_TOPIC not set, Exiting...")
        sys.exit(1)

  def __init__(self, thread_ctrl):
    load_dotenv(verbose=True)
    self.thread_ctrl = thread_ctrl
    log.info("reading MODE: [{0}]".format(os.getenv('NMD_MODE')))
    if os.getenv('NMD_MODE') == 'consumer' or os.getenv('NMD_MODE') == 'standalone':
      self.influxdb = self.InfluxDB(self.thread_ctrl)
      self.initInfluxdb()
      if os.getenv('NMD_MODE') == 'consumer':
        self.rabbitmq = self.RabbitMQ(self.thread_ctrl)
        self.initRabbitMQ()
        self.mode = 'c' # consumer
      else:
        self.mode = 's' # standalone
    else: 
      self.mode = 'p' # producer
      self.rabbitmq = self.RabbitMQ(self.thread_ctrl)
      self.initRabbitMQ()

    for p in self.getPlugins():
      log.info("Loading plugin " + p["name"])
      plugin = self.loadPlugin(p)
      priority, errmsg = plugin.init({'deployment': self.influxdb.deployment})
      if priority < 0:
        log.info(errmsg)
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

  class RabbitMQ(object):
    host = None
    port = 0
    user = None
    password = None
    cert = None
    keyf = None
    certpass = None
    topic = None
    def __init__(self,thread_ctrl):
      self.thread_ctrl = thread_ctrl

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

    #insert = None #inser queue
    influxdb_queue = None

    def __init__(self,thread_ctrl):
      self.influxdb_queue = queue.Queue()
      self.thread_ctrl = thread_ctrl

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
            log.warning("WARNING: malformed summary/insert data {0}".format(summary))
            continue
          else:
            insert = summary['std']
            extend = None
            if 'ext' in summary.keys():
              if 'insert' in summary['ext'].keys():
                extend = summary['ext']['insert']
            #log.info("EXTINFO: {}".format(summary['ext']))
          for dev in insert.keys():
            if insert[dev] is not None:
              for app in insert[dev]:
                 log.info(app + "-" + dev + " " + str(insert[dev][app]))
          try:
            data = ''
            TsEnd = None
            TsEndMemory = None
            for dev in insert.keys():
              for app in insert[dev]:
                #if insert[dev][app]['KbpsDw'] == 0.0 and\
                #  insert[dev][app]['KbpsUp'] == 0.0:
                #      continue

                data = data + 'network_traffic_application_kbpsdw'+\
                  ',deployment=' + self.deployment +\
                  ',device=' + dev +\
                  ',application=' + f(app) +\
                  ' value=' + str(insert[dev][app]['KbpsDw']) +\
                  ' ' + str(insert[dev][app]['TsEnd']) + '000000000' + '\n'
                data = data + 'network_traffic_application_kbpsup'+\
                  ',deployment=' + self.deployment +\
                  ',device=' + dev +\
                  ',application=' + f(app) +\
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
                    TsEndMemory = str(self.insert_memory[dev][app]['TsEnd'])
                  try:
                    #if float(insert[dev][app]['KbpsDw']) == 0.0 and\
                    #   float(insert[dev][app]['KbpsUp']) == 0.0
                            #force key error if not present
                    insert[dev][app]['KbpsDw']
                    insert[dev][app]['KbpsUp']
                  except KeyError:
                    data = data + 'network_traffic_application_kbpsdw'+\
                      ',deployment=' + self.deployment +\
                      ',device=' + dev +\
                      ',application=' + f(app) +\
                      ' value=0' +\
                      ' ' + TsEnd + '000000000' + '\n'
                    data = data + 'network_traffic_application_kbpsup'+\
                      ',deployment=' + self.deployment +\
                      ',device=' + dev +\
                      ',application=' + f(app) +\
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
                      ',application=' + f(app) +\
                      ' value=0' +\
                      ' ' + TsEndMemory + '000000000' + '\n'
                    data = data + 'network_traffic_application_kbpsup'+\
                      ',deployment=' + self.deployment +\
                      ',device=' + dev +\
                      ',application=' + f(app) +\
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
               log.info('OK' if response.getcode()==204 else 'Unexpected:'+str(response.getcode()))
          except Exception as e:
              exc_type, _, exc_tb = sys.exc_info()
              fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
              log.error("EXCEPTION: influxdb_updater_thread: {0} {1} {2} (dev:{3}) {4} {5}"\
                      .format(exc_type, fname, exc_tb.tb_lineno, dev, e, e.read().decode("utf8", 'ignore')))

          self.influxdb_queue.task_done()
  
  ##
  # "fs" mode, handles of /tmp/tmp.ta.* file changes via tail
  # "mq" mode, handles consumer message receive events
  class TAHandler(): 
      process_data_from_source = None
      iostatus = None
      thread_ctrl = None
      worker = None
      printFunc = None
      running = True
      filename = None
      rabbitmq = None
      mode = None
      def __init__(self, process_data_from_source, iostatus, mode, thread_ctrl, rabbitmq=None, influxdb=None):
        self.process_data_from_source = process_data_from_source
        self.iostatus = iostatus
        self.thread_ctrl = thread_ctrl
        self.mode = mode
        self.rabbitmq=rabbitmq
        self.influxdb=influxdb

      def mqreader(self):
        connection = None
        while self.thread_ctrl['continue'] and self.running:
          if self.worker is None:
            credentials = pika.PlainCredentials(self.rabbitmq.user, self.rabbitmq.password)
            context = ssl.create_default_context(cafile=certifi.where());
            basepath = os.path.join(os.path.dirname(__file__), "../")
            certfile = os.path.join(basepath, self.rabbitmq.cert)
            keyfile = os.path.join(basepath, self.rabbitmq.keyf)
            log.info("RabbitMQ SSL using {0} {1} from {2} to {3}:{4}".format(self.rabbitmq.cert, self.rabbitmq.keyf,\
              basepath, self.rabbitmq.host, self.rabbitmq.port))
            context.load_cert_chain(certfile, keyfile, self.rabbitmq.certpass)

            ssl_options = pika.SSLOptions(context, self.rabbitmq.host)
            try:
              connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.rabbitmq.host,
                port=int(self.rabbitmq.port),
                ssl_options = ssl_options,
                virtual_host='/',
                credentials=credentials))
            except Exception as e:
              exc_type, _, exc_tb = sys.exc_info()
              fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
              log.error("rabbitmq error: ({0}) {1} {2} {3}".format(str(e), exc_type, fname, exc_tb.tb_lineno))
              traceback.print_exc()
              sys.exit(1)
            channel = connection.channel()
            channel.queue_declare(queue=self.rabbitmq.topic)
            def callback(ch, method, properties, line):
              try:
                j=json.loads(line)
              except Exception as e:
                log.error("unrecognized message: {0}".format(line))
                log.error("Exception: {0}".format(e))
                return
              summary=get_summary_from_json(j)
              if summary is not None:
                self.influxdb.influxdb_queue.put(summary)
              else:
                log.warning("can't get summary from {0}".format(line))
            channel.basic_consume(queue=self.rabbitmq.topic, on_message_callback=callback, auto_ack=True)

            self.worker = threading.Thread(target=self.process_data_from_source, args=(self.rabbitmq.topic, channel,))
            self.iostatus[self.rabbitmq.topic] = {}
            self.iostatus[self.rabbitmq.topic]['thread'] = self.worker
            self.iostatus[self.rabbitmq.topic]['channel'] = channel
            self.worker.start()
          time.sleep(1)

        channel.stop_consuming()
        #connection.close()
        #channel.cancel()
        #channel.close()

      def fsreader(self):
        while self.thread_ctrl['continue'] and self.running:
          files=glob.glob("/tmp/tmp.ta.*")
          if len(files) > 1:
            log.warning("WARNING: multiple tmp.ta.* files found.")
          for f in files:
            try:
              if self.iostatus[f]['running']:
                log.info("TAHandler {0} is running.".format(f))
                continue
              log.info("TAHandler ignoring {0}.".format(f))
            except KeyError as ke:
              if self.worker is not None:
                self.iostatus[self.filename]['running'] = False
                self.iostatus[self.filename]['tail'].kill()
                self.worker.join()
                log.info("TAHandler terminating {0}:{1}.".format(f, ke))
              else:
                log.info("TAHandler initializing {0}:{1}.".format(f, ke))
              self.worker = threading.Thread(target=self.process_data_from_source, args=(f,))
              self.iostatus[f] = {}
              self.iostatus[f]['thread'] = self.worker
              self.filename = f
              self.worker.start()
            except Exception as e:
              log.error("ERROR: {0}".format(e))
          time.sleep(10)
  
      def start(self):
        if self.mode == 's' or self.mode == 'p': # standalone or producer
          self.thread = threading.Thread(target=self.fsreader) # file system (/tmp/tmp.ta.*)
        elif self.mode == 'c': # consumer
          self.thread = threading.Thread(target=self.mqreader) # rabbitmq receive
        else:
          log.error("INVALID MODE: {0}".format(self.mode))
          print("INVALID MODE: {0}".format(self.mode))
          sys.exit(1)
          
        self.thread.start()
      
      def stop(self):
        self.running = False

      def join(self):
        self.thread.join()


  def process_mq_ta(self, topic, channel):
      log.info("Processing: " + topic)
      try:
        channel.start_consuming()
      except pika.exceptions.StreamLostError:
        log.warning("rabbimq SSL channel terminated")
      except Exception as e:
        exc_type, _, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        log.error("process_mq_ta: {0} {1} {2} {3}".format(exc_type, fname, exc_tb.tb_lineno, e))
        traceback.print_exc()

  def process_tmp_ta(self, filename=""):
      if filename == "":
        log.info("INFO: No files to process now.")  
      else:
      
        if not os.path.isfile(filename):
          log.error("ERROR: filename "+filename+" is not a file.")
          return False
        else:
          log.info("Processing: " + filename)
          self.iostatus[filename]['running'] = True
          self.iostatus[filename]['tail'] = sh.tail("-F", filename, _iter=True, _bg_exc=False)
  
        while self.iostatus[filename]['running'] and self.thread_ctrl['continue']:
          try:
              line = self.iostatus[filename]['tail'].next()
              summary=get_summary_from_json(json.loads(line))
              if summary is not None:
                self.influxdb.influxdb_queue.put(summary)
              else:
                log.warning("can't get summary from {0}".format(line))

          except sh.ErrorReturnCode_1: # as e:
              log.info("process_tmp_ta: tail terminated {0}, (permission denied ?) ".format(filename))
              break
          except sh.SignalException_SIGKILL as e:
              log.info("process_tmp_ta: tail terminated {0} {1}".format(filename, e))
              break
          except Exception as e:
              exc_type, _, exc_tb = sys.exc_info()
              fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
              log.error("process_tmp_ta: {0} {1} {2} {4}".format(exc_type, fname, exc_tb.tb_lineno, e))

        log.info('process_tmp_ta: exiting ' + filename)
        #with open(iostatus, 'wb') as handle:
        #  pickle.dump(iostatus, handle, protocol=pickle.HIGHEST_PROTOCOL)
        return True

  def run(self):
    if self.mode == 'p': # producer
      print("PRODUCER NOT YET IMPLEMENTED")
      log.info("Running #### CLIENT/PRODUCER ####")
      sys.exit(0)

    elif self.mode == 'c': #consumer
      log.info("Running #### SERVER/CONSUMER ####")
      self.listener = self.TAHandler(self.process_mq_ta, self.iostatus, self.mode, self.thread_ctrl,\
        self.rabbitmq, self.influxdb)
      self.listener.start()
      if os.getenv('INFLUXDB_ENABLE') == 'true':
        log.info("CONSUMER: running thread.")
        threading.Thread(target=self.influxdb.influxdb_updater_thread, 
            args=(self.pluginPreProcess,),
            daemon=True).start()
        log.info("CONSUMER: Done")

    else: #standalone
      log.info("Running #### STANDALONE ####")
      self.listener = self.TAHandler(self.process_tmp_ta, self.iostatus, self.mode, self.thread_ctrl)
      self.listener.start()
      if os.getenv('INFLUXDB_ENABLE') == 'true':
        log.info("STANDALONE: running thread.")
        threading.Thread(target=self.influxdb.influxdb_updater_thread, 
            args=(self.pluginPreProcess,),
            daemon=True).start()
        log.info("STANDALONE: Done")
    log.info("MAIN: joining threads")

    try:
        while self.thread_ctrl['continue']:
          time.sleep(1)
          try:
            if self.mode == 'p': # producer
              print("PRODUCER NOT YET IMPLEMENTED")
            #elif self.mode == 'c': # consumer
            #  TBD
            else: # standalone
              for k in self.iostatus.keys():
                if 'running' in self.iostatus[k].keys():
                  if self.iostatus[k]['running']:
                    if 'thread' in self.iostatus[k].keys():
                      log.info("MAIN: waiting for " + k)
                      self.iostatus[k]['thread'].join()
                      self.iostatus[k]['running'] = False
                      log.info("MAIN: " +k + " joined")
          except RuntimeError as re:
            log.warning("WARNING: " + str(re))
            pass 
    except KeyboardInterrupt:
      self.stop()
    log.info("MAIN: listener join")
    self.listener.join()
    self.influxdb.influxdb_queue.join()

  def stop(self):
    if self.mode == 's':
      for k in self.iostatus.keys():
        try: 
            self.iostatus[k]['tail'].kill()
        except ProcessLookupError: # as ple: :TODO: improve this
            pass
    elif self.mode == 'c':
      for k in self.iostatus.keys():
        try: 
            self.iostatus[k]['channel'].close()
        except Exception: #TODO: improve this
            pass
    self.listener.stop()

def get_summary_from_json(j):
    summary = {'std' : {}, 'ext': {}} #std == standard, ext == extended (rDNS. GeoIP, etc)
    if 'TrafficData' not in j.keys():
      return None
    if 'Data' not in j['TrafficData'].keys():
      return None
    if j['TrafficData']['Data'] is None:
      return None
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
      #log.debug("DOMAIN:" + d['Domain'] + "," + d['SIP'])
      #for dev in summary.keys():
      #  for app in summary[dev]:
      #    log.debug(app + "-" + dev + " " + str(summary[dev][app]))
    return summary

#if __name__ == "__main__":
#  app = AppMonitor()
#  app.run()
