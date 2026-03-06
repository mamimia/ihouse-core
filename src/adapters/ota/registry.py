from typing import Dict

from .base import OTAAdapter
from .bookingcom import BookingComAdapter


_ADAPTERS: Dict[str, OTAAdapter] = {
    "bookingcom": BookingComAdapter(),
}


def get_adapter(channel: str) -> OTAAdapter:

    adapter = _ADAPTERS.get(channel)

    if not adapter:
        raise ValueError("unsupported_channel")

    return adapter
