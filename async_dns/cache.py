'''
Cache module.
'''

import os
from . import logger, types, hosts, Record

__all__ = ['DNSMemCache']
CACHE_FILE = os.path.expanduser('~/.async_dns/named.cache.txt')

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
