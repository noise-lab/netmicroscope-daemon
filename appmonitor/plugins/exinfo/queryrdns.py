#!/usr/bin/env python3
import os, sys
import dns.resolver,dns.reversename

print([str(a) for a in dns.resolver.resolve(dns.reversename.from_address(sys.argv[1]),"PTR")])

# https://www.dnspython.org/examples.html
#answers = dns.resolver.query(sys.argv[1], 'MX')
#for rdata in answers:
#    print('Host', rdata.exchange, 'has preference', rdata.preference)
