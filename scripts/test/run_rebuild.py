import os
import runpy

os.environ.setdefault("IHOUSE_ALLOW_SQLITE", "1")
runpy.run_path("scripts/dev/run_sqlite_rebuild.py", run_name="__main__")
