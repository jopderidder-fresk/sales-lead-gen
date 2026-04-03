#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema to a JSON file.

Usage:
    python -m scripts.export_openapi              # writes to ../openapi.json
    python -m scripts.export_openapi output.json  # writes to output.json

This does NOT start the server — it imports the app and calls
``app.openapi()`` directly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the backend package is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402


def main() -> None:
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent.parent / "openapi.json"
    schema = app.openapi()
    dest.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"OpenAPI schema written to {dest}")


if __name__ == "__main__":
    main()
