# notifications-utils

Shared Python code for GOV.UK Notify applications. Standardises how to do logging, rendering message templates, parsing spreadsheets, talking to external services and more.

## Setting up

### Python version

This repo is written in Python 3.

### Pre-commit

We use [pre-commit](https://pre-commit.com/) to ensure that committed code meets basic standards for formatting, and will make basic fixes for you to save time and aggravation.

Install pre-commit system-wide with, eg `brew install pre-commit`. Then, install the hooks in this repository with `pre-commit install --install-hooks`.

## To test the library

```
# install dependencies, etc.
make bootstrap

# run the tests
make test
```

## Publishing a new version

Versioning should be done by running the `make version-[type of change]` command, following [semantic versioning](https://semver.org/). For example

```
make version-patch
```

Include a short summary (sentence or two) about the changes you've made in `CHANGELOG.md`. Please do this even if you're only making a minor or patch version change.
