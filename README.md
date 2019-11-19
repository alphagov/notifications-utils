# GOV.UK Notify - notifications-utils

Shared python code for GOV.UK Notify, such as logging utils etc.

## Installing

This is a Python 3 application.

    brew install python3

We recommend using [VirtualEnvWrapper](http://virtualenvwrapper.readthedocs.org/en/latest/command_ref.html) for managing your virtual environments.

    mkvirtualenv -p /usr/local/bin/python3 notifications-utils

    pip install -r requirements_for_test.txt

## Tests

The `./scripts/run_tests.sh` script will run all the tests.

## Documentation

Documentation for the template used to render emails is in the [docs](./docs/README.md) folder.
