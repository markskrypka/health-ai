"""Nearest site: where the caller is, how far each clinic is in a straight line, and how to get there.

The organizers rank by straight-line distance to the published site coordinates and choose origins "so the
winner wins by a clear margin" — so a town or a landmark is as good as a house number, and a caller's street
may arrive mangled by speech-to-text. Order of trust: a town outside the city named in the text, then the
street through OpenStreetMap, then a district or landmark from the list below.
"""

import math
import re
import unicodedata

import httpx

_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_HEADERS = {"User-Agent": "clinic-agent-hackspain/0.1"}

# Towns around Madrid: naming one settles the question on its own.
_TOWNS = {
    "getafe": (40.3057, -3.7329), "leganes": (40.3280, -3.7635), "alcorcon": (40.3459, -3.8249),
    "mostoles": (40.3223, -3.8650), "fuenlabrada": (40.2842, -3.7942), "parla": (40.2360, -3.7675),
    "pinto": (40.2415, -3.6999), "valdemoro": (40.1908, -3.6742), "aranjuez": (40.0333, -3.6028),
    "rivas": (40.3420, -3.5180), "arganda": (40.3008, -3.4382), "alcobendas": (40.5475, -3.6420),
    "san sebastian de los reyes": (40.5474, -3.6261), "tres cantos": (40.6009, -3.7080),
    "colmenar viejo": (40.6590, -3.7676), "pozuelo": (40.4350, -3.8130), "majadahonda": (40.4730, -3.8720),
    "las rozas": (40.4930, -3.8740), "boadilla": (40.4050, -3.8760), "coslada": (40.4240, -3.5610),
    "san fernando de henares": (40.4250, -3.5320), "torrejon": (40.4590, -3.4790), "alcala de henares": (40.4820, -3.3640),
}
# Districts and landmarks inside the city, for when the street cannot be placed.
_PLACES = {
    "plaza de castilla": (40.4663, -3.6897), "chamartin": (40.4615, -3.6766), "tetuan": (40.4605, -3.6980),
    "fuencarral": (40.4955, -3.6935), "hortaleza": (40.4745, -3.6410), "barajas": (40.4736, -3.5790),
    "las tablas": (40.5060, -3.6700), "sanchinarro": (40.4920, -3.6540), "nuevos ministerios": (40.4460, -3.6920),
    "bernabeu": (40.4530, -3.6883), "cuatro caminos": (40.4470, -3.7040), "alberto alcocer": (40.4645, -3.6836),
    "puerta del sol": (40.4169, -3.7035), "gran via": (40.4200, -3.7050), "plaza mayor": (40.4155, -3.7074),
    "callao": (40.4200, -3.7058), "opera": (40.4180, -3.7095), "atocha": (40.4066, -3.6900), "retiro": (40.4153, -3.6845),
    "lavapies": (40.4088, -3.7010), "la latina": (40.4110, -3.7110), "malasana": (40.4260, -3.7040),
    "chueca": (40.4230, -3.6975), "chamberi": (40.4340, -3.7030), "barrio de salamanca": (40.4300, -3.6780),
    "moncloa": (40.4350, -3.7190), "arguelles": (40.4300, -3.7150), "principe pio": (40.4210, -3.7200),
    "arganzuela": (40.3980, -3.6980), "legazpi": (40.3910, -3.6950), "usera": (40.3810, -3.7070),
    "carabanchel": (40.3742, -3.7440), "villaverde": (40.3456, -3.7095), "vallecas": (40.3797, -3.6210),
    "aluche": (40.3920, -3.7600), "ciudad lineal": (40.4480, -3.6500), "moratalaz": (40.4070, -3.6450),
    "vicalvaro": (40.4040, -3.6060), "san blas": (40.4330, -3.6150), "canillejas": (40.4440, -3.6080),
    "sol": (40.4169, -3.7035), "city centre": (40.4168, -3.7038), "city center": (40.4168, -3.7038),
    "the centre": (40.4168, -3.7038), "the center": (40.4168, -3.7038), "downtown": (40.4168, -3.7038),
    "el centro": (40.4168, -3.7038),
}
_STREET = re.compile(r"\b(calle|paseo|avenida|avda|plaza|ronda|carretera|camino|glorieta|travesia|street|avenue|square)\b")
_TAIL = re.compile(r",|\s(?:by|at|near|next to|beside|junto a|cerca de|al lado de|in|en)\s")
_COMPASS = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]


def _fold(text: str) -> str:
    plain = "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", plain.lower()).strip()


def _named(places: dict, folded: str) -> tuple[float, float] | None:
    hits = [name for name in places if re.search(rf"\b{re.escape(name)}\b", folded)]
    return places[max(hits, key=len)] if hits else None


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


def directions(lat: float, lon: float, site: dict) -> str:
    """How to get to a site from where the caller is, from the two coordinates alone: distance, compass
    direction and rough journey times. The caller only needs an answer — 'I do not know' ends the call."""
    km = haversine_km(lat, lon, site["latitude"], site["longitude"])
    bearing = math.degrees(math.atan2(math.radians(site["longitude"] - lon) * math.cos(math.radians(lat)),
                                      math.radians(site["latitude"] - lat))) % 360
    heading = _COMPASS[round(bearing / 45) % 8]
    where = f'{site["name"]} is at {site["address"]}'
    if km < 1.5:
        return f"{where}, about {max(round(km * 1000, -2), 100):.0f} metres {heading} of you: around {max(round(km * 13), 3)} minutes on foot."
    return (f"{where}, about {km:.0f} kilometres {heading} of you: around {max(round(km * 2.5), 8)} minutes by car or taxi, "
            f"or about {max(round(km * 4.5), 15)} by metro, Cercanías train or bus. Any maps app will take you to that address.")


async def _search(client: httpx.AsyncClient, **params: str) -> tuple[float, float] | None:
    try:
        resp = await client.get(_NOMINATIM, params={"format": "jsonv2", "limit": 1, "countrycodes": "es", **params})
        resp.raise_for_status()
        hits = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    return (float(hits[0]["lat"]), float(hits[0]["lon"])) if hits else None


async def geocode(address: str) -> tuple[float, float] | None:
    """Where the caller is → (lat, lon), or None when nothing in what they said can be placed."""
    folded = _fold(address)
    town = _named(_TOWNS, folded)
    if town:
        return town
    street = _TAIL.split(address, maxsplit=1)[0].strip()
    if _STREET.search(_fold(street)):
        number = re.search(r"\b\d{1,4}\b", street)
        name = re.sub(r"\b\d{1,4}\b", "", street).strip(" ,.")
        async with httpx.AsyncClient(timeout=4.0, headers=_HEADERS) as client:
            for query in ({"street": f"{number.group()} {name}" if number else name, "city": "Madrid"}, {"q": f"{name}, Madrid"}):
                found = await _search(client, **query)
                if found and haversine_km(*found, 40.4168, -3.7038) < 40:  # a street of that name somewhere else in Spain is no answer
                    return found
    return _named(_PLACES, folded)
