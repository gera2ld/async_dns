import socket
from urllib.parse import urlparse
from . import types, InternetProtocol

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

class Address:
    def __init__(self, host, port, ip_type, protocol):
        self.host = host
        self.port = port
        self.ip_type = ip_type
        if protocol is not None:
            protocol = InternetProtocol.get(protocol)
        self.protocol = protocol

    def __eq__(self, other):
        return self.host == other.host and self.port == other.port

    def __repr__(self):
        return self.to_str()

    def __hash__(self):
        return hash(self.to_addr())

    def copy(self):
        return Address(self.host, self.port, self.ip_type, self.protocol)

    def to_str(self, default_port = 0):
        if default_port is None or self.port == default_port:
            return self.host
        host = self.host if self.ip_type is types.AAAA else '[' + self.host + ']'
        protocol = self.protocol or '-'
        return f'{protocol}//{host}:{self.port}'

    def to_addr(self):
        return self.host, self.port

    def to_ptr(self):
        if self.ip_type is types.A:
            return '.'.join(reversed(self.host.split('.'))) + '.in-addr.arpa'
        raise InvalidIP(self.host)

    @classmethod
    def parse(cls, value, default_port=0, default_protocol=None, allow_domain=False):
        if isinstance(value, Address):
            return value.copy()
        if '://' in value:
            data = urlparse(value)
            host, port, protocol = (data.hostname or ''), (data.port or default_port), (data.scheme or default_protocol)
        elif value.count(':') == 1 or '[' in value:
            data = Host(value)
            host, port, protocol = data.hostname, data.port, default_protocol
        else:
            host, port, protocol = value, default_port, default_protocol
        if ':' in host:
            # ipv6
            try:
                socket.inet_pton(socket.AF_INET6, host)
            except OSError:
                raise InvalidHost(host)
            ip_type = types.AAAA
        else:
            # ipv4 or domain name
            try:
                socket.inet_pton(socket.AF_INET, host)
            except OSError:
                if not allow_domain:
                    raise InvalidHost(host)
                ip_type = None
            else:
                ip_type = types.A
        return Address(host, port, ip_type, protocol)
