#!/usr/bin/env bash

# Get the directory name
PACKAGE_NAME=$(basename "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")

uv sync --extra dev

uv run python -m pip install -e .

uv run python -m ipykernel install --user --name "$PACKAGE_NAME" --display-name "$PACKAGE_NAME"
