"""Nominatim from geopy helper."""

import asyncio
from dataclasses import dataclass, fields
import logging

from geopy.adapters import AioHTTPAdapter
from geopy.exc import GeocoderRateLimited
from geopy.geocoders import Nominatim
from geopy.location import Location

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import (
    SERVER_SOFTWARE,
    async_get_clientsession,
)

NOMINATIM_DATA = "sharable_nominatim"
TIMEOUT = 10
INITIAL_WAIT = 1.5
CACHE_SIZE = 25

_LOGGER = logging.getLogger(__name__)


@dataclass
class NomData:
    """Nomination data."""

    cache: dict[str, Location | None]
    lock: asyncio.Lock
    nominatim: Nominatim
    wait: float


def _save_nom_data(hass: HomeAssistant, nom_data: NomData) -> None:
    """Save nominatim data to hass.data."""
    hass.data[NOMINATIM_DATA] = {
        field.name: getattr(nom_data, field.name) for field in fields(nom_data)
    }


def init_nominatim(hass: HomeAssistant) -> bool:
    """Initialize sharable Nominatim object."""
    if NOMINATIM_DATA in hass.data:
        nom_data = hass.data[NOMINATIM_DATA]
        try:
            for field in fields(NomData):
                if not isinstance(nom_data[field.name], field.type):
                    raise TypeError
        except (KeyError, TypeError):
            msg = f"Unexpected data in hass.data[{NOMINATIM_DATA!r}]: {nom_data}"
            _LOGGER.error(msg)
            return False
        return True

    nominatim = Nominatim(
        user_agent=SERVER_SOFTWARE,
        timeout=TIMEOUT,
        adapter_factory=lambda proxies, ssl_context: AioHTTPAdapter(
            proxies=proxies, ssl_context=ssl_context
        ),
    )
    nominatim.adapter.__dict__["session"] = async_get_clientsession(hass)

    _save_nom_data(hass, NomData({}, asyncio.Lock(), nominatim, INITIAL_WAIT))
    _LOGGER.debug("Initialized Nominatim data with cache size = %i", CACHE_SIZE)
    return True


async def get_location(hass: HomeAssistant, lat: float, lng: float) -> Location | None:
    """Get location data from given coordinates."""
    nom_data = NomData(**hass.data[NOMINATIM_DATA])

    async def limit_rate() -> None:
        """Hold the lock to limit calls to server."""
        await asyncio.sleep(nom_data.wait)
        nom_data.lock.release()

    coordinates = f"{lat}, {lng}"
    await nom_data.lock.acquire()
    try:
        return await nom_data.nominatim.reverse(coordinates)
    except GeocoderRateLimited as exc:
        if retry_after := exc.retry_after:
            if retry_after > nom_data.wait:
                _LOGGER.debug("Increasing wait time to %f sec", retry_after)
                nom_data.wait = retry_after
                _save_nom_data(hass, nom_data)
        _LOGGER.warning("Request has been rate limited. Will retry")
        return await get_location(hass, lat, lng)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        _LOGGER.error("While retrieving reverse geolocation data: %s", exc)
        return None
    finally:
        hass.async_create_background_task(limit_rate(), "Limit nominatim query rate")
