"""config.py — Centralized config loaded from .env (with sane defaults)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = Path(os.getenv("RAW_DATA_DIR", ROOT_DIR / "data" / "raw"))
PROCESSED_DATA_DIR = Path(os.getenv("PROCESSED_DATA_DIR", ROOT_DIR / "data" / "processed"))

CO2_FACTOR_KG_PER_KWH = float(os.getenv("CO2_FACTOR_KG_PER_KWH", 0.468))

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "retech/energy/+")
