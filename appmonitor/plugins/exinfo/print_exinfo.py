#!/usr/bin/env python3

import pickle

d = pickle.load(open("exinfo.pkl",'rb'))

print("{}".format(d))
