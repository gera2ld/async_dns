from .udp import Dispatcher
from .util import ConnectionPool


def clean():
    Dispatcher.data.clear()
    ConnectionPool.destroy_all()
