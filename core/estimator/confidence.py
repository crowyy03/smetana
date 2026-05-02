"""Классификация метода оценки по confidence."""

from config import config


def classify_method(confidence: float, needs_manual_review: bool) -> str:
    if needs_manual_review or confidence < config.MEDIUM_CONFIDENCE_THRESHOLD:
        return "needs_manual"
    if confidence >= config.HIGH_CONFIDENCE_THRESHOLD:
        return "auto_high"
    return "auto_medium"
