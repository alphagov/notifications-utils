# GOV.UK Notify - notifications-utils

Shared Python code for GOV.UK Notify applications. Standardises how to do logging, rendering message templates, parsing spreadsheets, talking to external services and more.

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
