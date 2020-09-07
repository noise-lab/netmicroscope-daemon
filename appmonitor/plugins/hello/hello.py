import logging

"""appmonitor plugin template"""

printF = print

def init(printFunc=print):
  printF = printFunc
  printF("hello plugin init")

def preprocess(data):
  #printF("hello plugin preprocess")
  return data
