from app.pipeline.processors.constants import PRECIPITATION_THRESHOLDS as THRESHOLDS, SUSC_WEIGHT


def score_from_precipitation(mm: float, threshold_mm: float) -> float:
    """
    Map cumulative precipitation to a raw hazard score in [0.02, 0.95].

    Thresholds calibrated to Ecuador coastal/Andean conditions:
      24 h → 50 mm  (IDEAM critical threshold for shallow landslides)
      48 h → 100 mm
      72 h → 150 mm
    """
    if mm <= 0:
        return 0.02
    ratio = min(mm / threshold_mm, 1.5)
    return round(min(0.05 + 0.65 * ratio, 0.95), 4)


def compute_probabilities(
    mm_24h: float,
    mm_48h: float,
    mm_72h: float,
    susceptibility_class: int = 0,
) -> dict[int, float]:
    """
    Returns {horizon_hours: probability} for 24 / 48 / 72 h.

    Probability = precipitation_score × LHASA susceptibility weight.
    A class-0 corridor (water/no-data) gets a floor of 0.02 instead of 0.
    """
    weight = SUSC_WEIGHT.get(susceptibility_class, 0.0)
    results = {}
    for horizon, mm in ((24, mm_24h), (48, mm_48h), (72, mm_72h)):
        raw = score_from_precipitation(mm, THRESHOLDS[horizon])
        if weight == 0.0:
            results[horizon] = 0.02
        else:
            results[horizon] = round(max(raw * weight, 0.02), 4)
    return results
