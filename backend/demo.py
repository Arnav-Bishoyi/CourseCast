"""Offline fixtures only. No API fetching or trained forecasts."""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

def load_sections():
    return json.loads((DATA_DIR / "demo_sections.json").read_text(encoding="utf-8"))

def load_forecasts():
    return json.loads((DATA_DIR / "demo_forecasts.json").read_text(encoding="utf-8"))
