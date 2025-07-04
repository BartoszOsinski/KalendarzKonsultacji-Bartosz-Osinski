# Makefile for Flask project

# Default shell
SHELL := /bin/bash

# Docker compose command
DC ?= exec

# TTY setting for CI
TTY := $(if $(shell tty -s || echo no),,"-T")

# Helper function to run docker compose
define dc
	docker compose $(DC) $(TTY) $(1)
endef

.PHONY: all cmd flask lint lint-dockerfile format format-imports quality test test-coverage shell psql redis-cli pip-install pip-outdated yarn-install yarn-outdated yarn-build-js yarn-build-css clean ci-install-deps ci-test help

all: help

cmd:
	$(call dc,web $(filter-out $@,$(MAKECMDGOALS)))

flask:
	$(call dc,web flask $(filter-out $@,$(MAKECMDGOALS)))

lint:
	$(call dc,web flake8 $(filter-out $@,$(MAKECMDGOALS)))

lint-dockerfile:
	docker container run --rm -i hadolint/hadolint hadolint --ignore DL3008 -t style - < Dockerfile

format-imports:
	$(call dc,web isort . $(filter-out $@,$(MAKECMDGOALS)))

format:
	$(call dc,web black . $(filter-out $@,$(MAKECMDGOALS)))

quality: format-imports format lint

test:
	$(call dc,web pytest test/ $(filter-out $@,$(MAKECMDGOALS)))

test-coverage:
	$(call dc,web pytest --cov test/ --cov-report term-missing $(filter-out $@,$(MAKECMDGOALS)))

shell:
	$(call dc,web bash $(filter-out $@,$(MAKECMDGOALS)))

psql:
	$(eval include .env)
	$(call dc,postgres psql -U "$(POSTGRES_USER)" $(filter-out $@,$(MAKECMDGOALS)))

redis-cli:
	$(call dc,redis redis-cli $(filter-out $@,$(MAKECMDGOALS)))

pip-install:
	docker compose build
	docker compose run $(TTY) web bin/pip3-install
	docker compose down
	docker compose up -d

pip-outdated:
	$(call dc,web pip3 list --outdated)

yarn-install:
	docker compose build
	docker compose run $(TTY) js yarn install
	docker compose down

yarn-outdated:
	$(call dc,js yarn outdated)

yarn-build-js:
	mkdir -p ../public/js
	node esbuild.config.mjs

yarn-build-css:
	mkdir -p ../public/css
	tailwindcss --postcss -i css/app.css -o ../public/css/app.css $(if $(filter production,$(NODE_ENV)),--minify,--watch)

clean:
	rm -rf public/*.* public/js public/css public/images public/fonts .pytest_cache/ .coverage celerybeat-schedule
	touch public/.keep

ci-install-deps:
	sudo apt-get install -y curl shellcheck
	sudo curl -L https://raw.githubusercontent.com/nickjj/wait-until/v0.2.0/wait-until -o /usr/local/bin/wait-until && sudo chmod +x /usr/local/bin/wait-until

ci-test: lint-dockerfile
	cp --no-clobber .env.example .env
	docker compose build
	docker compose up -d
	$(eval include .env)
	wait-until "docker compose exec -T -e POSTGRES_PASSWORD=$(POSTGRES_PASSWORD) postgres psql -U $(POSTGRES_USER) $(POSTGRES_USER) -c 'SELECT 1'"
	docker compose logs
	$(MAKE) lint format-imports format test

# New command to add a package and update requirements.txt
add-package:
	@read -p "Enter package name: " package; \
	$(call dc,web pip install $$package); \
	$(call dc,web pip freeze > requirements.txt); \
	echo "Package $$package installed and requirements.txt updated."

help:
	@echo "Available targets:"
	@awk '/^[a-zA-Z\-\_0-9]+:/ { \
		helpMessage = match(lastLine, /^# (.*)/); \
		if (helpMessage) { \
			helpCommand = substr($$1, 0, index($$1, ":")-1); \
			helpMessage = substr(lastLine, RSTART + 2, RLENGTH); \
			printf "\033[36m%-30s\033[0m %s\n", helpCommand, helpMessage; \
		} \
	} \
	{ lastLine = $$0 }' $(MAKEFILE_LIST)

# This allows us to accept extra arguments
%:
	@: