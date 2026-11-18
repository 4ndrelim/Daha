"""Which country a store search is in, worked out on our server (C6, plans/LOCATION.md).

- From coordinates: the country of the nearest town with 15,000+ people (GeoNames data in
  data/country_points.csv.gz, CC BY 4.0, rebuilt by scripts/build_location_data.py). It runs
  offline, so a location never goes anywhere extra for this.
- From a typed place: US ZIP codes and states first (DAHA is for US colleges first), then common
  country names. Anything else stays unknown, and the place's words do the work in the query.
- Typed coordinates ("1.30, 103.85") and US ZIPs (data/us_zip_points.csv.gz, same source) become
  a real location, so people who keep location services off can still say where they are.
- The local currency, so prices rank and show the way people there read them.
"""

import gzip
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

DATA = Path(__file__).parent / "data" / "country_points.csv.gz"
ZIPS = Path(__file__).parent / "data" / "us_zip_points.csv.gz"
EARTH_KM = 6371.0
MAX_KM = 300.0  # farther than this from any town counts as "at sea": no country

# fmt: off
US_STATES = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas", "CA": "california",
    "CO": "colorado", "CT": "connecticut", "DE": "delaware", "DC": "district of columbia",
    "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho", "IL": "illinois",
    "IN": "indiana", "IA": "iowa", "KS": "kansas", "KY": "kentucky", "LA": "louisiana",
    "ME": "maine", "MD": "maryland", "MA": "massachusetts", "MI": "michigan", "MN": "minnesota",
    "MS": "mississippi", "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico", "NY": "new york",
    "NC": "north carolina", "ND": "north dakota", "OH": "ohio", "OK": "oklahoma", "OR": "oregon",
    "PA": "pennsylvania", "RI": "rhode island", "SC": "south carolina", "SD": "south dakota",
    "TN": "tennessee", "TX": "texas", "UT": "utah", "VT": "vermont", "VA": "virginia",
    "WA": "washington", "WV": "west virginia", "WI": "wisconsin", "WY": "wyoming",
    "PR": "puerto rico",
}
COUNTRY_NAMES = {
    "us": "US", "usa": "US", "united states": "US", "america": "US",
    "canada": "CA", "mexico": "MX", "uk": "GB", "united kingdom": "GB", "england": "GB",
    "scotland": "GB", "wales": "GB", "ireland": "IE", "france": "FR", "germany": "DE",
    "spain": "ES", "italy": "IT", "netherlands": "NL", "switzerland": "CH", "japan": "JP",
    "china": "CN", "hong kong": "HK", "taiwan": "TW", "korea": "KR", "south korea": "KR",
    "singapore": "SG", "malaysia": "MY", "thailand": "TH", "vietnam": "VN", "philippines": "PH",
    "indonesia": "ID", "india": "IN", "australia": "AU", "new zealand": "NZ", "brazil": "BR",
    "uae": "AE", "united arab emirates": "AE", "israel": "IL",
}
CURRENCY_BY_COUNTRY = {
    "US": "USD", "PR": "USD", "GU": "USD", "VI": "USD", "CA": "CAD", "MX": "MXN", "GB": "GBP",
    "IE": "EUR", "FR": "EUR", "DE": "EUR", "ES": "EUR", "IT": "EUR", "NL": "EUR", "BE": "EUR",
    "PT": "EUR", "AT": "EUR", "FI": "EUR", "GR": "EUR", "LU": "EUR", "CH": "CHF", "SE": "SEK",
    "NO": "NOK", "DK": "DKK", "PL": "PLN", "CZ": "CZK", "JP": "JPY", "CN": "CNY", "HK": "HKD",
    "TW": "TWD", "KR": "KRW", "SG": "SGD", "MY": "MYR", "TH": "THB", "VN": "VND", "PH": "PHP",
    "ID": "IDR", "IN": "INR", "AU": "AUD", "NZ": "NZD", "AE": "AED", "IL": "ILS", "TR": "TRY",
    "BR": "BRL", "AR": "ARS", "CL": "CLP", "CO": "COP", "ZA": "ZAR",
}
# fmt: on
_US_ZIP = re.compile(r"^\d{5}(?:-\d{4})?$")
_TRAILING_ZIP = re.compile(r"(\d{5})(?:-\d{4})?$")
_COORDS = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*[,\s]\s*(-?\d{1,3}(?:\.\d+)?)\s*$")


@lru_cache(maxsize=1)
def _points() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lats: list[float] = []
    lngs: list[float] = []
    codes: list[str] = []
    with gzip.open(DATA, "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            lat, lng, code = line.rstrip("\n").split(",")
            lats.append(float(lat))
            lngs.append(float(lng))
            codes.append(code)
    return np.radians(lats), np.radians(lngs), np.array(codes)


def country_for(lat: float, lng: float) -> str | None:
    """ISO country code of the nearest town, or None far out at sea."""
    lats, lngs, codes = _points()
    p, q = np.radians(lat), np.radians(lng)
    h = np.sin((lats - p) / 2) ** 2 + np.cos(p) * np.cos(lats) * np.sin((lngs - q) / 2) ** 2
    i = int(np.argmin(h))
    km = 2 * EARTH_KM * float(np.arcsin(np.sqrt(h[i])))
    return str(codes[i]) if km <= MAX_KM else None


def place_country(place: str) -> str | None:
    """A typed town or ZIP → a country when we can tell: "94040", "Berkeley, CA", "Kyoto, Japan"."""
    text = " ".join(place.lower().replace(",", " , ").split())
    if _US_ZIP.match(text):
        return "US"
    last = text.split(",")[-1].strip()  # "berkeley , ca" → "ca"
    if last in COUNTRY_NAMES:
        return COUNTRY_NAMES[last]
    words = last.split()
    tail = words[-1] if words else ""
    if (tail.upper() in US_STATES and len(text.split(",")) > 1) or last in US_STATES.values():
        return "US"
    if len(words) > 1 and tail.upper() in US_STATES and tail.upper() != "IN":
        return "US"  # "Austin TX", without a comma ("in" is a word, not Indiana)
    if text in COUNTRY_NAMES:
        return COUNTRY_NAMES[text]
    return None


def parse_coordinates(text: str) -> tuple[float, float] | None:
    """ "1.30, 103.85" or "37.43 -122.17" → (lat, lng); anything else → None."""
    m = _COORDS.match(text)
    if not m:
        return None
    lat, lng = float(m.group(1)), float(m.group(2))
    return (lat, lng) if -90 <= lat <= 90 and -180 <= lng <= 180 else None


@lru_cache(maxsize=1)
def _zips() -> dict[str, tuple[float, float]]:
    zips: dict[str, tuple[float, float]] = {}
    with gzip.open(ZIPS, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.startswith("#"):
                code, lat, lng = line.rstrip("\n").split(",")
                zips[code] = (float(lat), float(lng))
    return zips


def us_zip_point(place: str) -> tuple[float, float] | None:
    """Where a typed US ZIP is: "94305", "94305-1234", or "Stanford, CA 94305".

    A ZIP after other words only counts when the words say US (a state, "USA"), so a French
    "Paris 75001" isn't taken for Texas's 75001.
    """
    text = place.strip()
    if _US_ZIP.match(text):
        return _zips().get(text[:5])
    m = _TRAILING_ZIP.search(text)
    if m and place_country(text[: m.start()].strip(" ,")) == "US":
        return _zips().get(m.group(1))
    return None


def local_currency(country: str | None) -> str:
    """The currency prices there are in; US dollars when we can't tell (US colleges first)."""
    return CURRENCY_BY_COUNTRY.get(country or "", "USD")
