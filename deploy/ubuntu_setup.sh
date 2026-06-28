#!/usr/bin/env bash
set -euo pipefail

# Ubuntu server setup for this Django + SQLite project.
# Run on the server from /home/ubuntu/daudi
#
# What it does:
# - Installs system packages (nginx, python venv)
# - Creates venv and installs requirements
# - Creates /etc/daudi/daudi.env (you must set DJANGO_SECRET_KEY)
# - Runs migrate + collectstatic
# - Installs/starts Gunicorn systemd service
# - Installs Nginx site config and (optionally) runs certbot

APP_DIR="/home/ubuntu/daudi"
DOMAIN="wosac.silicon4forge.org"

sudo apt-get update
sudo apt-get install -y python3-venv python3-pip nginx

# Webroot used by Nginx for Let's Encrypt HTTP-01 challenges
sudo mkdir -p /var/www/letsencrypt/.well-known/acme-challenge
sudo chown -R www-data:www-data /var/www/letsencrypt

cd "$APP_DIR"

python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

# Environment file
sudo mkdir -p /etc/daudi
sudo bash -c "cat > /etc/daudi/daudi.env" <<'EOF'
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=wosac.silicon4forge.org
DJANGO_CSRF_TRUSTED_ORIGINS=https://wosac.silicon4forge.org
DJANGO_SQLITE_PATH=db.sqlite3

# REQUIRED in production:
DJANGO_SECRET_KEY=CHANGE_ME_TO_A_LONG_RANDOM_VALUE
EOF
sudo chmod 600 /etc/daudi/daudi.env
sudo chown root:root /etc/daudi/daudi.env

# Django DB + static
./.venv/bin/python manage.py migrate
./.venv/bin/python manage.py collectstatic --noinput

# systemd service
sudo cp deploy/gunicorn-daudi.service /etc/systemd/system/gunicorn-daudi.service
sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn-daudi
sudo systemctl status --no-pager gunicorn-daudi || true

# Nginx site
sudo cp deploy/nginx-wosac.conf /etc/nginx/sites-available/daudi
sudo ln -sf /etc/nginx/sites-available/daudi /etc/nginx/sites-enabled/daudi
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

cat <<EOF

Next steps:
1) Edit /etc/daudi/daudi.env and set DJANGO_SECRET_KEY.
2) Ensure DNS for $DOMAIN points to this server.
3) Install TLS cert (recommended):
   sudo snap install --classic certbot || sudo apt-get install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d $DOMAIN

Test locally on the server:
  curl -X POST http://127.0.0.1:8001/sensor_data/ -H 'Content-Type: application/json' -d '{"sensor_id":"A1","temperature":23.4}'

Then test externally:
  https://$DOMAIN/sensor_data/
EOF
