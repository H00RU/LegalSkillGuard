"""Deterministic paired uncertainty estimates for skill audits and reporting."""

from __future__ import annotations

import statistics
from collections.abc import Mapping

import numpy as np
from pydantic import BaseModel, ConfigDict, Field


class PairedEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pairs: int = Field(ge=1)
    mean_delta: float
    median_delta: float
    confidence_level: float
    lower: float
    upper: float
    bootstrap_samples: int
    seed: int


def paired_bootstrap_interval(
    deltas: list[float],
    *,
    samples: int = 10_000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> PairedEstimate:
    if not deltas:
        raise ValueError("paired bootstrap requires at least one delta")
    if samples < 100:
        raise ValueError("paired bootstrap requires at least 100 samples")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must lie strictly between zero and one")
    values = np.asarray(deltas, dtype=float)
    generator = np.random.default_rng(seed)
    indices = generator.integers(0, len(values), size=(samples, len(values)))
    means = values[indices].mean(axis=1)
    alpha = (1.0 - confidence_level) / 2.0
    lower, upper = np.quantile(means, [alpha, 1.0 - alpha])
    return PairedEstimate(
        pairs=len(deltas),
        mean_delta=round(statistics.fmean(deltas), 6),
        median_delta=round(statistics.median(deltas), 6),
        confidence_level=confidence_level,
        lower=round(float(lower), 6),
        upper=round(float(upper), 6),
        bootstrap_samples=samples,
        seed=seed,
    )


def clustered_mean_deltas(
    cluster_ids: list[str], before: list[float], after: list[float]
) -> list[float]:
    """Collapse repeated persona/seed observations to independent case-level deltas."""

    if not (len(cluster_ids) == len(before) == len(after)):
        raise ValueError("cluster ids and paired values must have identical lengths")
    if not cluster_ids:
        raise ValueError("clustered paired deltas require at least one observation")
    grouped: dict[str, list[float]] = {}
    for cluster_id, baseline, treatment in zip(cluster_ids, before, after, strict=True):
        grouped.setdefault(cluster_id, []).append(float(treatment) - float(baseline))
    return [statistics.fmean(grouped[key]) for key in sorted(grouped)]


def paired_sign_flip_p_value(
    deltas: list[float], *, samples: int = 20_000, seed: int = 42
) -> float:
    """Two-sided paired randomization p-value using deterministic sign flips."""
    if not deltas:
        raise ValueError("paired randomization requires at least one delta")
    if samples < 100:
        raise ValueError("paired randomization requires at least 100 samples")
    values = np.asarray(deltas, dtype=float)
    observed = abs(float(values.mean()))
    generator = np.random.default_rng(seed)
    signs = generator.choice(np.asarray([-1.0, 1.0]), size=(samples, len(values)))
    simulated = np.abs((signs * values).mean(axis=1))
    return round(float((np.count_nonzero(simulated >= observed) + 1) / (samples + 1)), 8)


def benjamini_hochberg(p_values: Mapping[str, float]) -> dict[str, float]:
    """Return monotone Benjamini-Hochberg adjusted p-values by endpoint name."""
    if not p_values:
        return {}
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    count = len(ordered)
    adjusted: dict[str, float] = {}
    running = 1.0
    for rank, (name, value) in reversed(list(enumerate(ordered, start=1))):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"p-value for {name} is outside [0, 1]")
        running = min(running, value * count / rank)
        adjusted[name] = round(running, 8)
    return adjusted
