# Daudi (Django)

This project exposes one endpoint:

- `GET /sensor_data/` renders a single HTML page showing stored sensor payloads
- `POST /sensor_data/` accepts JSON, stores it to SQLite, and returns `{ success: true, id: <int> }`

Target production URL:

- `https://wosac.silicon4forge.org/sensor_data/`

## Local run

```powershell
cd e:\lety\daudi
$env:DJANGO_DEBUG='True'
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Open:

- http://127.0.0.1:8000/sensor_data/

POST example:

```powershell
curl -X POST http://127.0.0.1:8000/sensor_data/ ^
  -H "Content-Type: application/json" ^
  -d "{\"temperature\": 23.4, \"humidity\": 41, \"sensor_id\": \"A1\"}"
```

## Production settings

All production-relevant config is in [daudi_project/settings.py](daudi_project/settings.py) and is controlled via env vars.

Minimum env vars:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS` (comma-separated)
- `DJANGO_DEBUG=False`

See [.env.example](.env.example).

## Nginx + Gunicorn

Example configs are in:

- [deploy/nginx-wosac.conf](deploy/nginx-wosac.conf)
- [deploy/gunicorn-daudi.service](deploy/gunicorn-daudi.service)

Typical Linux deployment outline:

1. Install requirements into a virtualenv.
2. Set up `/etc/daudi/daudi.env` on the server.
3. Run migrations: `python manage.py migrate`
4. Collect static: `python manage.py collectstatic --noinput`
5. Start Gunicorn (systemd) and reload Nginx.

Quick server helper script:

- [deploy/ubuntu_setup.sh](deploy/ubuntu_setup.sh)
