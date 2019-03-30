'''
Cache module.
'''

import os
from . import logger, types, hosts, Record

__all__ = ['DNSMemCache']

class DNSMemCache(hosts.Hosts):
    '''
    Memory cache for DNS.
    '''
    name = 'DNSMemD/async_dns'

    def __init__(self):
        super().__init__()
        self.add_item('localhost', types.A, '127.0.0.1')

    def add_item(self, name, qtype, data):
        '''
        Add an item to cache.
        '''
        self.add_host(Record(name=name, data=data, qtype=qtype, ttl=-1))
