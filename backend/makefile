.PHONY: format lint typecheck test ci clean ensure-networks

# Ensure shared external networks exist before starting the Compose stacks.
ensure-networks:
	@for network in my-storage-net my-kafka-net; do \
		if docker network inspect $$network >/dev/null 2>&1; then \
			echo "Docker network '$$network' already exists"; \
		else \
			docker network create $$network; \
		fi; \
	done

# Automatically format code and sort imports
format:
	uv run ruff check --fix .
	uv run ruff format .

# Check for lint issues without modifying files (used in CI)
lint:
	uv run ruff check .

# Run static type checking via ty
typecheck:
	uv run ty check

# Run pytest unit and integration tests
test:
	uv run pytest

# Local developer check: formats, lints, typechecks, and tests
check: format lint typecheck test
	@echo "✨ All local checks passed successfully!"

# CI pipeline check: validates everything without mutating files, then runs tests
ci: lint typecheck test
	@echo "🚀 CI pipeline validation passed successfully!"

# Clean up build caches, pycache, and virtual environments
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
