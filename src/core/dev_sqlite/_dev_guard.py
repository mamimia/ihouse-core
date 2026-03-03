import os

if os.environ.get("IHOUSE_ALLOW_SQLITE") != "1":
    raise RuntimeError(
        "core.dev_sqlite is a development adapter. "
        "Set IHOUSE_ALLOW_SQLITE=1 to enable."
    )
