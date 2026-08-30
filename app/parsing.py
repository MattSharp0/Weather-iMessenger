import re

_COORD_RE = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*[,\s]\s*(-?\d+(?:\.\d+)?)\s*$"
)


def parse_coordinates(text: str) -> tuple[float, float] | None:
    """Parse 'lat,lon' or 'lat lon' decimal degrees. Returns None if invalid."""
    match = _COORD_RE.match(text)
    if not match:
        return None

    lat, lon = float(match.group(1)), float(match.group(2))
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None

    return lat, lon
