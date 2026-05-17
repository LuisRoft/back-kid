# Maps LHASA susceptibility class (0–5) → weight applied to precipitation score.
# Calibrated so that classes 3–5 can breach RISK_THRESHOLD=0.65:
#   class-3 max prob: 0.95 × 0.70 = 0.665 (just over threshold at extreme rain)
#   class-4 max prob: 0.95 × 0.85 = 0.808
#   class-5 max prob: 0.95 × 1.00 = 0.950
SUSC_WEIGHT: dict[int, float] = {
    0: 0.00,  # water / no data — no landslide risk
    1: 0.05,  # very low  — max prob 0.047 — never alerts
    2: 0.30,  # low       — max prob 0.285 — never alerts
    3: 0.70,  # moderate  — max prob 0.665 — alerts only at extreme rainfall
    4: 0.85,  # high      — max prob 0.808 — alerts at heavy rainfall
    5: 1.00,  # very high — max prob 0.950 — alerts at moderate rainfall
}

PRECIPITATION_THRESHOLDS: dict[int, float] = {
    24: 50.0,   # IDEAM critical threshold for shallow landslides
    48: 100.0,
    72: 150.0,
}
