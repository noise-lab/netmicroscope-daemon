#!/usr/bin/env python3
import os
import exinfo
import time
exinfopath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
extpkl = os.path.join(exinfopath, "exinfo.pkl")

exinfo.init()
exinfo.test_query("8.8.8.8", "")

time.sleep(10)
