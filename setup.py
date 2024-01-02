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
        "cachetools>=4.1.1",
        "mistune<2.0.0",  # v2 is totally incompatible with unclear benefit
        "requests>=2.25.0",
        "python-json-logger>=2.0.1",
        "Flask>=2.1.1",
        "ordered-set>=4.1.0",
        "Jinja2>=2.11.3",
        "statsd>=3.3.0",
        "Flask-Redis>=0.4.0",
        "pyyaml>=5.3.1",
        "phonenumbers>=8.13.18",
        "pytz>=2020.4",
        "smartypants>=2.0.1",
        "pypdf>=3.9.0",
        "itsdangerous>=1.1.0",
        "govuk-bank-holidays>=0.10,<1.0",
        "boto3>=1.19.4",
        "segno>=1.5.2,<2.0.0",
    ],
)
