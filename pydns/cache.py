import os
from . import *
__all__ = ['DNSMemCache']

cachefile = os.path.expanduser('~/.pydns/named.cache.txt')
def get_name_cache(url = 'ftp://rs.internic.net/domain/named.cache',
        fname = cachefile):
    from urllib import request
    logger.info('Fetching named.cache...')
    try:
        r = request.urlopen(url)
    except:
        logger.warning('Error fetching named.cache')
    else:
        open(fname, 'wb').write(r.read())

def get_root_servers(fname = cachefile):
    if not os.path.isfile(fname):
        os.makedirs(os.path.dirname(fname), exist_ok = True)
        get_name_cache(fname = fname)
    # in case failed fetching named.cache
    if os.path.isfile(fname):
        for line in open(fname, 'r'):
            if line.startswith(';'): continue
            it = iter(filter(None, line.split()))
            data = [next(it).rstrip('.')]   # name
            expires = next(it)  # ignored
            data.append(types.MAP_TYPES.get(next(it), 0))   # qtype
            data.append(next(it).rstrip('.'))   # data
            yield data

class DNSMemCache(hosts.Hosts):
    name = 'DNSMemD/pydns'

    def __init__(self, filename = None):
        super().__init__(filename)
        self.add_item('1.0.0.127.in-addr.arpa', types.PTR, self.name)
        self.add_item('localhost', types.A, '127.0.0.1')

    def add_item(self, key, qtype, data):
        self.add_host(Record(name = key, data = data, qtype = qtype, ttl = -1))

    def add_root_servers(self):
        for item in get_root_servers():
            self.add_item(*item)
