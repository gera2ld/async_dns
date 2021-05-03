import time
from typing import Dict, Iterable, Union

from async_dns.core.record import RData

from . import types
from .record import Record

__all__ = ['CacheNode']


class CacheValue:
    def __init__(self):
        self.data: Dict[int, Dict[RData, Record]] = {}

    def check_ttl(self, record: Record):
        return record.ttl < 0 or record.timestamp + record.ttl >= time.time()

    def get(self, qtype: int) -> Iterable[Record]:
        if qtype == types.ANY:
            for qt in self.data.keys():
                yield from self.get(qt)
            return
        results = self.data.get(qtype)
        if results is not None:
            keys = list(results.keys())
            for key in keys:
                record = results[key]
                if self.check_ttl(record):
                    yield record
                else:
                    results.pop(key, None)

    def add(self, record: Record):
        if self.check_ttl(record):
            results = self.data.setdefault(record.qtype, {})
            results[record.data] = record


class CacheNode:
    def __init__(self):
        self.children: Dict[str, CacheNode] = {}
        self.data = CacheValue()

    def get(self, fqdn: str, touch: bool = False):
        current = self
        keys = reversed(fqdn.split('.'))
        for key in keys:
            child = current.children.get(key)
            if child is None:
                child = current.children.get('*')
            if child is None:
                if not touch: return
                child = CacheNode()
                current.children[key] = child
            current = child
        return current.data

    def query(self, fqdn: str, qtype: Union[int, Iterable[int]]):
        if isinstance(qtype, int):
            value = self.get(fqdn)
            if value is not None:
                yield from value.get(qtype)
        else:
            for t in qtype:
                yield from self.query(fqdn, t)

    def add(self,
            fqdn: str = None,
            qtype: int = None,
            data=None,
            ttl=-1,
            record: Record = None):
        if record is None:
            assert fqdn is not None
            assert qtype is not None
            assert data is not None
            record = Record(name=fqdn, data=data, qtype=qtype, ttl=ttl)
        value = self.get(record.name, True)
        value.add(record)

    def iter_values(self) -> Iterable[Record]:
        '''Yield all cached values in this node and its subtree.'''
        yield from self.data.get(types.ANY)
        for child in self.children.values():
            yield from child.iter_values()
