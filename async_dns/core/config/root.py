'''
Cache module.
'''

import os
import json
from .. import logger, types, Record

__all__ = [
    'core_config',
    'get_name_cache',
    'get_root_servers',
]

CONFIG_DIR = os.environ.get('ASYNC_DNS_CONFIG_DIR', os.path.expanduser('~/.config/async_dns'))
os.makedirs(CONFIG_DIR, exist_ok=True)
CACHE_FILE = os.path.join(CONFIG_DIR, 'named.cache.txt')

try:
    user_config = json.load(open(os.path.join(CONFIG_DIR, 'config.json')))
except:
    user_config = None
core_config = {
    'default_nameservers': [
        '8.8.8.8',
        '8.8.4.4',
    ],
}
if user_config is not None:
    core_config.update(user_config)
    del user_config

def get_nameservers():
    return []

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
        get_name_cache(filename=filename)
    # in case failed fetching named.cache
    if not os.path.isfile(filename):
        return
    for line in open(filename, 'r'):
        if line.startswith(';'):
            continue
        parts = line.lower().split()
        if len(parts) < 4:
            continue
        yield Record(
            name=parts[0].rstrip('.'),   # name
            # parts[1] (expires) is ignored
            qtype=types.get_code(parts[2], 0),   # qtype
            data=parts[3].rstrip('.'),   # data
            ttl=-1,
        )
