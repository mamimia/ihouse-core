from typing import Dict

from .base import OTAAdapter
from .bookingcom import BookingComAdapter
from .expedia import ExpediaAdapter
from .airbnb import AirbnbAdapter
from .agoda import AgodaAdapter
from .tripcom import TripComAdapter
from .vrbo import VrboAdapter
from .gvr import GVRAdapter
from .traveloka import TravelokaAdapter
from .makemytrip import MakemytripAdapter
from .klook import KlookAdapter
from .despegar import DespegarAdapter
from .hotelbeds import HotelbedsAdapter
from .rakuten import RakutenAdapter
from .hostelworld import HostelworldAdapter  # Phase 195: Hostelworld global hostel OTA


_ADAPTERS: Dict[str, OTAAdapter] = {
    "bookingcom": BookingComAdapter(),
    "expedia": ExpediaAdapter(),
    "airbnb": AirbnbAdapter(),
    "agoda": AgodaAdapter(),
    "tripcom": TripComAdapter(),
    "ctrip":   TripComAdapter(),          # Phase 238: Ctrip alias (same adapter, China market)
    "vrbo": VrboAdapter(),
    "gvr": GVRAdapter(),
    "traveloka": TravelokaAdapter(),
    "makemytrip": MakemytripAdapter(),
    "klook": KlookAdapter(),
    "despegar": DespegarAdapter(),
    "hotelbeds": HotelbedsAdapter(),
    "rakuten":   RakutenAdapter(),    # Phase 187: Japan market
    "hostelworld": HostelworldAdapter(),
}


def get_adapter(channel: str) -> OTAAdapter:
    adapter = _ADAPTERS.get(channel)

    if not adapter:
        raise ValueError("unsupported_channel")

    return adapter
