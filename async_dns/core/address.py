import socket
from urllib.parse import urlparse
from . import types

__all__ = [
    'Host',
    'Address',
    'InvalidHost',
    'InvalidIP',
    'InvalidNameServer',
]

class Host:
    def __init__(self, netloc):
        if isinstance(netloc, Host):
            hostname, port, username, password = netloc.hostname, netloc.port, netloc.username, netloc.password
        elif isinstance(netloc, str):
            userinfo, _, hostinfo = netloc.rpartition('@')
            hostname, _, port = hostinfo.rpartition(':')
            port = int(port)
            if hostname.startswith('[') and hostname.endswith(']'):
                hostname = hostname[1:-1]
            if userinfo:
                username, _, password = userinfo.partition(':')
            else:
                username = password = None
        elif len(netloc) == 2:
            hostname, port = netloc
            username = password = None
        else:
            hostname, port, username, password = netloc
        self.hostname, self.port, self.username, self.password = hostname, port, username, password

    @property
    def host(self):
        hostname = f'[{self.hostname}]' if ':' in self.hostname else self.hostname
        return f'{hostname}:{self.port}'

    def __str__(self):
        userinfo = ''
        if self.username:
            userinfo += self.username
            if self.password:
                userinfo += ':' + self.password
            userinfo += '@'
        return userinfo + self.host

class InvalidHost(Exception):
    pass

class InvalidIP(Exception):
    pass

class InvalidNameServer(Exception):
    pass

def get_ip_type(hostname):
    if ':' in hostname:
        # ipv6
        try:
            socket.inet_pton(socket.AF_INET6, hostname)
        except OSError:
            raise InvalidHost(hostname)
        return types.AAAA
    # ipv4 or domain name
    try:
        socket.inet_pton(socket.AF_INET, hostname)
    except OSError:
        # domain name
        pass
    else:
        return types.A

class Address:
    def __init__(self, hostinfo, protocol, path=None):
        self.hostinfo = hostinfo
        self.protocol = protocol
        self.path = path
        self.ip_type = get_ip_type(self.hostinfo.hostname)

    def __str__(self):
        protocol = self.protocol or '-'
        host = self.hostinfo.host
        return f'{protocol}://{host}'

    def __eq__(self, other):
        return str(self) == str(other)

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash(str(self))

    def copy(self):
        return Address(Host(self.hostinfo), self.protocol, self.path)

    def to_addr(self):
        return self.hostinfo.hostname, self.hostinfo.port

    def to_ptr(self):
        if self.ip_type is types.A:
            return '.'.join(reversed(self.hostinfo.hostname.split('.'))) + '.in-addr.arpa'
        raise InvalidIP(self.hostinfo.hostname)

    @classmethod
    def parse(cls, value, default_port=0, default_protocol=None, allow_domain=False):
        if isinstance(value, Address):
            return value.copy()
        if '://' not in value:
            value = '//' + value
        data = urlparse(value, scheme=default_protocol or 'udp')
        netloc = data.netloc
        if netloc.count(':') == 1 or '[' in netloc:
            hostinfo = Host(netloc)
        else:
            hostinfo = Host((netloc, default_port))
        addr = Address(hostinfo, data.scheme, data.path)
        if not allow_domain:
            assert addr.ip_type, InvalidHost(hostinfo.hostname)
        return addr
