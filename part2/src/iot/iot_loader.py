"""iot_loader.py — Load IoT sensor data (from MQTT broker or CSV log)."""
from pathlib import Path

import pandas as pd
from loguru import logger

from src.utils.config import RAW_DATA_DIR


def load_iot_data() -> pd.DataFrame:
    """Load IoT sensor readings.

    For the hackathon, we read from a CSV log file. Later we can replace this
    with a live MQTT subscriber (see `src/iot/mqtt_listener.py`).
    """
    iot_file = Path(RAW_DATA_DIR).parent / "iot" / "sensors.csv"
    if not iot_file.exists():
        logger.warning(f"No IoT file found at {iot_file} — returning empty.")
        return pd.DataFrame()
    df = pd.read_csv(iot_file)
    df["source"] = "iot_sensor"
    logger.info(f"Loaded {len(df)} IoT rows")
    return df
