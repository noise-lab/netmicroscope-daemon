#!/usr/bin/env python3
import os, sys
import dns.resolver,dns.reversename

print([str(a) for a in dns.resolver.resolve(dns.reversename.from_address(sys.argv[1]),"PTR")])

