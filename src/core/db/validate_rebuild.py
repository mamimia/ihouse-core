from __future__ import annotations
import runpy

# This module is used both as "python -m core.db.validate_rebuild"
# and as an import source for snapshot_fingerprints.py.
if __name__ == "__main__":
    runpy.run_module("core.dev_sqlite.validate_rebuild", run_name="__main__")

from core.dev_sqlite.validate_rebuild import *  # noqa: F401,F403,E402
