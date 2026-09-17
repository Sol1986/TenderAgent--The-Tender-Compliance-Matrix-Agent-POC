.PHONY: check test integration verify-phase

check:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest tests/unit/

integration:
	uv run pytest tests/integration/

verify-phase: check test integration