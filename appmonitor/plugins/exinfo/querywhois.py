#!/usr/bin/env python3
import os, sys
from ipwhois import IPWhois

print("{}".format(IPWhois(sys.argv[1]).lookup_whois()))
