"""
Python API client for GOV.UK Notify
"""
import re
import ast
from setuptools import setup, find_packages


_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('notifications_utils/version.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))

setup(
    name='notifications-utils',
    version=version,
    url='https://github.com/alphagov/notifications-utils',
    license='MIT',
    author='Government Digital Service',
    description='Shared python code for GOV.UK Notify.',
    long_description=__doc__,
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'bleach==3.1.0',
        'mistune==0.8.4',
        'requests==2.21.0',
        'python-json-logger==0.1.10',
        'Flask>=0.12.2',
        'orderedset==2.0.1',
        'Jinja2==2.10',
        'statsd==3.3.0',
        'Flask-Redis==0.3.0',
        'pyyaml==3.13',
        'phonenumbers==8.10.5',
        'pytz==2018.9',
        'smartypants==2.0.1',
        'monotonic==1.5',
        'pypdf2==1.26.0',

        # required by both api and admin
        'awscli==1.15.79',
        'boto3==1.6.16',
    ]
)
