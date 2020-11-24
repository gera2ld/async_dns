import socket
from urllib.parse import urlparse
from . import types

__all__ = [
    'Host',
    'Address',
    'InvalidHost',
    'InvalidIP',
]

class Host:
    def __init__(self, netloc):
        if isinstance(netloc, Host):
            hostname, port, username, password = netloc.hostname, netloc.port, netloc.username, netloc.password
        elif isinstance(netloc, str):
            userinfo, _, host = netloc.rpartition('@')
            if host.count(':') == 1 or '[' in host:
                hostname, _, port = host.rpartition(':')
                port = int(port)
            else:
                hostname, port = host, None
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
        host = f'[{self.hostname}]' if ':' in self.hostname else self.hostname
        if self.port:
            host = f'{host}:{self.port}'
        return host

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
        path = self.path or ''
        return f'{protocol}://{host}{path}'

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

    default_ports = {
        'tcp': 53,
        'udp': 53,
        'tcps': 853,
        'https': 443,
    }

    @classmethod
    def parse(cls, value, default_protocol=None, allow_domain=False):
        if isinstance(value, Address):
            return value.copy()
        if '://' not in value:
            value = '//' + value
        data = urlparse(value, scheme=default_protocol or 'udp')
        hostinfo = Host(data.netloc)
        if hostinfo.port is None:
            hostinfo.port = cls.default_ports.get(data.scheme, 53)
        addr = Address(hostinfo, data.scheme, data.path)
        if not allow_domain and addr.ip_type is None:
            raise InvalidHost(hostinfo.hostname)
        return addr
