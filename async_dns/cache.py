'''
Cache module.
'''

import os
from . import logger, types, hosts, Record

__all__ = ['DNSMemCache']
CACHE_FILE = os.path.expanduser('~/.async_dns/named.cache.txt')

def get_name_cache(
        url='ftp://rs.internic.net/domain/named.cache',
        filename=CACHE_FILE, timeout=10):
    '''
    Download root nameservers and save cache.
    '''
    from urllib import request
    logger.info('Fetching named.cache...')
    try:
        res = request.urlopen(url, timeout=timeout)
    except:
        logger.warning('Error fetching named.cache')
    else:
        open(filename, 'wb').write(res.read())

def get_root_servers(filename=CACHE_FILE):
    '''
    Load root servers from cache.
    '''
    if not os.path.isfile(filename):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        get_name_cache(filename=filename)
    # in case failed fetching named.cache
    if not os.path.isfile(filename):
        return
    for line in open(filename, 'r'):
        if line.startswith(';'):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        yield [
            parts[0].rstrip('.'),   # name
            # parts[1] (expires) is ignored
            types.get_code(parts[2], 0),   # qtype
            parts[3].rstrip('.'),   # data
        ]

class DNSMemCache(hosts.Hosts):
    '''
    Memory cache for DNS.
    '''
    name = 'DNSMemD/async_dns'

    def __init__(self, filename=None):
        super().__init__(filename)
        self.add_item('1.0.0.127.in-addr.arpa', types.PTR, self.name)
        self.add_item('localhost', types.A, '127.0.0.1')

    def add_item(self, name, qtype, data):
        '''
        Add an item to cache.
        '''
        self.add_host(Record(name=name, data=data, qtype=qtype, ttl=-1))

    def add_root_servers(self):
        '''
        Load root servers from cache file and add them to memory cache.
        '''
        for item in get_root_servers():
            self.add_item(*item)
