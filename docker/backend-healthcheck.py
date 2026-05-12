#!/usr/bin/env python3
"""Backend Docker healthcheck with useful failure diagnostics.

Docker stores healthcheck output in `docker inspect`, but many deployment UIs
only surface container logs. On failure this script also writes a short message
to PID 1 stderr so the reason appears in backend logs.
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request


URL = os.environ.get("BACKEND_HEALTHCHECK_URL", "http://localhost:8000/health/deep")
TIMEOUT = float(os.environ.get("BACKEND_HEALTHCHECK_TIMEOUT", "8"))
MAX_BODY_CHARS = 500


def _write_container_log(message: str) -> None:
    line = f"[healthcheck] {message}\n"
    try:
        with open("/proc/1/fd/2", "a", encoding="utf-8") as proc_stderr:
            proc_stderr.write(line)
    except OSError:
        pass
    print(line, file=sys.stderr, end="")


def main() -> int:
    try:
        with urllib.request.urlopen(URL, timeout=TIMEOUT) as response:
            body = response.read(MAX_BODY_CHARS).decode("utf-8", errors="replace")
            status = getattr(response, "status", 200)
            if status >= 400:
                _write_container_log(f"{URL} returned HTTP {status}: {body}")
                return 1
            return 0
    except urllib.error.HTTPError as exc:
        body = exc.read(MAX_BODY_CHARS).decode("utf-8", errors="replace")
        _write_container_log(f"{URL} returned HTTP {exc.code}: {body}")
        return 1
    except urllib.error.URLError as exc:
        _write_container_log(f"cannot reach {URL}: {exc.reason}")
        return 1
    except Exception as exc:
        _write_container_log(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
