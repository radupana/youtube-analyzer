# Python project automation - similar to Maven/Gradle tasks
# Usage: make <command>

.PHONY: help install dev clean format lint type test test-cov run build pre-commit

# Default target - show help
help:
	@echo "YouTube Analyzer - Development Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install      Install production dependencies"
	@echo "  make dev          Install development dependencies + pre-commit hooks"
	@echo ""
	@echo "Code Quality:"
	@echo "  make format       Auto-format code (black + isort)"
	@echo "  make lint         Run linters (ruff + mypy)"
	@echo "  make type         Type-check with mypy"
	@echo "  make check        Run all checks (format check + lint + type)"
	@echo ""
	@echo "Testing:"
	@echo "  make test         Run tests"
	@echo "  make test-cov     Run tests with coverage report"
	@echo ""
	@echo "Build & Run:"
	@echo "  make run          Run the CLI tool"
	@echo "  make build        Build distribution packages"
	@echo "  make clean        Remove build artifacts and cache"
	@echo ""
	@echo "Git Hooks:"
	@echo "  make pre-commit   Run pre-commit on all files"

# Install production dependencies
install:
	pip install -e .

# Install dev dependencies and pre-commit hooks
dev:
	pip install -e ".[dev]"
	pip install isort pre-commit
	pre-commit install
	@echo "✅ Development environment ready!"
	@echo "Pre-commit hooks installed - will auto-format on commit"

# Format code with black and isort
format:
	@echo "🎨 Formatting code..."
	isort src/ tests/
	black src/ tests/
	@echo "✅ Code formatted!"

# Check if code is formatted (CI mode)
format-check:
	@echo "📋 Checking code format..."
	isort --check-only src/ tests/
	black --check src/ tests/

# Run linter
lint:
	@echo "🔍 Running linter..."
	ruff check src/ tests/

# Run type checker
type:
	@echo "🔎 Type checking..."
	mypy src/

# Run all checks
check: format-check lint type
	@echo "✅ All checks passed!"

# Run tests
test:
	@echo "🧪 Running tests..."
	pytest

# Run tests with coverage
test-cov:
	@echo "🧪 Running tests with coverage..."
	pytest --cov=src --cov-report=term-missing --cov-report=html
	@echo "📊 Coverage report: htmlcov/index.html"

# Run the CLI tool
run:
	@python -m yt_agent_kit

# Build distribution packages
build:
	@echo "📦 Building packages..."
	pip install build
	python -m build
	@echo "✅ Packages built in dist/"

# Clean build artifacts
clean:
	@echo "🧹 Cleaning..."
	rm -rf build/ dist/ *.egg-info .coverage htmlcov/ .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✅ Clean!"

# Run pre-commit on all files
pre-commit:
	pre-commit run --all-files
