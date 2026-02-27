from __future__ import annotations

import signal
import sys
import time
from typing import Optional

from core.db.outbox_worker import process_once


class OutboxDaemon:
    def __init__(self, interval_seconds: int = 5) -> None:
        self.running = True
        self.interval = max(1, int(interval_seconds))

        signal.signal(signal.SIGINT, self._stop)
        signal.signal(signal.SIGTERM, self._stop)

    def _stop(self, *args) -> None:
        print("[OUTBOX] shutdown signal received", flush=True)
        self.running = False

    def run(self) -> None:
        print(f"[OUTBOX] daemon started interval={self.interval}s", flush=True)

        while self.running:
            try:
                sent, failed = process_once()
                if sent or failed:
                    print(f"[OUTBOX] batch sent={sent} failed={failed}", flush=True)

                # sleep in small steps so SIGTERM feels instant
                for _ in range(self.interval * 2):
                    if not self.running:
                        break
                    time.sleep(0.5)

            except Exception as e:
                print(f"[OUTBOX] ERROR {e!r}", file=sys.stderr, flush=True)
                time.sleep(self.interval)


def main() -> None:
    interval = 5
    try:
        # optional: IHOUSE_OUTBOX_INTERVAL_SEC
        import os
        interval = int(os.getenv("IHOUSE_OUTBOX_INTERVAL_SEC", "5"))
    except Exception:
        interval = 5

    OutboxDaemon(interval_seconds=interval).run()


if __name__ == "__main__":
    main()
