"""Smoke test — make sure modules import cleanly."""

def test_imports():
    from src.normalization.normalize import normalize_to_kwh, UNIT_TO_KWH
    from src.emissions.co2 import add_co2_emissions
    from src.anomalies.detect import detect_anomalies
    assert UNIT_TO_KWH["kwh"] == 1.0
