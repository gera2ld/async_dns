#!python
# coding=utf-8
from setuptools import setup, find_packages

setup(
    name='async_dns',
    version='1.0.0',
    description='Asynchronous DNS client and server',
    long_description='Asynchronous DNS client and server written in pure Python, based on asyncio.',
    url='https://github.com/gera2ld/async_dns',
    author='Gerald',
    author_email='i@gerald.top',
    license='MIT',
    classifiers=[
        'Development Status :: 6 - Mature',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3 :: Only',
    ],
    keywords='async dns asyncio',
    packages=find_packages(exclude=['tests']),
)
