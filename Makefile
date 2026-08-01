# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

.PHONY: help install install-dev install-tests test lint format check type-check clean pre-commit-setup pre-commit-run

# Default target
help:
	@echo "OARepo CLI - Available targets:"
	@echo ""
	@echo "  Installation:"
	@echo "    install        - Install package with minimal dependencies"
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
	@echo "    clean          - Remove build artifacts and cache directories"

# Installation targets
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

install-tests:
	pip install -e ".[tests]"

install-all:
	pip install -e ".[dev,tests]"

# Development targets
test:
	pytest

lint:
	ruff check .

format:
	ruff format .

check: lint format type-check
	@echo "All checks passed!"

type-check:
	ty check --python-version 3.14 .

clean:
	rm -rf build/ dist/ *.egg-info/ .eggs/
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -rf htmlcov/ .coverage coverage.xml
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.py[cod]" -delete 2>/dev/null || true
	find . -type f -name "*$$py.class" -delete 2>/dev/null || true

# Pre-commit targets
pre-commit-setup:
	pre-commit install

pre-commit-run:
	pre-commit run --all-files
