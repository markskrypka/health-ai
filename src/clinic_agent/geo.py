"""Nearest site: straight-line distance to the published site coordinates."""

import math

import httpx

_NOMINATIM = "https://nominatim.openstreetmap.org/search"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def sites_by_distance(lat: float, lon: float, locations: list[dict]) -> list[dict]:
    """Locations ordered nearest first, each with its distance in km."""
    ranked = [
        {**loc, "distance_km": round(haversine_km(lat, lon, loc["latitude"], loc["longitude"]), 2)}
        for loc in locations
    ]
    return sorted(ranked, key=lambda loc: loc["distance_km"])


async def geocode(address: str) -> tuple[float, float] | None:
    """Street address in the Madrid area → (lat, lon), or None when it cannot be placed."""
    params = {"q": f"{address}, Comunidad de Madrid, España", "format": "jsonv2", "limit": 1, "countrycodes": "es"}
    headers = {"User-Agent": "clinic-agent-hackspain/0.1"}
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(_NOMINATIM, params=params, headers=headers)
            resp.raise_for_status()
            hits = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not hits:
        return None
    return float(hits[0]["lat"]), float(hits[0]["lon"])
