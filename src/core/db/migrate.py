from __future__ import annotations
import runpy

# Shim module. Keeps python -m core.db.migrate working.
if __name__ == "__main__":
    runpy.run_module("core.dev_sqlite.migrate", run_name="__main__")

# Also expose symbols if callers import them.
from core.dev_sqlite.migrate import *  # noqa: F401,F403,E402
