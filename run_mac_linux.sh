#!/usr/bin/env bash
# Sets up a virtual environment (first run only) and starts SafeHer.
set -e
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt
python app.py
