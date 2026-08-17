"""ROS-free canonical signal sample contract.

The implementation is intentionally introduced in the GREEN task.  Keeping the
public shape importable here makes the fixture-driven RED tests exercise the
real boundary instead of failing during test collection.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CanonicalSignalSample:
    """Immutable canonical sample value returned by the contract builder."""

    value: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return a detached JSON-compatible representation."""
        return dict(self.value)


def build_canonical_signal_sample(
    *,
    topic_token: str,
    sample: Mapping[str, Any],
    measurement: object | None = None,
) -> CanonicalSignalSample:
    """Validate and freeze one decoded sample and its authoritative facts."""
    raise NotImplementedError('canonical_validation_unimplemented')
