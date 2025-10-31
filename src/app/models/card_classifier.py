"""Card classifier stub and simple inference wrapper.

This module provides a minimal interface so the rest of the app can call
`classify_card(image_bytes)` and later we can swap in a trained model.

The initial implementation returns a conservative 'other' result. When you
have a trained model, implement `load_model()` and update `classify_card`.
"""
from typing import Tuple

_MODEL = None


def load_model(path: str = None):
    """Load a trained model from `path` (implementation placeholder)."""
    global _MODEL
    # TODO: load a PyTorch/ONNX model here
    _MODEL = None
    return _MODEL


def classify_card(image_bytes: bytes) -> Tuple[str, float, str]:
    """Classify card image bytes into ('pr'|'driver_license'|'health_card'|'other'),
    returning (label, score, reason).

    Current implementation is a stub that always returns 'other'.
    """
    # Placeholder conservative return value
    return ("other", 0.0, "stub_no_model")
