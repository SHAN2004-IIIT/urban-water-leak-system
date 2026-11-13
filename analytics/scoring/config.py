"""Versioned, explainable scoring parameters (not calibrated probabilities)."""
SCORE_VERSION = "rules-v1"
WEIGHTS = {"consumption": 35, "nighttime": 25, "complaints": 25, "persistence": 15}
assert sum(WEIGHTS.values()) == 100
ALLOWED_ACCESS = {"OPEN", "BLOCKED", "UNKNOWN"}
