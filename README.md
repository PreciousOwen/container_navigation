# Container Navigation GPS Cloud Service

This Django service receives raw prototype sensor data and exposes an authenticated, structured GPS API for the WOSAC container management system.

The application timezone is `Africa/Dar_es_Salaam` (East Africa Time, UTC+3).

## Endpoints

| Method | URL | Purpose | Authentication |
|---|---|---|---|
| `GET` | `/sensor_data/` | Human-readable monitoring page | None |
| `POST` | `/sensor_data/` | Temporary legacy raw sensor receiver | None |
| `POST` | `/api/v1/gps/readings/` | Receive validated GPS data | Optional; configurable |
| `GET` | `/api/v1/gps/readings/latest/` | Retrieve a device's latest position | Optional; configurable |
| `GET` | `/api/v1/gps/readings/` | Synchronize GPS route history | Optional; configurable |

Production base URL:

```text
https://wosac.silicon4forge.org
```

## Environment configuration

Copy the values from `deploy/daudi.env.example` into `/etc/daudi/daudi.env` and replace every placeholder secret.

Required production variables:

```text
DJANGO_SECRET_KEY=<long-random-value>
GPS_DEVICE_API_TOKEN=<device-secret>
GPS_MANAGEMENT_API_TOKEN=<different-management-secret>
GPS_REQUIRE_API_AUTH=True
```

Generate secrets, for example:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

When authentication is enabled, the API fails with HTTP `503` if its required
token is not configured.

## Local setup

```bash
cd container_navigation
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DJANGO_DEBUG=True
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Open `http://127.0.0.1:8000/sensor_data/`.

Authentication is disabled by default for the local prototype. Production
should set `GPS_REQUIRE_API_AUTH=True` and configure both tokens.

## Submit structured GPS data

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/gps/readings/" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "GPS-PROTOTYPE-001",
    "latitude": -6.783814,
    "longitude": 39.198997,
    "recorded_at": "2026-06-28T11:20:00Z",
    "gps_fix": true,
    "satellites": 7,
    "speed_kph": 28.5,
    "heading": 120,
    "battery_percent": 82,
    "signal_strength": 18,
    "sequence_number": 105
  }'
```

The pair `device_id + sequence_number` is unique. Resending the same transmission returns the existing record with `"duplicate": true`.

For the single-device prototype, `device_id` may be omitted. The server then
uses `GPS_PROTOTYPE_DEVICE_ID`, which defaults to `GPS-PROTOTYPE-001`.

The latest-position and history GET endpoints use the same default when their
`device_id` query parameter is omitted.

## Retrieve the latest position

```bash
curl "http://127.0.0.1:8000/api/v1/gps/readings/latest/?device_id=GPS-PROTOTYPE-001"
```

## Synchronize route history

```bash
curl "http://127.0.0.1:8000/api/v1/gps/readings/?device_id=GPS-PROTOTYPE-001&after_id=0&limit=100"
```

Store the returned `last_id` in the management system and use it as the next request's `after_id`.

## Legacy firmware support

While `GPS_LEGACY_INGEST_ENABLED=True`, the current firmware may continue posting:

```json
{
  "gps_location": "-6.783814,39.198997"
}
```

to `/sensor_data/`. Valid coordinates are automatically copied into `GPSReading` using the configured `GPS_PROTOTYPE_DEVICE_ID`. Invalid `0,0` readings remain visible as raw diagnostics but are not exposed as valid GPS positions.

Move the firmware to the authenticated API when possible, then set:

```text
GPS_LEGACY_INGEST_ENABLED=False
```

## Tests and checks

```bash
python manage.py check
python manage.py makemigrations --check
python manage.py test
```

## Production deployment

After pulling an update on the server:

```bash
cd /opt/daudi
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn-daudi
sudo systemctl reload nginx
```

Deployment examples are available in `deploy/`.
