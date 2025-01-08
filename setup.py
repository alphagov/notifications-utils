"""
Python API client for GOV.UK Notify
"""

import ast
import re

from setuptools import find_packages, setup

_version_re = re.compile(r"__version__\s+=\s+(.*)")

with open("notifications_utils/version.py", "rb") as f:
    version = str(ast.literal_eval(_version_re.search(f.read().decode("utf-8")).group(1)))

setup(
    name="notifications-utils",
    version=version,
    url="https://github.com/alphagov/notifications-utils",
    license="MIT",
    author="Government Digital Service",
    description="Shared python code for GOV.UK Notify.",
    long_description=__doc__,
    packages=find_packages(exclude=("tests",)),
    include_package_data=True,
    install_requires=[
        "cachetools>=5.5.0",
        "mistune<2.0.0",  # v2 is totally incompatible with unclear benefit
        "requests>=2.32.2",  # Can’t go past 2.32.2 until https://github.com/psf/requests/issues/6730 is fixed
        "python-json-logger>=2.0.7",
        "Flask>=3.1.0",
        "gunicorn[eventlet]>=20.1.0",
        "ordered-set>=4.1.0",
        "Jinja2>=3.1.5",
        "statsd>=4.0.1",
        "Flask-Redis>=0.4.0",
        "pyyaml>=6.0.2",
        "phonenumbers>=8.13.50",
        "pytz>=2024.2",
        "smartypants>=2.0.1",
        "pypdf>=3.13.0",
        "itsdangerous>=2.2.0",
        "govuk-bank-holidays>=0.15",
        "boto3[crt]>=1.34.100",
        "segno>=1.6.1",
    ],
)
