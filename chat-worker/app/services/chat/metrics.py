"""Metrics utilities for chat workflow."""
from __future__ import annotations

from typing import Dict

from app.utils.logging import get_logger

logger = get_logger(__name__)


def log_latency_breakdown(state: Dict) -> None:
    """Log latency breakdown from final state."""
    breakdown = state.get("latency_breakdown", {})
    if not breakdown:
        return

    total = sum(breakdown.values())
    logger.info(
        "Latency breakdown",
        extra={
            "reflection": breakdown.get("reflection", 0.0),
            "retrieval": breakdown.get("retrieval", 0.0),
            "rerank": breakdown.get("rerank", 0.0),
            "generate": breakdown.get("generate", 0.0),
            "total": total,
        },
    )
