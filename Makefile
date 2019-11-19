.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help
help:
	@cat $(MAKEFILE_LIST) | grep -E '^[a-zA-Z_-]+:.*?## .*$$' | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: venv
venv: venv/bin/activate ## Create virtualenv if it does not exist

venv/bin/activate:
	test -d venv || virtualenv venv

.PHONY: dependencies
dependencies: venv ## Install build dependencies
	./venv/bin/pip install -r requirements_for_test.txt

.PHONY: build
build: dependencies ## Build project

.PHONY: test
test: venv ## Run tests
	./scripts/run_tests.sh

clean:
	rm -rf cache venv
