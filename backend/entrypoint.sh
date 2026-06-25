#!/bin/sh
set -e
flask --app app:app db upgrade
exec "$@"
