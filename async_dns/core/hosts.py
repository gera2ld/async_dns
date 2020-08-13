import os
from .address import Address
from .record import Record

if os.name == 'nt':
    hosts_file = os.path.expandvars(r'%windir%\System32\drivers\etc\hosts')
elif os.name == 'posix':
    hosts_file = '/etc/hosts'
else:
    hosts_file = None

def parse_hosts_file(filename=None):
    if filename is None: filename = hosts_file
    filename = os.path.expanduser(filename)
    if not os.path.isfile(filename):
        return
    with open(filename, 'r') as f:
        for line in f:
            items = line.strip().split('#')[0].split()
            try:
                it = iter(items)
                addr = Address.parse(next(it))
            except StopIteration:
                pass
            else:
                for name in it:
                    yield Record(name=name, qtype=addr.ip_type, ttl=-1, data=addr.hostinfo.hostname)
