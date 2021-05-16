from .udp import Dispatcher
from .util import ConnectionPool


def clean():
    ConnectionPool.destroy_all()
    Dispatcher.destroy_all()
