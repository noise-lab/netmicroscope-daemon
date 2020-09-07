import os
from os import path
import logging
import pickle
import urllib.request
import re

"""OUI mac address to manufacturer mapping"""

printF = print
ouidatpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ouitxt = os.path.join(ouidatpath, "oui.txt")
ouipkl = os.path.join(ouidatpath, "oui.pkl")

oui = None

ouiurl=[
  "https://linuxnet.ca/ieee/oui.txt",
  "http://standards-oui.ieee.org/oui/oui.txt"
]

def init(printFunc=print):
  global oui
  printF = printFunc
  if not path.exists(ouidatpath):
    os.mkdir(ouidatpath)
  if path.exists(ouipkl):
    oui = pickle.load(open(ouipkl,'rb'))
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

  printF("Module OUI mapping initialized (ouimap)")

def preprocess(data):
  #printF("ouimap: preprocessing")
  ddata = {}
  if oui is None:
    printF("ouimap: ERROR oui dict not initialized")
    return data
  for dev in data.keys():
    try:
       ddata[transform(oui[dev[:8]])+dev[-2]+dev[-1]] = data[dev]
    except KeyError:
       ddata[dev[:8]+"_"+dev[-2]+dev[-1]] = data[dev]
  return ddata

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
