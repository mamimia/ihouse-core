from typing import Dict

from .base import OTAAdapter
from .bookingcom import BookingComAdapter
from .expedia import ExpediaAdapter


_ADAPTERS: Dict[str, OTAAdapter] = {
    "bookingcom": BookingComAdapter(),
    "expedia": ExpediaAdapter(),
}


def get_adapter(channel: str) -> OTAAdapter:
    adapter = _ADAPTERS.get(channel)

    if not adapter:
        raise ValueError("unsupported_channel")

    return adapter
