from io import TextIOWrapper
import os
from typing import Union

from .address import Address

if os.name == 'nt':
    hosts_file = os.path.expandvars(r'%windir%\System32\drivers\etc\hosts')
elif os.name == 'posix':
    hosts_file = '/etc/hosts'
else:
    hosts_file = None


def _parse_lines(fd: TextIOWrapper):
    for line in fd:
        items = line.strip().split('#')[0].split()
        try:
            it = iter(items)
            addr = Address.parse(next(it))
        except StopIteration:
            pass
        else:
            for name in it:
                if isinstance(addr.ip_type, int):
                    yield name, addr.ip_type, (addr.hostinfo.hostname, )


def parse_hosts_file(fd: Union[str, TextIOWrapper] = None):
    if fd is None:
        fd = hosts_file
    try:
        if isinstance(fd, str):
            fd = os.path.expanduser(fd)
            with open(fd, 'r', encoding='utf-8-sig') as f:
                yield from _parse_lines(f)
        else:
            yield from _parse_lines(fd)
    except:
        pass
