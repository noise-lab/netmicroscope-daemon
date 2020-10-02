import os, sys
from os import path
import geoip2.webservice
import dns.resolver,dns.reversename
from ipwhois import IPWhois
import pickle
import re
import asyncio
import threading
import time
from geoip2.errors import *

"""Extended info about TCP/IP connections (GeoIP, rDNS, DNS)"""
PLUGIN_PRIORITY = 2

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
    
    def __new__(cls, exinfopath, extpkl, debug = False):
        if not ExInfo.instance:
            ExInfo.instance = ExInfo.__ExInfo(exinfopath, extpkl, debug)
        return ExInfo.instance

    def __getattr__(self, name):
        return getattr(self.instance, name)

    def __setattr__(self, name, value):
        return setattr(self.instance, name, value)

    class __ExInfo:
        debug = False
        client = None
        ext = None
        count = 0
        lock = asyncio.Lock()
        loop = None
        extpkl = None #pickle with cache resolutions
        extbls = None #black list of mac addresses
        def __init__(self, exinfopath, extpkl, debug): #arg TBD
            self.debug = debug
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
            #TODO: all multicast addr
            if host.startswith("239."):
                return {}
            self.count+=1

            try:
                #async with self.lock:
                self.ext[host]['hits']+=1
                self.ext[host]['lts'] = time.time()
                self.ext[host]['ltsh'] = time.ctime(time.time())
                if self.ext[host]['hits'] > 1 and self.ext[host]['query'] =='':
                    if 'rdns_fqdn' not in self.ext[host]:
                        if 'whois' not in self.ext[host]:
                            self.ext[host]['unresolved'] = host
                        else:
                            self.ext[host]['query'] = self.ext[host]['whois']['asn_description']
                            
                    else:
                        self.ext[host]['query'] = self.ext[host]['rdns_fqdn']
                    
                if dnsquery is not None and self.ext[host]['query'] is None:
                    self.ext[host]['query'] = dnsquery
                r = self.ext[host]
            except (KeyError, TypeError):
                n = -1
                r = {}
                r['hits'] = 1
                r['query'] = dnsquery
                r['qr'] = n #queries remaining
                r['ts'] = time.time()
                r['tsh'] = time.ctime(time.time())
                self.ext[host] = r
                pass
            
            if 'rdns_fqdn' not in self.ext[host].keys():
                if self.ext[host]['hits'] > 10 :
                    if self.debug:
                      printF("WARNING rdns_fqdn for {0}".format(host))
                else:
                    asyncio.run_coroutine_threadsafe(self.task_resolve_rdns(self.ext, host, self.lock), self.loop)

            if 'whois' not in self.ext[host].keys():
                if self.ext[host]['hits'] > 10 :
                    if self.debug:
                      printF("WARNING whois for {0}".format(host))
                else:
                    asyncio.run_coroutine_threadsafe(self.task_resolve_whois(self.ext, host, self.lock), self.loop)

            if 'geoip' not in self.ext[host].keys():
                if self.ext[host]['hits'] > 10 :
                    if self.debug:
                      printF("WARNING geoip for {0}".format(host))
                else:
                    asyncio.run_coroutine_threadsafe(self.task_resolve_geoip(self.ext, host, self.lock), self.loop)
            
            if self.count % 5 == 0: #save pickle every 25 (5x5) seconds
                asyncio.run_coroutine_threadsafe(self.task_save(self.ext, self.lock), self.loop)
            
            return r
        
        def thread_main_loop(self, lock, loop):
            loop.run_forever()
            loop.close()

        async def task_resolve_rdns(self, ext, host, lock):
            async with lock:
              try:
                ext[host]['rdns_fqdn'] = \
                        [str(a) for a in dns.resolver.resolve(dns.reversename.from_address(host),"PTR")]
                if ext[host]['query'] == '':
                    ext[host]['query'] = ext[host]['rdns_fqdn'][0]
              except Exception as e:
                  if self.debug:
                    printF("task_resolve_rdns {}".format(e))
                  pass

        async def task_resolve_whois(self, ext, host, lock):
            async with lock:
              try:
                ext[host]['whois'] = IPWhois(host).lookup_whois()
              except Exception as e:
                if self.debug:
                  printF("task_resolve_whois {}".format(e))
                pass

        async def task_resolve_geoip(self, ext, host, lock):
            async with lock:
              try:
                ext[host]['geoip'] = mmquery(self.client, host)
              except Exception as e:
                if self.debug:
                  printF("task_resolve_geoip {}".format(e))
                pass

        async def task_save(self, ext, lock):
             async with lock:
                try:
                    with open(extpkl, 'wb') as f:
                        pickle.dump(ext, f, protocol=pickle.HIGHEST_PROTOCOL)
                except Exception as e:
                  if self.debug:
                    printF("task_save: Exception {}".format(e))
                  pass



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

def f(s):
  if s is None:
      return ''
  else:
      return str(s).replace(',', '\,').replace(' ', '\ ')

def connid(isp, org, city, state, device, query):
    ret = ''
    if len(isp) > 1:
        ret += isp
    elif len(org) > 1:
        ret += isp
    if len(city) > 1:
        ret += "|" + city
    if len(state) > 1:
        ret += "," + state
    ret += "|" + device
    ret += "|{}".format(query)
    return f(ret)


def mmquery(client, ipaddr):
    try:
        response = client.city(ipaddr)
    except HTTPError as he:
        if he is not None:
            printF("(HTTPSerror) Failed to query {0}: {1}".format(ipaddr, he))
            return {'err' : str(he)}, None
    except GeoIP2Error as ge:
        if ge is not None:
            printF("(GeoIP2Error) Failed to query {0}: {1}".format(ipaddr, ge))
            return {'err' : str(ge)}, None
    except Exception as e:
        printF("(Exception) Failed to query {0}: {1}".format(ipaddr, e))
        return {'err' : str(e)}, None

    #printF("Queries remaining:", response.maxmind.queries_remaining)
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
  return PLUGIN_PRIORITY

def preprocess(data):
  device = None
  sip = None
  query = None
  ddata = None
  insert = []
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
    #printF("DEVICE:{}".format(device))
          if sip is not None and query is not None:
            if not exinfo.isblacklisted(device):
                ddata = exinfo.query(sip, query)
                #else:
                #   printF("DEVICE BLACKLISTED:{}".format(device))
                data['ext'][device] = { sip : ddata }
                insertQuery = ''
                if 'geoip' in data['ext'][device][sip].keys():
                    try:
                        insertQuery = ("geometric,lat={0},lng={1},country={2},"\
                            "connid={3},device={4} metric=1 {5}"\
                            .format(data['ext'][device][sip]['geoip'][0]['lat'],\
                                data['ext'][device][sip]['geoip'][0]['lng'],\
                                data['ext'][device][sip]['geoip'][0]['country'],\
                                    connid(data['ext'][device][sip]['geoip'][0]['isp'],\
                                        data['ext'][device][sip]['geoip'][0]['org'],\
                                            data['ext'][device][sip]['geoip'][0]['city'],\
                                                data['ext'][device][sip]['geoip'][0]['state'],\
                                                device, data['ext'][device][sip]['query']),\
                                                    device,\
                                                    str(data['std'][dev][app]['TsEnd']) + '000000000'))
                        insert.append(insertQuery)
                    except KeyError:
                        #TODO: better error handling
                        #printF("Key Error {0} {1}".format(device, sip))
                        pass
  data['ext']['insert'] = insert
  return data

def test_query(sip, query):
    print("{}".format(exinfo.query(sip, query)))
