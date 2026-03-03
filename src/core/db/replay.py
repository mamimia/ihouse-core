from __future__ import annotations
import runpy

if __name__ == "__main__":
    runpy.run_module("core.dev_sqlite.replay", run_name="__main__")

from core.dev_sqlite.replay import *  # noqa: F401,F403,E402
