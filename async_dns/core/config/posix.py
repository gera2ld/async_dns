'''
This module load nameservers from posix resolv.conf.
'''
from pathlib import Path


def get_nameservers(filename='/etc/resolv.conf'):
    '''
    Load nameservers from resolv.conf file.
    '''
    nameservers = []
    for line in Path(filename).read_text().splitlines():
        if line.startswith('#'):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        if parts[0] == 'nameserver':
            nameservers.append(parts[1])
    return nameservers
