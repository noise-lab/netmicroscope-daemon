import logging

"""appmonitor plugin template"""
PLUGIN_PRIORITY = 0

printF = print
config = None

def init(printFunc=print, conf = None):
  printF = printFunc
  config = None
  printF("hello plugin init with {0}".format(config))
  return PLUGIN_PRIORITY, "ok"

def preprocess(data):
  #printF("hello plugin preprocess")
  return data
