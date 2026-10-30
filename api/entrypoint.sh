#!/bin/sh
set -e

python manage.py migrate --database=migration --noinput
python manage.py setup_relational_extras
python manage.py seed_demo_data
python manage.py collectstatic --noinput

exec gunicorn sika.wsgi:application --bind 0.0.0.0:8000 --workers 3
