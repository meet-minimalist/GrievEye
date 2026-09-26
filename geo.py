"""
Location helpers: GPS from photo metadata, distance between two points, map links.

Telegram (and WhatsApp) strip metadata from normal photos, so GPS is only found
in photos sent "as a file" from a phone whose camera saves location.
"""
import io
import math

from PIL import Image

GPS_IFD = 0x8825
FAR_METRES = 500  # proof taken further than this from the complaint is flagged


def exif_gps(image_bytes):
    """(lat, lon) from a photo's EXIF data, or None."""
    try:
        gps = Image.open(io.BytesIO(image_bytes)).getexif().get_ifd(GPS_IFD)
        if not gps or 2 not in gps or 4 not in gps:
            return None

        def degrees(value, ref):
            d, m, s = (float(x) for x in value)
            result = d + m / 60 + s / 3600
            return -result if ref in ("S", "W") else result

        lat, lon = degrees(gps[2], gps.get(1, "N")), degrees(gps[4], gps.get(3, "E"))
        if lat == 0 and lon == 0:
            return None
        return round(lat, 6), round(lon, 6)
    except Exception:
        return None


def distance_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres."""
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def maps_link(lat, lon):
    return f"https://maps.google.com/?q={lat},{lon}"


def describe_distance(metres):
    if metres is None:
        return None
    text = f"{round(metres)} m" if metres < 1000 else f"{metres / 1000:.1f} km"
    return f"{text} from the complaint location " + ("✅" if metres <= FAR_METRES else "⚠️")
