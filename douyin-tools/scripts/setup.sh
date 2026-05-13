#!/bin/bash
set -e

echo "=== Installing system dependencies (brew) ==="
brew install poppler
brew install libreoffice

echo "=== Installing Python dependencies ==="
pip3 install -r ../config/requirements.txt

echo "=== Done! Run: python3 app.py ==="
