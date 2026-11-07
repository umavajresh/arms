import logging

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


def normalize_flight_code(code):
    return (code or "").strip().upper().replace(" ", "")


class LiveFlightProvider:
    name = ""

    def lookup(self, flight_code):
        raise NotImplementedError


class AviationStackProvider(LiveFlightProvider):
    name = "aviationstack"
    endpoint = "http://api.aviationstack.com/v1/flights"
    timeout = 10

    def lookup(self, flight_code):
        api_key = settings.ARMS_AVIATIONSTACK_API_KEY
        if not api_key:
            return None
        try:
            response = requests.get(
                self.endpoint,
                params={"access_key": api_key, "flight_iata": flight_code},
                timeout=self.timeout,
            )
            response.raise_for_status()
            records = (response.json() or {}).get("data") or []
        except (requests.RequestException, ValueError):
            logger.exception("AviationStack lookup failed for %s", flight_code)
            return None
        return self._parse(records[0], flight_code) if records else None

    def _parse(self, item, flight_code):
        flight = item.get("flight") or {}
        airline = item.get("airline") or {}
        departure = item.get("departure") or {}
        arrival = item.get("arrival") or {}
        live = item.get("live") or {}
        return {
            "flight_code": (
                flight.get("iata") or flight.get("icao") or flight_code or ""
            ).upper(),
            "airline": airline.get("name") or "Unknown airline",
            "from_code": (departure.get("iata") or departure.get("icao") or "").upper(),
            "from_name": departure.get("airport") or "Unknown origin",
            "to_code": (arrival.get("iata") or arrival.get("icao") or "").upper(),
            "to_name": arrival.get("airport") or "Unknown destination",
            "departure": departure.get("scheduled")
            or departure.get("estimated")
            or departure.get("actual"),
            "arrival": arrival.get("scheduled")
            or arrival.get("estimated")
            or arrival.get("actual"),
            "status": item.get("flight_status") or item.get("status") or "Unknown",
            "latitude": live.get("latitude"),
            "longitude": live.get("longitude"),
            "altitude": live.get("altitude"),
            "speed_horizontal": live.get("speed_horizontal"),
            "updated_at": live.get("updated") or timezone.now().isoformat(),
            "source": self.name,
        }


class OpenSkyProvider(LiveFlightProvider):
    name = "opensky"
    endpoint = "https://opensky-network.org/api/states/all"
    timeout = 8
    cache_key = "arms:opensky:states"
    cache_seconds = 15
    unavailable_cache_seconds = 60
    callsign_index = 1
    longitude_index = 5
    latitude_index = 6
    altitude_index = 7
    velocity_index = 9

    def lookup(self, flight_code):
        code = normalize_flight_code(flight_code)
        if not code:
            return None
        for state in self._states():
            match = self._parse(state, code)
            if match:
                return match
        return None

    def _states(self):
        states = cache.get(self.cache_key)
        if states is None:
            states = self._download_states()
            lifetime = self.cache_seconds if states else self.unavailable_cache_seconds
            cache.set(self.cache_key, states, lifetime)
        return states

    def _download_states(self):
        try:
            response = requests.get(self.endpoint, timeout=self.timeout)
            response.raise_for_status()
            return (response.json() or {}).get("states") or []
        except (requests.RequestException, ValueError):
            logger.exception("OpenSky states download failed")
            return []

    def _parse(self, state, code):
        if len(state) <= self.velocity_index:
            return None
        callsign = normalize_flight_code(state[self.callsign_index])
        if not callsign or (callsign != code and not callsign.startswith(code)):
            return None
        latitude = state[self.latitude_index]
        longitude = state[self.longitude_index]
        if latitude is None or longitude is None:
            return None
        return {
            "flight_code": code,
            "airline": "OpenSky Network",
            "from_code": "",
            "from_name": "Live airspace position",
            "to_code": "",
            "to_name": "Live tracking data",
            "departure": None,
            "arrival": None,
            "status": "Live airborne",
            "latitude": latitude,
            "longitude": longitude,
            "altitude": state[self.altitude_index],
            "speed_horizontal": state[self.velocity_index],
            "updated_at": timezone.now().isoformat(),
            "source": self.name,
            "progress": 50,
        }


class LiveFlightLookup:
    def __init__(self, providers=None):
        self.providers = providers or [AviationStackProvider(), OpenSkyProvider()]

    def find(self, flight_code):
        for provider in self.providers:
            result = provider.lookup(flight_code)
            if result:
                return result
        return None
