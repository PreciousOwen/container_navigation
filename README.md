# Container Navigation GPS Cloud Service

This Django service receives raw prototype sensor data and exposes an authenticated, structured GPS API for the WOSAC container management system.

## Endpoints

| Method | URL | Purpose | Authentication |
|---|---|---|---|
| `GET` | `/sensor_data/` | Human-readable monitoring page | None |
| `POST` | `/sensor_data/` | Temporary legacy raw sensor receiver | None |
| `POST` | `/api/v1/gps/readings/` | Receive validated GPS data | Device bearer token |
| `GET` | `/api/v1/gps/readings/latest/` | Retrieve a device's latest position | Management bearer token |
| `GET` | `/api/v1/gps/readings/` | Synchronize GPS route history | Management bearer token |

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
```

Generate secrets, for example:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The API fails with HTTP `503` if its required token is not configured.

## Local setup

```bash
cd container_navigation
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DJANGO_DEBUG=True
export GPS_DEVICE_API_TOKEN=device-development-secret
export GPS_MANAGEMENT_API_TOKEN=management-development-secret
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Open `http://127.0.0.1:8000/sensor_data/`.

## Submit structured GPS data

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/gps/readings/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer device-development-secret" \
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

## Retrieve the latest position

```bash
curl "http://127.0.0.1:8000/api/v1/gps/readings/latest/?device_id=GPS-PROTOTYPE-001" \
  -H "Authorization: Bearer management-development-secret"
```

## Synchronize route history

```bash
curl "http://127.0.0.1:8000/api/v1/gps/readings/?device_id=GPS-PROTOTYPE-001&after_id=0&limit=100" \
  -H "Authorization: Bearer management-development-secret"
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
