.PHONY: install verify test pack serve hunt clean

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
STUMP ?= .venv/bin/stump
PYTEST ?= .venv/bin/pytest

.venv:
	python3 -m venv .venv

install: .venv
	$(PIP) install -e ".[dev]"

test: install
	$(PYTEST) -q

pack: install
	$(STUMP) pack

verify: test pack
	@echo "verify ok"

serve: pack
	$(STUMP) serve --host 127.0.0.1 --port 8765

hunt: install
	$(STUMP) hunt --year-start 1880 --year-end 1895 --limit 10 -v

clean:
	rm -rf data/hunt_index.json .pytest_cache src/*.egg-info *.egg-info
