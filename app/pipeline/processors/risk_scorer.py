def score_from_precipitation(mm: float, threshold_mm: float) -> float:
    """
    Map cumulative precipitation to a landslide probability in [0.02, 0.95].

    Thresholds are calibrated to Ecuador coastal/Andean conditions:
      24 h → 50 mm  (IDEAM critical threshold for shallow landslides)
      48 h → 100 mm
      72 h → 150 mm
    """
    if mm <= 0:
        return 0.02
    ratio = min(mm / threshold_mm, 1.5)
    return round(min(0.05 + 0.65 * ratio, 0.95), 4)


THRESHOLDS = {24: 50.0, 48: 100.0, 72: 150.0}


def compute_probabilities(
    mm_24h: float, mm_48h: float, mm_72h: float
) -> dict[int, float]:
    """Returns {horizon_hours: probability} for 24 / 48 / 72 h."""
    return {
        24: score_from_precipitation(mm_24h, THRESHOLDS[24]),
        48: score_from_precipitation(mm_48h, THRESHOLDS[48]),
        72: score_from_precipitation(mm_72h, THRESHOLDS[72]),
    }
