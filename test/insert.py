#!/usr/bin/env python

import os, sys
import time
import urllib
import urllib.parse
import urllib.request
from dotenv import load_dotenv

load_dotenv(verbose=True)

host = ''
port = ''
userw = ''
passw = ''
deployment = ''
database = ''

if os.getenv('INFLUXDB_ENABLE') == 'true':
    print("INFO: influxdb enabled, checking environment variables...")
    if os.getenv('INFLUXDB_HOST') is not None:
      host = os.getenv('INFLUXDB_HOST')
    else:
      print("ERROR: INFLUXDB_HOST not set, Exiting...")
      sys.exit(1)
    if os.getenv('INFLUXDB_PORT') != 0:
      port = os.getenv('INFLUXDB_PORT')
    else:
      print("ERROR: INFLUXDB_PORT not set, Exiting...")
      sys.exit(1)
    if os.getenv('INFLUXDB_WRITE_USER') is not None:
      userw = os.getenv('INFLUXDB_WRITE_USER')
    else:
      print("ERROR: INFLUXDB_WRITE_USER not set, Exiting...")
      sys.exit(1)
    if os.getenv('INFLUXDB_WRITE_USER_PASSWORD') is not None:
      passw = os.getenv('INFLUXDB_WRITE_USER_PASSWORD')
    else:
      print("ERROR: INFLUXDB_WRITE_USER_PASSWORD not set, Exiting...")
      sys.exit(1)
    if os.getenv('INFLUXDB_DEPLOYMENT') is not None:
      deployment = os.getenv('INFLUXDB_DEPLOYMENT')
    else:
      print("ERROR: INFLUXDB_DEPLOYMENT not set, Exiting...")
      sys.exit(1)
    if os.getenv('INFLUXDB_DB') is not None:
      database = os.getenv('INFLUXDB_DB')
    else:
      print("ERROR: INFLUXDB_DB not set, Exiting...")
      sys.exit(1)


def influxdb_updater_thread():
  url = None
  header = None
  while True:
      if url == None:
        url = "https://" + host + ":" + port + "/api/v2/write?bucket=" +\
          database + "/rp&precision=ns"
      if header == None:
        header = {'Authorization': 'Token ' + userw + ":" + passw}

      deployment = 'test'
      dev = '01:02:03:0a:0b:0c'
      app = 'Netflix'
      KbpsDw = 100.0
      KbpsUp = 100.0
      TsEnd = str(time.time())[:10] + '000000000'
      data = ''

      data = data + 'network_traffic_application_kbpsdw'+\
              ',deployment=' + deployment +\
              ',device=' + dev +\
              ',application=' + app +\
              ' value=' + str(KbpsDw) +\
              ' ' + TsEnd + '\n'
      data = data + 'network_traffic_application_kbpsup'+\
              ',deployment=' + deployment +\
              ',device=' + dev +\
              ',application=' + app +\
              ' value=' + str(KbpsUp)  +\
              ' ' + TsEnd + '\n'

      app = 'Youtube'
      KbpsDw = 50.0
      KbpsUp = 50.0
      data = data + 'network_traffic_application_kbpsdw'+\
              ',deployment=' + deployment +\
              ',device=' + dev +\
              ',application=' + app +\
              ' value=' + str(KbpsDw) +\
              ' ' + TsEnd + '\n'
      data = data + 'network_traffic_application_kbpsup'+\
              ',deployment=' + deployment +\
              ',device=' + dev +\
              ',application=' + app +\
              ' value=' + str(KbpsUp)  +\
              ' ' + TsEnd + '\n'

      data = data.encode()
      req = urllib.request.Request(url, data, header)
      with urllib.request.urlopen(req) as response:
        print('OK' if response.getcode()==204 else 'Unexpected:'+str(response.getcode()))
      
      time.sleep(5)

influxdb_updater_thread()
