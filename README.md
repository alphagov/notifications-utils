# notifications-utils

Shared Python code for GOV.UK Notify applications. Standardises how to do logging, rendering message templates, parsing spreadsheets, talking to external services and more.

## Setting up

### Python version

This repo is written in Python 3.

### uv

We use [uv](https://github.com/astral-sh/uv) for Python dependency management. Follow the [install instructions](https://github.com/astral-sh/uv?tab=readme-ov-file#installation) or run:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Pre-commit

We use [pre-commit](https://pre-commit.com/) to ensure that committed code meets basic standards for formatting, and will make basic fixes for you to save time and aggravation.

Install pre-commit system-wide with, eg `brew install pre-commit`. Then, install the hooks in this repository with `pre-commit install --install-hooks`.

### Redis

We use a real [Redis](https://redis.io/) instance to test `notifications_utils.redis_client.RedisClient`. You can either [install locally with brew](https://redis.io/docs/latest/operate/oss_and_stack/install/archive/install-redis/install-redis-on-mac-os/) or [run inside a docker container](https://hub.docker.com/_/redis).

The unit test fixture uses `FLUSHALL` every single time it is called. To prevent this from having unexpected side effects with a locally running redis instance (*e.g.* notifications-local) the tests expect redis to run on port 6999. In docker simply change the port mapping flag to `-p 6999:6379`. If running outside a container add the flag `--port 6999`.

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


## Updating utils version in apps
App repos should be updated with the latest version of `notifications-utils` where possible. The repos to update are API, Admin, Document Download, Document Download Frontend, Template Preview, Email Stub.

To do this in the app repo: 
- Ensure npm, py uv is installed and you're using Python 3.11
- Run `make bootstrap`
- Run `make bump-utils`
- Run `make freeze-requirements`
- Commit with the recommended message and raise a PR. 