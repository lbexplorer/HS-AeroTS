"""Truth-blind replay gating and normal-only threshold calibration.

No onset, mutation ID, affected topic, or true module is accepted by inference.
Cross-validation membership is defined by source flight log, not windows.
"""
from __future__ import annotations
import numpy as np


def sustained_gate(scores: np.ndarray, threshold: float, consecutive: int = 3) -> np.ndarray:
    """Causal persistence: open on the kth crossing, never backdate alarms."""
    scores = np.asarray(scores, dtype=float)
    if scores.ndim != 1 or not np.isfinite(scores).all():
        raise ValueError('scores must be a finite vector')
    if consecutive < 1 or not np.isfinite(threshold):
        raise ValueError('invalid gating parameters')
    gate = np.zeros(len(scores), dtype=bool)
    streak = 0
    for i, score in enumerate(scores):
        streak = streak + 1 if score > threshold else 0
        gate[i] = streak >= consecutive
    return gate


def normal_threshold(normal_scores: list[np.ndarray], quantile: float = .99) -> float:
    """Fit solely to explicitly supplied normal calibration flights."""
    if not 0 < quantile <= 1 or not normal_scores:
        raise ValueError('normal calibration flights and valid quantile required')
    values = np.concatenate(normal_scores)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError('empty/nonfinite normal calibration data')
    return float(np.quantile(values, quantile, method='higher'))


def gated_module_scores(values: np.ndarray, reference: np.ndarray, gate: np.ndarray) -> np.ndarray:
    """Existing paired SHAP evidence, with no oracle time restriction."""
    if values.shape != reference.shape or values.shape[0] != len(gate):
        raise ValueError('matched time-grid shapes required')
    delta = np.maximum(values - reference, 0.)
    return delta[gate].mean(axis=0) if gate.any() else np.zeros(values.shape[1])


def conservative_ranks(scores: np.ndarray) -> np.ndarray:
    """Worst rank within ties; zero evidence is unavailable, not alphabetical."""
    scores = np.asarray(scores, dtype=float)
    return np.array([np.sum(scores >= s - 1e-12) if s > 1e-12 else np.inf for s in scores])
