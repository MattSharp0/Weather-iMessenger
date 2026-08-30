import logging

from fastapi import FastAPI, Header, Request, Response

from app import db, parsing, sendblue, weather

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("weather-messenger")

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.post("/webhook/sendblue")
async def sendblue_webhook(
    request: Request,
    sb_signing_secret: str | None = Header(default=None, alias="sb-signing-secret"),
) -> Response:
    if not sendblue.verify_signature(sb_signing_secret):
        return Response(status_code=401)

    payload = await request.json()

    if payload.get("is_outbound"):
        return Response(status_code=200)

    sender, content = sendblue.extract_incoming(payload)
    if not sender or content is None:
        logger.warning("Unrecognized webhook payload shape: %s", payload)
        return Response(status_code=200)

    content = content.strip()

    with db.get_connection() as conn:
        phone_row = db.get_phone_number(conn, sender)

        if phone_row is None:
            logger.info("Ignoring message from unregistered number")
            return Response(status_code=200)

        db.log_message(conn, phone_row["id"], "inbound", "other", content)

        if not phone_row["verified"]:
            # Verification happens out-of-band via `cli.py verify-number`, not here —
            # same "don't reveal this endpoint exists" posture as an unregistered number.
            logger.info("Ignoring message from unverified number")
            return Response(status_code=200)

        _handle_weather_request(conn, phone_row, content)

    return Response(status_code=200)


def _handle_weather_request(conn, phone_row, content: str) -> None:
    coords = parsing.parse_coordinates(content)

    if coords is None:
        reply = "Send coordinates as 'lat,lon', e.g. 47.6062,-122.3321"
        sendblue.send_message(phone_row["phone_number"], reply)
        db.log_message(conn, phone_row["id"], "outbound", "other", reply)
        return

    lat, lon = coords
    conn.execute(
        "UPDATE messages SET message_type = 'weather_request', parsed_lat = ?, parsed_lon = ? "
        "WHERE id = (SELECT MAX(id) FROM messages WHERE phone_number_id = ?)",
        (lat, lon, phone_row["id"]),
    )

    try:
        reply = weather.get_forecast(lat, lon)
    except Exception:
        logger.exception("Weather lookup failed for %s,%s", lat, lon)
        reply = "Sorry, couldn't fetch a forecast for that location right now."

    sendblue.send_message(phone_row["phone_number"], reply)
    db.log_message(conn, phone_row["id"], "outbound", "weather_reply", reply, lat, lon)
