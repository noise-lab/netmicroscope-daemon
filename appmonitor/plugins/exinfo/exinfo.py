import os, sys
from os import path
import geoip2.webservice
import dns.resolver,dns.reversename
import pickle
import re
import asyncio
import threading
import time
from geoip2.errors import *

"""Extended info about TCP/IP connections (GeoIP, rDNS, DNS)"""

printF = print
exinfopath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
extpkl = os.path.join(exinfopath, "exinfo.pkl")
extbls = os.path.join(exinfopath, "exinfo.bls")

#lift from https://gist.github.com/mnordhoff/2213179
ipv4re = re.compile(
    '^(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$'
    )
ipv6re = re.compile(
    '^(?:(?:[0-9A-Fa-f]{1,4}:){6}(?:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4}|(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))|::(?:[0-9A-Fa-f]{1,4}:){5}(?:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4}|(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))|(?:[0-9A-Fa-f]{1,4})?::(?:[0-9A-Fa-f]{1,4}:){4}(?:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4}|(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))|(?:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4})?::(?:[0-9A-Fa-f]{1,4}:){3}(?:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4}|(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))|(?:(?:[0-9A-Fa-f]{1,4}:){,2}[0-9A-Fa-f]{1,4})?::(?:[0-9A-Fa-f]{1,4}:){2}(?:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4}|(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))|(?:(?:[0-9A-Fa-f]{1,4}:){,3}[0-9A-Fa-f]{1,4})?::[0-9A-Fa-f]{1,4}:(?:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4}|(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))|(?:(?:[0-9A-Fa-f]{1,4}:){,4}[0-9A-Fa-f]{1,4})?::(?:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4}|(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))|(?:(?:[0-9A-Fa-f]{1,4}:){,5}[0-9A-Fa-f]{1,4})?::[0-9A-Fa-f]{1,4}|(?:(?:[0-9A-Fa-f]{1,4}:){,6}[0-9A-Fa-f]{1,4})?::)$'
    )

class ExInfo:
    instance = None
    
    def __new__(cls, exinfopath, extpkl):
        if not ExInfo.instance:
            ExInfo.instance = ExInfo.__ExInfo(exinfopath, extpkl)
        return ExInfo.instance

    def __getattr__(self, name):
        return getattr(self.instance, name)

    def __setattr__(self, name, value):
        return setattr(self.instance, name, value)

    class __ExInfo:
        client = None
        ext = None
        count = 0
        lock = asyncio.Lock()
        loop = None
        extpkl = None #pickle with cache resolutions
        extbls = None #black list of mac addresses
        def __init__(self, exinfopath, extpkl): #arg TBD
            self.loop = asyncio.get_event_loop()
            threading.Thread(target=self.thread_main_loop, 
                args=[self.lock, self.loop],
                daemon=True).start()
            if os.getenv('MMGEOIP_ID') is not None:
                mmgeoip_id = os.getenv('MMGEOIP_ID')
            else:
                printF("ERROR: MMGEOIP_ID not set, Exiting...")
                print("ERROR: MMGEOIP_ID not set, Exiting...")
                sys.exit(1)
            if os.getenv('MMGEOIP_KEY') is not None:
                mmgeoip_key = os.getenv('MMGEOIP_KEY')
            else:
                printF("ERROR: MMGEOIP_KEY not set, Exiting...")
                sys.exit(1)
            self.client = geoip2.webservice.Client(
                mmgeoip_id,
                mmgeoip_key
            )
            if not path.exists(exinfopath):
                os.mkdir(exinfopath)
            if path.exists(extpkl):
                self.ext = pickle.load(open(extpkl,'rb'))
                self.extpkl = extpkl
                if self.ext is None:
                   self.ext = {}
            else:
                self.ext = {}
                with open(extpkl, 'wb') as f:
                    pickle.dump(self.ext, f, protocol=pickle.HIGHEST_PROTOCOL)
            if path.exists(extbls):
                with open(extbls, 'r') as f:
                    self.extbls = f.readlines()
                blacklist = []
                for l in self.extbls:
                    if l[-1] == '\n':
                        blacklist.append(l[:-1])
                    else:
                        blacklist.append(l)
                self.extbls = blacklist
                #printF("{}".format(blacklist))

        def __str__(self):
            return repr(self) + self.client

        def __del__(self):
            self.loop.stop()
            with open(extpkl, 'wb') as f:
                pickle.dump(self.ext, f, protocol=pickle.HIGHEST_PROTOCOL)

        def isblacklisted(self, device):
            if self.extbls is not None:
                return device in self.extbls
            return False

        def query(self, host, dnsquery): #host can be ipaddr or not
            r = None # result
            if host is None:
                return
            if host.startswith("127.0.0.1"):
                return {}
            if host.startswith("10."):
                return {}
            if host.startswith("192.168."):
                return {}
            if host.startswith("172.16."):
                return {}
            self.count+=1

            try:
                #async with self.lock:
                self.ext[host]['hits']+=1
                self.ext[host]['lts'] = time.time()
                self.ext[host]['ltsh'] = time.ctime(time.time())
                if dnsquery is not None and self.ext[host]['query'] is None:
                    self.ext[host]['query'] = dnsquery
                r = self.ext[host]
            except (KeyError, TypeError):
                n = -1
                #if(ipv4re.match(host)):
                #    r, n = mmquery(self.client, host)
                #elif (ipv6re.match(host)):
                #    r, n = mmquery(self.client, host)
                #else:
                    #TODO query hostname
                #async with self.lock:
                r = {}
                r['hits'] = 1
                r['query'] = dnsquery
                r['qr'] = n #queries remaining
                r['ts'] = time.time()
                r['tsh'] = time.ctime(time.time())
                self.ext[host] = r
                pass
            
            if 'rdns_fqdn' not in self.ext[host].keys():
                asyncio.run_coroutine_threadsafe(self.task_resolve_rdns(self.ext, host, self.lock), self.loop)
            
            if self.count % 5 == 0: #save pickle every 25 (5x5) seconds
                asyncio.run_coroutine_threadsafe(self.task_save(self.ext, self.lock), self.loop)
            
            return r
        
        def thread_main_loop(self, lock, loop):
            loop.run_forever()
            loop.close()

        async def task_resolve_rdns(self, ext, host, lock):
            async with lock:
              ext[host]['rdns_fqdn'] = \
                    [str(a) for a in dns.resolver.resolve(dns.reversename.from_address(host),"PTR")]
        
        async def task_save(self, ext, lock):
             async with lock:
                try:
                    with open(extpkl, 'wb') as f:
                        pickle.dump(ext, f, protocol=pickle.HIGHEST_PROTOCOL)
                except Exception as e:
                    printF("task_save: Exception {}".format(e))

exinfo = None

def s(s):
  if s is None:
      return ''
  else:
      return str(s).replace(',', ' ')

def i(i):
  if type(i) == int:
      return i
  else:
     try:
         int(i)
     except Exception as e:
         printF("ERROR: mmquery.i {0}".format(e))
         return -1

def mmquery(client, ipaddr):
    try:
        response = client.city(ipaddr)
    except HTTPError as he:
        if he is not None:
            printF("(HTTPSerror) Failed to query {0}: {1}".format(ipaddr, he))
            return {'err' : str(he)}, None
    except GeoIP2Error as ge:
        if ge is not None:
            print("(GeoIP2Error) Failed to query {0}: {1}".format(ipaddr, ge))
            return {'err' : str(ge)}, None
    except Exception as e:
        print("(Exception) Failed to query {0}: {1}".format(ipaddr, e))
        return {'err' : str(e)}, None

    printF("Queries remaining:", response.maxmind.queries_remaining)
    return {'ip': ipaddr, 'city': s(response.city.name),
            'state': s(response.subdivisions.most_specific.iso_code),
            'country': s(response.country.iso_code),
            'continent': s(response.continent.name),
            'lat': s(response.location.latitude),
            'lng': s(response.location.longitude),
            'isp': s(response.traits.isp),
            'org': s(response.traits.organization),
            'domain': s(response.traits.domain),
            'conntype': s(response.traits.connection_type),
            'ASnum': i(response.traits.autonomous_system_number),
            'ASorg': s(response.traits.autonomous_system_organization)}, response.maxmind.queries_remaining

def init(printFunc=print):
  global exinfo
  printF = printFunc
  exinfo = ExInfo(exinfopath, extpkl)

def preprocess(data):
  device = None
  sip = None
  query = None
  ddata = None
  
  if data is None:
      return data

  if 'std' in data.keys():
    if data['std'] is not None:
      for dev in data['std'].keys():
        for app in data['std'][dev].keys():
          if 'SIP' in data['std'][dev][app].keys():
            sip = data['std'][dev][app]['SIP']
            device = dev
          if 'Domain' in data['std'][dev][app].keys():
            query = data['std'][dev][app]['Domain']
    if sip is not None and query is not None:
        if not exinfo.isblacklisted(device):
           ddata = exinfo.query(sip, query)
        #else:
        #   printF("DEVICE BLACKLISTED:{}".format(device))
  data['ext'] = ddata
  return data

def test_query(sip, query):
    print("{}".format(exinfo.query(sip, query)))
