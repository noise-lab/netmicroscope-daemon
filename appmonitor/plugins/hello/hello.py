import logging

"""appmonitor plugin template"""
PLUGIN_PRIORITY = 0

config = None

log = logging.getLogger(__name__)

def init(conf = None):
  config = None
  log.info("hello plugin init with {0}".format(config))
  return PLUGIN_PRIORITY, "ok"

def preprocess(data):
  #log.info("hello plugin preprocess")
  return data
