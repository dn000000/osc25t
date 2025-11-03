# Makefile for sysaudit project

.PHONY: help install install-dev test test-unit test-integration test-compliance test-fast test-coverage test-html clean lint format check

# Default target
help:
	@echo "Sysaudit Development Commands"
	@echo "=============================="
	@echo ""
	@echo "Installation:"
	@echo "  make install          Install package"
	@echo "  make install-dev      Install package with dev dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests"
	@echo "  make test-unit        Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make test-compliance  Run compliance tests only"
	@echo "  make test-fast        Run tests, skip slow ones"
	@echo "  make test-coverage    Run tests with coverage report"
	@echo "  make test-html        Run tests with HTML coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             Run linting checks"
	@echo "  make format           Format code with black"
	@echo "  make check            Run all checks (lint + test)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Remove build artifacts and cache files"

# Installation targets
install:
	pip install -e .

install-dev:
	pip install -e .[dev]

# Testing targets
test:
	python run_tests.py

test-unit:
	python run_tests.py --unit

test-integration:
	python run_tests.py --integration

test-compliance:
	python run_tests.py --compliance

test-fast:
	python run_tests.py --fast

test-coverage:
	python run_tests.py --coverage

test-html:
	python run_tests.py --html-coverage
	@echo "Coverage report generated in htmlcov/index.html"

# Code quality targets
lint:
	@echo "Running flake8..."
	-flake8 sysaudit tests --max-line-length=88 --extend-ignore=E203,W503
	@echo ""
	@echo "Running mypy..."
	-mypy sysaudit --ignore-missing-imports

format:
	@echo "Formatting code with black..."
	black sysaudit tests

check: lint test
	@echo "All checks passed!"

# Cleanup targets
clean:
	@echo "Cleaning up..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete
	@echo "Cleanup complete!"

# Development workflow
dev: install-dev
	@echo "Development environment ready!"
	@echo "Run 'make test' to run tests"
	@echo "Run 'make help' to see all available commands"
