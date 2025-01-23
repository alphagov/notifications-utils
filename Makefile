.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help
help:
	@cat $(MAKEFILE_LIST) | grep -E '^[a-zA-Z_-]+:.*?## .*$$' | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: freeze-requirements
freeze-requirements: ## Pin all test requirements including sub dependencies into requirements_for_test.txt
	pip install --upgrade pip-tools
	pip-compile requirements_for_test.in setup.py --output-file requirements_for_test.txt

.PHONY: bootstrap
bootstrap: ## Build project
	pip install -r requirements_for_test.txt
	pip install -e .

.PHONY: test
test: ## Run tests
	ruff check .
	ruff format --check .
	pytest -n auto
	python setup.py sdist

.PHONY: watch-tests
watch-tests: ## Automatically rerun tests
	ptw --runner "pytest --testmon -n auto"

clean:
	rm -rf cache venv

.PHONY: fix-imports
fix-imports:
	ruff --fix --select=I ./notifications_utils ./tests

.PHONY: reset-version
reset-version:
	git fetch
	git checkout origin/main -- notifications_utils/version.py

.PHONY: version-major
version-major: reset-version ## Update the major version number
	./scripts/bump_version.py major

.PHONY: version-minor
version-minor: reset-version ## Update the minor version number
	./scripts/bump_version.py minor

.PHONY: version-patch
version-patch: reset-version ## Update the patch version number
	./scripts/bump_version.py patch
