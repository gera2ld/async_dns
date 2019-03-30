import os, time
from . import address, utils, types, Record

class Hosts:
    def __init__(self):
        self.data = {}
        self.changed = False
        self.add_item('localhost', types.A, '127.0.0.1')

    def __bool__(self):
        return bool(self.data)

    def __repr__(self):
        return '<%s [%s]>' % (self.__class__.__name__, ', '.join(self.data.keys()))

    def update(self, other):
        for k, v in other.data.items():
            item = self.data.setdefault(k, [])
            item.extend(v)

    def add_host(self, record):
        if record.ttl == 0:
            # RFC 1035: should not be cached while TTL=0
            return
        key = record.name.lower()
        item = self.data.get(key, [])
        for i in item:
            if i.update(record): break
        else:
            item.append(record)
        if item:
            self.data[key] = item
        self.changed = True

    def add_item(self, name, qtype, data):
        '''
        Add an item to cache.
        '''
        self.add_host(Record(name=name, data=data, qtype=qtype, ttl=-1))

    def get(self, key, default = None):
        # TODO improve cache GC performance
        vs = self.data.get(key)
        now = time.time()
        if vs is not None:
            i = 0
            while i < len(vs):
                v = vs[i]
                if v.ttl >= 0 and v.timestamp + v.ttl < now:
                    last = vs.pop()
                    if last is not v:
                        vs[i] = last
                    self.changed = True
                else:
                    i += 1
        if vs is None:
            vs = [] if default is None else default
        return vs

    def get_ip(self, key, default = None):
        a = aaaa = cname = None
        for i in self.data.get(key):
            if aaaa is None and i.qtype == types.AAAA:
                aaaa = i
            elif a is None and i.qtype == types.A:
                a = i
            elif cname is None and i.qtype == types.CNAME:
                cname = i
        return aaaa or a or cname or default

    def query(self, name, qtype = types.ANY):
        name = name.lower()
        while True:
            host = self.get(name)
            if host: break
            i = name.find('.', 1)
            if i < 0: break
            name = name[i:]
        try:
            qtype = tuple(qtype)
        except:
            qtype = qtype,
        return filter(lambda h: h.qtype in qtype, host)
