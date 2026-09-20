#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
printf 'Open http://localhost:8000\n'
python3 -m http.server 8000 --bind 127.0.0.1
