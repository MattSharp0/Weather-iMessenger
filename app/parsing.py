import re

_COORD_RE = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*[,\s]\s*(-?\d+(?:\.\d+)?)\s*$"
)

FORECAST_OPTIONS = {"forecast", "tonight", "tomorrow"}


def parse_coordinates(text: str) -> tuple[float, float] | None:
    """Parse 'lat,lon' or 'lat lon' decimal degrees. Returns None if invalid."""
    match = _COORD_RE.match(text)
    if not match:
        return None

    lat, lon = float(match.group(1)), float(match.group(2))
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None

    return lat, lon


def parse_request(text: str) -> tuple[float, float, str] | None:
    """Parse 'lat,lon' optionally followed by a forecast option word
    (one of FORECAST_OPTIONS). Returns (lat, lon, option), where option is
    "default" when omitted. Returns None if coordinates can't be parsed.
    """
    text = text.strip()

    coord_part, _, option_part = text.rpartition(" ")
    if coord_part and option_part.lower() in FORECAST_OPTIONS:
        coords = parse_coordinates(coord_part)
        if coords is not None:
            return coords[0], coords[1], option_part.lower()

    coords = parse_coordinates(text)
    if coords is None:
        return None
    return coords[0], coords[1], "default"
