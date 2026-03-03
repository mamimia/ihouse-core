from core.db._sqlite_guard import require_sqlite_enabled

require_sqlite_enabled()

from core.dev_sqlite.outbox_worker import *  # noqa: F401,F403
