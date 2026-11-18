"""Build app/discovery/data/country_points.csv.gz: where towns are, and which country they're in.

    cd backend && uv run python scripts/build_country_points.py

Downloads GeoNames' cities15000 (every town with 15,000+ people, about 33,000 places) and keeps
only latitude, longitude (rounded to 0.01°, about 1 km) and the country code. The store search
uses it to tell Exa which country a location is in, without sending the location anywhere else.

Data: GeoNames (https://www.geonames.org), licensed CC BY 4.0. Run again to refresh it.
"""

import gzip
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://download.geonames.org/export/dump/cities15000.zip"
OUT = Path(__file__).resolve().parents[1] / "app" / "discovery" / "data" / "country_points.csv.gz"


def main() -> None:
    with urllib.request.urlopen(URL, timeout=60) as resp:
        archive = zipfile.ZipFile(io.BytesIO(resp.read()))
    rows: set[tuple[float, float, str]] = set()
    with archive.open("cities15000.txt") as raw:
        for line in io.TextIOWrapper(raw, encoding="utf-8"):
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 9 or len(cols[8]) != 2:
                continue
            rows.add((round(float(cols[4]), 2), round(float(cols[5]), 2), cols[8].upper()))
    if len(rows) < 10_000:
        sys.exit(f"Only {len(rows)} places found; the download looks wrong, nothing written.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8", compresslevel=9) as out:
        out.write(
            "# lat,lng,country. From GeoNames cities15000 (https://www.geonames.org), CC BY 4.0.\n"
        )
        out.write("# Rebuild: cd backend && uv run python scripts/build_country_points.py\n")
        for lat, lng, cc in sorted(rows):
            out.write(f"{lat:.2f},{lng:.2f},{cc}\n")
    print(f"Wrote {len(rows)} places to {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
