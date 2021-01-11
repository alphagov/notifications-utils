.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help
help:
	@cat $(MAKEFILE_LIST) | grep -E '^[a-zA-Z_-]+:.*?## .*$$' | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: dependencies
dependencies: ## Install build dependencies
	pip install -r requirements_for_test.txt

.PHONY: build
build: dependencies ## Build project

.PHONY: test
test: ## Run tests
	./scripts/run_tests.sh

clean:
	rm -rf cache venv

.PHONY: fix-imports
fix-imports:
	isort -rc ./notifications_utils ./tests
