# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

.PHONY: help test lint format check type-check clean pre-commit-setup pre-commit-run

VENV_DIR := .venv
VENV_BIN := $(VENV_DIR)/bin
MARKER_DIR := $(VENV_DIR)/markers

# Marker file constants
INSTALL := $(MARKER_DIR)/install
INSTALL_DEV := $(MARKER_DIR)/install-dev
INSTALL_TESTS := $(MARKER_DIR)/install-tests
INSTALL_ALL := $(MARKER_DIR)/install-all

# Default target
help:
	@echo "OARepo CLI - Available targets:"
	@echo ""
	@echo "  Installation:"
	@echo "    install-dev    - Install package with dev dependencies (ruff, ty, pre-commit)"
	@echo "    install-tests  - Install package with test dependencies (pytest, pytest-cov)"
	@echo "    install-all    - Install package with all dependencies"
	@echo ""
	@echo "  Development:"
	@echo "    test           - Run pytest with coverage"
	@echo "    lint           - Run ruff linter"
	@echo "    format         - Format code with ruff"
	@echo "    check          - Run all checks (lint + format + type-check)"
	@echo "    type-check     - Run ty type checker"
	@echo ""
	@echo "  Pre-commit:"
	@echo "    pre-commit-setup - Install pre-commit hooks"
	@echo "    pre-commit-run   - Run pre-commit on all files"
	@echo ""
	@echo "  Cleanup:"
	@echo "    clean          - Remove build artifacts, cache directories, and virtualenv"

# Virtual environment creation with uv (includes marker directory)
$(VENV_DIR):
	uv venv $(VENV_DIR)
	mkdir -p $(MARKER_DIR)

# Installation targets (marker files as prerequisites)
$(INSTALL): $(VENV_DIR)
	uv pip install -e .
	touch $@

$(INSTALL_DEV): $(INSTALL)
	uv pip install -e ".[dev]"
	touch $@

$(INSTALL_TESTS): $(INSTALL)
	uv pip install -e ".[tests]"
	touch $@

$(INSTALL_ALL): $(VENV_DIR)
	uv pip install -e ".[dev,tests]"
	touch $@

# Installation targets
install-dev: $(INSTALL_DEV)

install-tests: $(INSTALL_TESTS)

install-all: $(INSTALL_ALL)

# Development targets
test: install-tests
	$(VENV_BIN)/pytest

lint: install-dev
	$(VENV_BIN)/ruff check .

format: install-dev
	$(VENV_BIN)/ruff format .

check: lint format type-check
	@echo "All checks passed!"

type-check: install-dev
	$(VENV_BIN)/ty check --python-version 3.14 .

clean:
	rm -rf build/ dist/ *.egg-info/ .eggs/
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -rf htmlcov/ .coverage coverage.xml
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.py[cod]" -delete 2>/dev/null || true
	find . -type f -name "*$$py.class" -delete 2>/dev/null || true
	rm -rf $(VENV_DIR)

# Pre-commit targets
pre-commit-setup: install-dev
	$(VENV_BIN)/pre-commit install

pre-commit-run: install-dev
	$(VENV_BIN)/pre-commit run --all-files
