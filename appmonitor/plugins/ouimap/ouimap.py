import os, sys
from os import path
import logging
import pickle
import urllib.request
import re

"""OUI mac address to manufacturer mapping"""
PLUGIN_PRIORITY = 1

printF = print
ouidatpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ouitxt = os.path.join(ouidatpath, "oui.txt")
ouipkl = os.path.join(ouidatpath, "oui.pkl")

config = None
oui = None

ouiurl=[
  "https://linuxnet.ca/ieee/oui.txt",
  "http://standards-oui.ieee.org/oui/oui.txt"
]

def init(printFunc=print, conf=None):
  global oui
  printF = printFunc
  config = conf
  if not path.exists(ouidatpath):
    os.mkdir(ouidatpath)
  if path.exists(ouipkl):
    try:
      oui = pickle.load(open(ouipkl,'rb'))
    except Exception as e:
      exc_type, _, exc_tb = sys.exc_info()
      fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
      return -1, "ouimap: ({0}) {1} {2} {3}".format(str(e), exc_type, fname, exc_tb.tb_lineno)
  else:
    if not path.exists(ouitxt):
      for url in ouiurl:
        try:
          response = urllib.request.urlopen(url)
          data = response.read()
          f = open(ouitxt, "w")
          f.write(data.decode('utf-8'))
          f.close()
          break
        except Exception as e:
          printF("ouimap: WARNING Failed to retrive {0}".format(url))
          printF("ouimap: ERROR {0}".format(e))
          pass
      oui = generate_oui_dict()
  printF("Module OUI mapping initialized (ouimap) with {0}".format(config))
  return PLUGIN_PRIORITY, "ok"

def preprocess(data):
  #printF("ouimap: preprocessing")
  ddata = {}
  if oui is None:
    printF("ouimap: ERROR oui dict not initialized")
    return data
  if data is None:
    return data
  if 'std' in data.keys() and data['std'] is not None:
    for dev in data['std'].keys():
      try:
        ddata[transform(oui[dev[:8]])+dev[-2]+dev[-1]] = data['std'][dev]
      except KeyError:
        ddata[dev[:8]+"_"+dev[-2]+dev[-1]] = data['std'][dev]
  data['std'] = ddata
  return data

def transform(str):
  str = str.replace(" ", "_")
  str = str.replace(".", "_")
  str = str.replace(",", "_")
  str = str.replace("___", "_")
  str = str.replace("__", "_")
  str = str.replace("_-_", "-")
  if str[-1] != '_':
    str = str + "_"
  return str

def generate_oui_dict():
    oui = {}
    with open(ouitxt,'r') as f:
        ouilines = f.readlines()
        p = re.compile("^(..-..-..).*\t\t(.*)") # Extract mac prefix 44-4A-DB and Manufacturer 
        for line in ouilines:
            r = p.match(line)
            if r is not None:
                try:
                    # r1 Organizational Unique Identifier OUI eg 44:4a:db
                    # r2 manufacturer eg "Apple, Inc."
                    r1=r.group(1).replace("-",":").lower()
                    r2=r.group(2)
                except IndexError as ie:
                    print("WARN: generate_oui_dict regex - " + str(ie))
                    continue
                oui[r1] = r2
    with open(ouipkl, 'wb') as f:
      pickle.dump(oui, f, protocol=pickle.HIGHEST_PROTOCOL)
    return oui
