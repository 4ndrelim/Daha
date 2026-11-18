"""Build the offline location data the store search uses (C6, app/discovery/countries.py).

    cd backend && uv run python scripts/build_location_data.py

Writes two small files in app/discovery/data/, both from GeoNames (https://www.geonames.org),
licensed CC BY 4.0. Run again to refresh them.
- country_points.csv.gz: every town with 15,000+ people (cities15000): latitude, longitude
  (rounded to 0.01°, about 1 km) and country code. Tells Exa which country a location is in.
- us_zip_points.csv.gz: every US ZIP code with its latitude and longitude (rounded the same way).
  A typed ZIP becomes a real location, not just words in the query.
"""

import gzip
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "app" / "discovery" / "data"
CITIES = "https://download.geonames.org/export/dump/cities15000.zip"
US_ZIPS = "https://download.geonames.org/export/zip/US.zip"
CREDIT = "From GeoNames (https://www.geonames.org), CC BY 4.0."
REBUILD = "Rebuild: cd backend && uv run python scripts/build_location_data.py"


def download(url: str, member: str) -> list[list[str]]:
    with urllib.request.urlopen(url, timeout=60) as resp:
        archive = zipfile.ZipFile(io.BytesIO(resp.read()))
    with archive.open(member) as raw:
        return [line.rstrip("\n").split("\t") for line in io.TextIOWrapper(raw, encoding="utf-8")]


def write(name: str, header: str, rows: list[str], minimum: int) -> None:
    if len(rows) < minimum:
        sys.exit(f"Only {len(rows)} rows for {name}; the download looks wrong, nothing written.")
    path = DATA / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as out:
        out.write(f"# {header}. {CREDIT}\n# {REBUILD}\n")
        out.writelines(f"{row}\n" for row in rows)
    print(f"Wrote {len(rows)} rows to {path} ({path.stat().st_size // 1024} KB)")


def main() -> None:
    towns = {
        (round(float(c[4]), 2), round(float(c[5]), 2), c[8].upper())
        for c in download(CITIES, "cities15000.txt")
        if len(c) > 8 and len(c[8]) == 2
    }
    write(
        "country_points.csv.gz",
        "lat,lng,country",
        [f"{lat:.2f},{lng:.2f},{cc}" for lat, lng, cc in sorted(towns)],
        10_000,
    )
    zips: dict[str, tuple[float, float]] = {}
    for c in download(US_ZIPS, "US.txt"):
        if len(c) > 10 and len(c[1]) == 5 and c[1].isdigit() and c[9] and c[10]:
            zips.setdefault(c[1], (round(float(c[9]), 2), round(float(c[10]), 2)))
    write(
        "us_zip_points.csv.gz",
        "zip,lat,lng",
        [f"{z},{lat:.2f},{lng:.2f}" for z, (lat, lng) in sorted(zips.items())],
        30_000,
    )


if __name__ == "__main__":
    main()
