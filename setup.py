import setuptools


def long_description():
    with open('README.md', 'r') as file:
        return file.read()


setuptools.setup(
    name='aiogethostbyname',
    version='0.0.0',
    description='aiogethostbyname',
    long_description=long_description(),
    long_description_content_type='text/markdown',
    url='https://github.com/michalc/aiogethostbyname',
    author='Gerald',
    author_email='i@gerald.top',
    license='MIT',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3 :: Only',
    ],
    keywords='async dns asyncio',
    test_suite='test',
    packages=setuptools.find_packages(exclude=['tests']),
)
