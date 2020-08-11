#!/usr/bin/env python

from appmonitor.appmonitor import AppMonitor

if __name__ == "__main__":
  thread_continue = True
  app = AppMonitor()
  app.run(thread_continue)
