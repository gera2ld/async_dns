import asyncio
import sys
import random
from .address import Address

__all__ = [
    'NameServers',
    'NoNameServer',
]

class NoNameServer(Exception):
    pass

class IterMixIn:
    def __init__(self, *k, **kw):
        self._timers = set()
        self._activated = []
        self._disabled = set()
        self._update()

    def _update(self):
        self._activated = [item for item in self.data if item not in self._disabled]

    def get(self):
        if not self._activated: raise NoNameServer
        return random.choice(self._activated)

    def success(self, item):
        pass

    def fail(self, item):
        def clear():
            self._disabled.discard(item)
            self._timers.discard(handle)
            self._update()
        self._disabled.add(item)
        self._update()
        loop = asyncio.get_event_loop()
        handle = loop.call_later(1, clear)
        self._timers.add(handle)

class NameServers(IterMixIn):
    def __init__(self, nameservers=[], **kw):
        self.data = [Address.parse(item, default_protocol='udp', allow_domain=True) for item in nameservers]
        super().__init__(**kw)

    def __bool__(self):
        return len(self.data) > 0

    def __iter__(self):
        return iter(self.data)

    def __repr__(self):
        return '<NameServers [%s]>' % ','.join(map(str, self.data))
