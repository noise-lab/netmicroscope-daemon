#!/usr/bin/env python3
import os
from datetime import datetime
from sqlalchemy import bindparam
from sqlalchemy import Column
from sqlalchemy import create_engine
from sqlalchemy import pool
from sqlalchemy import Integer, String, DateTime, ForeignKey, func, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship
import threading

Base = declarative_base()
DATA_EXINFODB = "data/exinfodb.sqlite"

class Connection(Base):
    __tablename__ = "connection"
    id = Column(String, primary_key=True)
    host = Column(String, ForeignKey("ext.host", ondelete='cascade'), nullable=True)
    ts = Column(DateTime)  #timestamp
    lts = Column(DateTime) #last seen timestamp
    def __str__(self):
        return "Connection({0},{1},{2})".format(self.id, self.ts, self.lts)

class Ext(Base): #Extension (Extended Info)
    __tablename__ = "ext"
    host = Column(String, primary_key=True)
    device = Column(String)
    query = Column(String, nullable=True)
    hits = Column(Integer) #number of hits this profile has received
    qr = Column(Integer,  nullable=True)   #maxmind queries remaning recorded at the time this profile was hit
    ts = Column(DateTime)  #timestamp
    lts = Column(DateTime,  nullable=True) #last seen timestamp
    has_geoip = Column(Boolean, default=False)
    has_whois = Column(Boolean, default=False)
    has_rdns = Column(Boolean, default=False)
    is_pending = Column(Boolean, nullable=True)
    def __str__(self):
        return "Ext({0},{1},{2},{3},{4},{5},{6},{7},{8},{9})".format(self.host,\
            self.hits, self.device,self.query, self.qr, self.ts, self.lts,\
                 self.has_geoip, self.has_whois, self.has_rdns)

class GeoIP(Base):
    __tablename__ = "geoip"
    id = Column(Integer, primary_key=True)
    host = Column(String, ForeignKey("ext.host", ondelete='cascade'), nullable=True)
    city = Column(String)
    state = Column(String)
    country = Column(String)
    continent = Column(String)
    lat = Column(String)
    lng = Column(String)
    isp = Column(String)
    org = Column(String)
    domain = Column(String)
    conntype = Column(String)
    asnum = Column(Integer)
    asorg = Column(String)
    def __str__(self):
        return "GeoIP({0},{1},{2},{3},{4},{5},{6},{7},{8})".format(self.id, self.host,\
            self.city,self.state,self.country, self.lat, self.lng, self.domain, self.asorg)

class Rdns(Base):
    __tablename__ = "rdns"
    id = Column(Integer, primary_key=True)
    host = Column(String, ForeignKey("ext.host", ondelete='cascade'), nullable=True)
    info = Column(String) #summarized info
    def __str__(self):
        return "Rdns({0},{1},{2})".format(self.id, self.host, self.info)

class Whois(Base):
    __tablename__ = "whois"
    id = Column(Integer, primary_key=True)
    host = Column(String, ForeignKey("ext.host", ondelete='cascade'), nullable=True)
    info = Column(String) #summarized info
    def __str__(self):
        return "Whois({0},{1},{2})".format(self.id, self.host, self.info)

class ExInfoDB: # Extended Info
    engine = None
    session = None
    conn = None
    debug = None
    def __init__(self, debug = False):
        self.session = {}
        self.debug = debug

    def getSession(self):
        id = threading.current_thread().ident 
        if id not in self.session.keys():
           self.session[id] = {} #TODO: can use single engine (?)
           self.session[id]['engine'] = create_engine("sqlite:///"+\
                os.path.join(os.path.dirname(os.path.realpath(__file__)),\
                DATA_EXINFODB))
           self.session[id]['engine'].pool =\
                pool.StaticPool(creator=self.session[id]['engine'].pool._creator)
           self.session[id]['session'] =\
                Session(bind=self.session[id]['engine'])
           Base.metadata.drop_all(self.session[id]['engine'])
           Base.metadata.create_all(self.session[id]['engine'])
        return self.session[id]['session']
    
    def insertConnections(self, c):
        session = self.getSession()
        try:
            session.bulk_save_objects(
                c,
                return_defaults=True,
            )  
            session.commit()
        except Exception as err:
            session.rollback()
            c = self.getConnection(c[0].id)
            return c, "{}".format(err)
        return c, None

    def insertEx(self, e):
        session = self.getSession()
        try:
            session.bulk_save_objects(
                e,
                return_defaults=True,
            )     
            session.commit()
        except Exception as err:
            session.rollback()
            e = self.getEx(e[0].host)
            return e, "{}".format(err)
        return e, None
    
    def updateExQuery(self, ex, query):
        session = self.getSession()
        session.query(Ext).filter(Ext.host == ex.host).update({'query' : query})
        try:
            session.commit()
        except Exception as err:
            session.rollback()

    def updateEx(self, ex, exinfo, qr=0):
        session = self.getSession()
        if isinstance(exinfo, GeoIP):
            if not ex.has_geoip:
              session.query(Ext).filter(Ext.host == ex.host).update({'has_geoip' : True,\
                  'is_pending' : True, 'qr': qr})
            else:
              geoip = session.query(GeoIP).filter_by(host=ex.host).all()
              return geoip, None
        elif isinstance(exinfo, Whois):
            if not ex.has_whois:
              session.query(Ext).filter(Ext.host == ex.host).update({'has_whois' : True,\
                  'is_pending' : True})
            else:
              whois = session.query(Whois).filter_by(host=ex.host).all()
              return whois, None
        elif isinstance(exinfo, Rdns):
            if not ex.has_rdns:
              session.query(Ext).filter(Ext.host == ex.host).update({'has_rdns' : True,\
                  'is_pending' : True})
            else:
              rdns = session.query(Rdns).filter_by(host=ex.host).all()
              return rdns, None
        try:
            session.add_all([exinfo])
            session.commit()
        except Exception as err:
            session.rollback()
            return [exinfo], "{}".format(err)

        return [exinfo], None
    
    def hitAndUpdate(self, host, dnsquery):
        session = self.getSession()
        ex = self.getEx(host)
        if len(ex) > 0:
            ex = ex[0]
        else:
            return True, "Not found"
        query = None

        if ex.query is None or ex.query == '':
           if dnsquery is not None:
               query = dnsquery
           elif ex.has_rdns:
                rdns = session.query(Rdns).filter_by(host=ex.host).all()
                query = rdns[0].info
           else:
                if ex.has_whois:
                    whois = session.query(Whois).filter_by(host=ex.host).all()
                    query = whois[0].info
                #else:
                #    query = "unresolved"

        if query is None:
            session.query(Ext).filter_by(host=ex.host).update({
                'hits' : ex.hits + 1,
                'lts' : datetime.utcnow()
            })
        else:
            session.query(Ext).filter_by(host=ex.host).update({
                'hits' : ex.hits + 1,
                'lts' : datetime.utcnow(),
                'query' : query
            })
        try:
            session.commit()
        except Exception as err:
            session.rollback()
            return False, err
        return True, None

    def getConnection(self, connid):
        session = self.getSession()
        row = session.query(Connection).filter_by(id=connid).all()
        return row

    def getEx(self, host):
        session = self.getSession()
        row = session.query(Ext).filter_by(host=host).all()
        return row

    def getExInfo(self, host):
        session = self.getSession()
        geoip = session.query(GeoIP).filter_by(host=host).all()
        whois = session.query(Whois).filter_by(host=host).all()
        rdns = session.query(Rdns).filter_by(host=host).all()
        if isinstance(geoip, list):
            geoip = geoip[0] if len(geoip) > 0 else None
        if isinstance(whois, list):
            whois = whois[0] if len(whois) > 0 else None
        if isinstance(rdns, list):
            rdns = rdns[0] if len(rdns) > 0 else None
        return geoip, whois, rdns

    def getExPending(self):
        session = self.getSession()
        ret = []
        ext = session.query(Ext).filter_by(is_pending=True).all()
        for e in ext:
            geoip, whois, rdns = self.getExInfo(e.host)
            ret.append({'ext': e, 'geoip': geoip, 'whois': whois, 'rdns': rdns})
            session.query(Ext).filter_by(host=e.host).update({'is_pending': False})
        return ret

    #def __str__(self):
    def __del__(self):
        for k in self.session.keys():
            self.session[k]['session'].close()
            self.session[k]['engine'].dispose()

""" TODO: move to testing framework
def main():
    exinfodb = ExInfoDB()
    c1, err = exinfodb.insertConnections([Connection(id="test", \
        ts=datetime.utcnow(),\
        lts=datetime.utcnow())] )
    if err is not None:
        print("{}".format(err))
    else:
        print("{}".format(c1[0]))
    c2=exinfodb.getConnection("test")
    print("{}".format(c2[0]))
                                            # query="example.com",\
    ex1, err = exinfodb.insertEx([Ext(host="200.10.10.1",\
        hits=1, qr=0, ts=datetime.utcnow())])
        
        #,\
        #    has_geoip=False,\
        #        has_whois=False,\
        #            has_rdns=False)])
    if err is not None:
        print("{}".format(err))
    print("{}".format(ex1[0]))

    exinfo1, err = exinfodb.updateEx(ex1[0], Whois(host=ex1[0].host, info="whois.test.com"))
    if err is not None:
        print("{}".format(err))
    print("{}".format(exinfo1[0]))

    exinfo2, err = exinfodb.updateEx(ex1[0], Rdns(host=ex1[0].host, info="rdns.example.com"))
    if err is not None:
        print("{}".format(err))
    print("{}".format(exinfo2[0]))

    ok, err = exinfodb.hitAndUpdate("200.10.10.1", None)
    if ok:
        if err is not None:
            print("OK")
        else:
            print("{}".format(exinfodb.getEx("200.10.10.1")[0]))
    elif err is not None:
        print("{}".format(err))
    #else:
        #print("{}".format(exinfodb.getEx("200.10.10.1")[0]))

if __name__ == "__main__":
    main()
"""

