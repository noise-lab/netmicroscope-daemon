import os, sys, logging
from os import path
import geoip2.webservice
import dns.resolver, dns.reversename
from ipwhois import IPWhois
import pickle
import random
import re
import asyncio
import threading
import time
from datetime import datetime
from geoip2.errors import *
from appmonitor.plugins.exinfo.exinfodb import GeoIP, Whois, Rdns, ExInfoDB, Ext

"""Extended info about TCP/IP connections (GeoIP, rDNS, DNS)"""
PLUGIN_PRIORITY = 2

config = None
exinfopath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
extbls = os.path.join(exinfopath, "exinfo.bls")
extwls = os.path.join(exinfopath, "exinfo.wls")

log = logging.getLogger(__name__)

#lift from https://gist.github.com/mnordhoff/2213179
ipv4re = re.compile(
    '^(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$'
    )
ipv6re = re.compile(
    '^(?:(?:[0-9A-Fa-f]{1,4}:){6}(?:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4}|(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))|::(?:[0-9A-Fa-f]{1,4}:){5}(?:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4}|(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))|(?:[0-9A-Fa-f]{1,4})?::(?:[0-9A-Fa-f]{1,4}:){4}(?:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4}|(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))|(?:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4})?::(?:[0-9A-Fa-f]{1,4}:){3}(?:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4}|(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))|(?:(?:[0-9A-Fa-f]{1,4}:){,2}[0-9A-Fa-f]{1,4})?::(?:[0-9A-Fa-f]{1,4}:){2}(?:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4}|(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))|(?:(?:[0-9A-Fa-f]{1,4}:){,3}[0-9A-Fa-f]{1,4})?::[0-9A-Fa-f]{1,4}:(?:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4}|(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))|(?:(?:[0-9A-Fa-f]{1,4}:){,4}[0-9A-Fa-f]{1,4})?::(?:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4}|(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))|(?:(?:[0-9A-Fa-f]{1,4}:){,5}[0-9A-Fa-f]{1,4})?::[0-9A-Fa-f]{1,4}|(?:(?:[0-9A-Fa-f]{1,4}:){,6}[0-9A-Fa-f]{1,4})?::)$'
    )

class ExInfo:
    instance = None
    
    def __new__(cls, exinfopath, debug = False):
        if not ExInfo.instance:
            ExInfo.instance = ExInfo.__ExInfo(exinfopath, debug)
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
        extbls = None #black list of mac addresses
        extwls = None #white list of mac addresses
        exinfodb = ExInfoDB()
        def __init__(self, exinfopath, debug): #arg TBD
            self.debug = debug
            self.loop = asyncio.get_event_loop()
            threading.Thread(target=self.thread_main_loop, 
                args=[self.lock, self.loop],
                daemon=True).start()
            if os.getenv('MMGEOIP_ID') is not None:
                mmgeoip_id = os.getenv('MMGEOIP_ID')
            else:
                log.error("ERROR: MMGEOIP_ID not set, Exiting...")
                print("ERROR: MMGEOIP_ID not set, Exiting...")
                sys.exit(1)
            if os.getenv('MMGEOIP_KEY') is not None:
                mmgeoip_key = os.getenv('MMGEOIP_KEY')
            else:
                log.error("ERROR: MMGEOIP_KEY not set, Exiting...")
                sys.exit(1)
            self.client = geoip2.webservice.Client(
                mmgeoip_id,
                mmgeoip_key
            )
            if not path.exists(exinfopath):
                os.mkdir(exinfopath)
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
            if path.exists(extwls):
                with open(extwls, 'r') as f:
                    self.extwls = f.readlines()
                whitelist = []
                for l in self.extwls:
                    if l[-1] == '\n':
                        whitelist.append(l[:-1])
                    else:
                        whitelist.append(l)
                self.extwls = whitelist

        def __str__(self):
            return repr(self) + self.client

        def __del__(self):
            self.loop.stop()

        def isblacklisted(self, device):
            if self.extbls is not None:
                return device in self.extbls
            return False

        def iswhitelisted(self, device):
            if self.extwls is None:
                return True
            return device in self.extwls

        def query(self, host, dnsquery, device): #host can be ipaddr or not
            retErr = None
            if host is None:
                return None, retErr
            if host.startswith("127.0.0.1"):
                return None, retErr
            if host.startswith("10."):
                return None, retErr
            if host.startswith("192.168."):
                return None, retErr
            if host.startswith("172.16."):
                return None, retErr
            #TODO: decent multicast addr matching
            if host.startswith("239."):
                return None, retErr
            if host.startswith("224.0."):
                return None, retErr
            self.count+=1

            ext = [Ext(host=host,query=dnsquery,\
                device=device, hits=0, qr=-1, ts=datetime.utcnow())]
            ext1, err1 = self.exinfodb.insertEx(ext)
            if err1 is not None:
                ok, err2 = self.exinfodb.hitAndUpdate(host, dnsquery)
                if not ok and err2 is not None:
                    retErr = "WARNING: insertEx:{0}/hitAndUpdate:{1}".format(err1, err2)
                #else:
                    #print("{}".format(exinfodb.getEx("200.10.10.1")[0]))

            if isinstance(ext1, list):
                if len(ext1) > 0:
                   ext1 = ext1[0]
                else:
                   retErr = "WARNING: insertEx failed to insert {0}".format(ext1)
                   log.error(retErr)
                   return None, retErr

            if ext1 is not None:
                if not ext1.has_rdns:
                    asyncio.run_coroutine_threadsafe(self.task_resolve_rdns(self.ext, host, ext1, self.lock), self.loop)

            if ext1 is not None:
                if not ext1.has_whois:
                    asyncio.run_coroutine_threadsafe(self.task_resolve_whois(self.ext, host, ext1, self.lock), self.loop)

            if ext1 is not None:
                if not ext1.has_geoip:
                    asyncio.run_coroutine_threadsafe(self.task_resolve_geoip(self.ext, host, ext1, self.lock), self.loop)
            return ext1, retErr
        
        def thread_main_loop(self, lock, loop):
            loop.run_forever()
            loop.close()

        async def task_resolve_rdns(self, ext, host, ext1, lock):
            async with lock:
                try:
                   rdns_host=[str(a) for a in dns.resolver.resolve(dns.reversename.from_address(host),"PTR")]
                   if (ext1.query is None or ext1.query == '') and len(rdns_host) > 0:
                        self.exinfodb.updateExQuery(ext1, rdns_host[0])
                   _, err = self.exinfodb.updateEx(ext1,\
                   Rdns(host=ext1.host,\
                        info="{}".format(rdns_host)))
                   if self.debug:
                        log.info("RDNS: host:{0}, device:{1}, org:{2}, query:{3} rdns:{4}"\
                            .format(host, ext1.host, ext1.device,\
                                 ext1.query, rdns_host))
                   if err is not None:
                     log.warning("WARNING: task_resolve_rdns unable to update/insert ({0})".format(err))
                except Exception as e:
                  if self.debug:
                    log.error("task_resolve_rdns {}".format(e))

        async def task_resolve_whois(self, ext, host, ext1, lock):
            async with lock:
                try:
                    whois = IPWhois(host).lookup_whois()
                    if whois is not None:
                        if 'asn_description' in whois.keys():
                            _, err = self.exinfodb.updateEx(ext1,\
                                Whois(host=ext1.host,\
                                    info="{}".format(whois['asn_description'])))
                            if err is not None:
                                if self.debug:
                                    log.warning("WARNING: task_resolve_whois unable to update/inser ({0})".format(err))
                        elif self.debug:
                            log.warning("WARNING: task_resolve_whois unable to resolve ({0})".format(host))
                except Exception as e:
                    if self.debug:
                        log.info("task_resolve_whois {}".format(e))

        async def task_resolve_geoip(self, ext, host, ext1, lock):
            async with lock:
                try:
                    geoip, qr = mmquery(self.client, host)
                    if geoip is not None:
                        if self.debug:
                            log.info("GEOIP: host:{0}, device:{1}, org:{2}, query:{3} city:{4}"\
                                .format(host,ext1.device,\
                                    geoip['org'], ext1.query, geoip['city']))
                        if str(geoip['lat']) == "37.751" and str(geoip['lng'])== "-97.822":
                            geoip['lat'] += random.randint(-100, 100)
                            geoip['lng'] += random.randint(-100, 100)
                        _, err = self.exinfodb.updateEx(ext1,\
                                GeoIP(host=ext1.host,\
                                        city = geoip['city'],\
                                        state = geoip['state'],\
                                        country = geoip['country'],\
                                        continent = geoip['continent'],\
                                        lat = geoip['lat'],\
                                        lng = geoip['lng'],\
                                        isp = geoip['isp'],\
                                        org = geoip['org'],\
                                        domain = geoip['domain'],\
                                        conntype = geoip['conntype'],\
                                        asnum = geoip['ASnum'],\
                                        asorg = geoip['ASorg']), qr)
                        if err is not None:
                            log.warning("WARNING: task_resolve_geoip unable to update/inser ({0})".format(err))
                    else:
                        log.warning("WARNING: task_resolve_geoip unable to resolve ({0})".format(host))
                except Exception as e:
                    if self.debug:
                        log.warning("task_resolve_geoip {}".format(e))

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
         log.error("ERROR: mmquery.i {0}".format(e))
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
            log.warning("(HTTPSerror) Failed to query {0}: {1}".format(ipaddr, he))
            return {'err' : str(he)}, None
    except GeoIP2Error as ge:
        if ge is not None:
            log.warning("(GeoIP2Error) Failed to query {0}: {1}".format(ipaddr, ge))
            return {'err' : str(ge)}, None
    except Exception as e:
        log.warning("(Exception) Failed to query {0}: {1}".format(ipaddr, e))
        return {'err' : str(e)}, None

    #log.info("Queries remaining:", response.maxmind.queries_remaining)
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

def init(conf=None):
  global exinfo
  global config
  config = conf
  if 'deployment' not in config.keys():
      return -1, "deployment key not configured"
  exinfo = ExInfo(exinfopath)
  return PLUGIN_PRIORITY, "ok"

def preprocess(data):
  device = None
  sip = None
  query = None
  insert = []
  timestamp = None
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
          do_insert = False
          timestamp = str(data['std'][dev][app]['TsEnd'])
          if sip is not None and query is not None:
            if exinfo.iswhitelisted(device):
                do_insert = True
            if exinfo.isblacklisted(device): #black list overrides wls
                do_insert = False

            if do_insert:
                e, err = exinfo.query(sip, query, device)
                if err is not None:
                    log.info("WARNING: do_insert exinfo.query error ({0})".format(err))
                    continue
                if e is None:
                    continue
            
                geoip, whois, rdns = exinfo.exinfodb.getExInfo(e.host)

                if not e.query: # and e.hits > 0:
                    if rdns is not None:
                        if not rdns.info:
                            e.query = rdns.info
                            _, err = exinfo.exinfodb.updateExQuery(e, rdns.info)
                            if err is not None:
                                log.warning("WARNING: do_insert - unable to update query field (rdns)")
                    if not e.query:
                        if whois is not None:
                            if not whois.info:
                                e.query = whois.info
                                _, err = exinfo.exinfodb.updateExQuery(e, whois.info)
                                if err is not None:
                                    log.warning("WARNING: do_insert - unable to update query field (whois)")

                if geoip is None:
                    #log.warning("WARNING: insertQuery geoip null, query: {0}:{1}", e.host, e.query)
                    continue

                #TODO: consider disabling the following
                try:
                    insertQuery = ("geometric,deployment={0},lat={1},lng={2},country={3},"\
                        "connid={4},device={5},hits={6} metric=1 {7}"\
                        .format(config['deployment'],\
                            geoip.lat, geoip.lng, geoip.country,\
                                connid(geoip.isp, geoip.org,\
                                    geoip.city, geoip.state,\
                                        device, e.query),\
                                            device, e.hits,\
                                            timestamp + '000000000'))
                    #log.info(insertQuery)
                    insert.append(insertQuery)
                except KeyError:
                    #TODO: better error handling
                    #log.error("Key Error {0} {1}".format(device, sip))
                    pass
                '''
                data['ext'][device] = { sip : ddata }
                insertQuery = ''
                if 'geoip' in data['ext'][device][sip].keys():
                    try:
                        insertQuery = ("geometric,deployment={0},lat={1},lng={2},country={3},"\
                            "connid={4},device={5} metric=1 {6}"\
                            .format(config['deployment'],\
                                data['ext'][device][sip]['geoip'][0]['lat'],\
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
                        #log.error("Key Error {0} {1}".format(device, sip))
                        pass
                '''
  
  pending = None
  try:
      pending = exinfo.exinfodb.getExPending()
  except Exception as e:
      log.warning("WARNING exinfo.exinfodb.getExPending:{0}".format(e))
  if pending is not None:
    for p in pending:
        #log.info("PENDING: {0}, {1}/{2}/{3}".format(p['ext'], p['geoip'], p['whois'], p['rdns']))
        try:
            if p['geoip'] is None:
                continue
            else:
                e = p['ext']
                geoip = p['geoip']
            insertQuery = ("geometric,deployment={0},lat={1},lng={2},country={3},"\
                "connid={4},device={5},hits={6} metric=1 {7}"\
                .format(config['deployment'],\
                    geoip.lat, geoip.lng, geoip.country,\
                        connid(geoip.isp, geoip.org,\
                            geoip.city, geoip.state,\
                                e.device, e.query),\
                                    e.device, e.hits,\
                                    timestamp + '000000000'))
            #log.info(insertQuery)
            insert.append(insertQuery)
        except KeyError:
            #TODO: better error handling
            pass
  data['ext']['insert'] = insert
  return data

def test_query(sip, query):
    print("{}".format(exinfo.query(sip, query)))
