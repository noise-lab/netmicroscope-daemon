#!/usr/bin/python3
import os, sys
import geoip2.webservice
import shutil
import csv
from geoip2.errors import *
from dotenv import load_dotenv

def s(s):
  if s is None:
      return ''
  else:
      return str(s).replace(',', ' ')

#if len(sys.argv) < 2:
#  print("usage: " + sys.argv[0]+" ipaddr")
#  sys.exit(1)
#ipaddr = sys.argv[1]

def mmquery(ipaddr):
    filename = 'geoip1.csv'

    if ipaddr.startswith("10."):
        return {}

    if ipaddr.startswith("192.168."):
        return {}

    fields = ["ip","city","state","country","continent","lat","long","isp","org","domain","ASorg","hits"]

    with open(filename, 'r') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=fields)
        for row in reader:
            if row['ip'] == ipaddr:
                #print("hit")
                return row
                #sys.exit(0)

        client = geoip2.webservice.Client(MMGEOIP_ID, MMGEOIP_KEY)

        try:
            response = client.city(ipaddr)
        except GeoIP2Error as ge:
            if ge is not None:
                print("(GeoIP2Error) Failed to query " + ipaddr)
                print(str(ge))
                return {}
                #sys.exit(1)
        except HTTPError as he:
            if he is not None:
                print("(HTTPSerror) Failed to query " + ipaddr)
                print(str(he))
                return {}
                #sys.exit(1)
        except Exception as e:
            print("(Exception) Failed to query " + ipaddr)
            print(str(e))
            return {}
            #sys.exit(1)

    print("Queries remaining:", response.maxmind.queries_remaining)
    row=(ipaddr+","+s(response.city.name)+","+
        s(response.continent.name)+","+
        s(response.subdivisions.most_specific.iso_code)+","+
        s(response.country.iso_code)+","+
        s(response.location.latitude)+","+
        s(response.location.longitude)+","+
        s(response.traits.isp)+","+
        s(response.traits.organization)+","+
        s(response.traits.domain)+","+
        s(response.traits.autonomous_system_organization)+",\n")
    #print(row, end=""),
    with open('geoip1.csv','a') as fd:
        fd.write(row)
        fd.close()
    return {'ip': ipaddr, 'city': s(response.city.name),
            'state': s(response.subdivisions.most_specific.iso_code),
            'country': s(response.country.iso_code),
            'continent': s(response.continent.name),
            'lat': s(response.location.latitude),
            'long': s(response.location.longitude),
            'isp': s(response.traits.isp),
            'org': s(response.traits.organization),
            'domain': s(response.traits.domain),
            'AS': s(response.traits.autonomous_system_number),
            'domain': s(response.traits.domain),
            'connection_type': s(response.traits.connection_type),
            'ASorg': s(response.traits.autonomous_system_organization)}

def main(argv):
    if len(sys.argv) < 2:
        print("usage: " + sys.argv[0]+" ipaddr")
        sys.exit(1)
    ipaddr = sys.argv[1]
    r=mmquery(ipaddr)
    print(str(r),end="")

       
if __name__== "__main__":
   load_dotenv(verbose=True)

   MMGEOIP_ID = os.getenv('MMGEOIP_ID')
   MMGEOIP_KEY = os.getenv('MMGEOIP_KEY')

   main(sys.argv)
