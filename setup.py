#!python
# coding=utf-8
from setuptools import setup, find_packages

setup(
    name='pydns',
    version='1.0',
    packages=find_packages(exclude=['test']),
    author='Gerald',
    author_email='i@gerald.top',
    description='DNS client and server written in Python, based on asyncio.',
    url='https://github.com/gera2ld/pydns',
)
