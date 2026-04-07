#!/bin/bash

cd "$(dirname "$0")"
echo "Jestem w katalogu:"
pwd

echo "Aktualizuję repozytorium..."
git fetch
git pull origin main

echo "Uruchamiam aplikację..."

source venv/bin/activate

streamlit run app.py

echo "Gotowe"