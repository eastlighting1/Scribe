from __future__ import annotations

import warnings
from typing import Any

from scribe import CompositeSink, PayloadFamily, Scribe
from scribe.sinks import Sink


class RecordingSink(Sink):
    name = "recording"
    supported_families = frozenset(PayloadFamily)

    def __init__(self) -> None:
        self.actions: list[tuple[PayloadFamily, Any]] = []

    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        self.actions.append((family, payload))


class FailingSink(Sink):
    name = "failing"
    supported_families = frozenset(PayloadFamily)

    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        raise RuntimeError(f"cannot store {family.value}")


def test_composite_sink_continues_after_child_failure_and_aggregates_errors() -> None:
    recording = RecordingSink()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        composite = CompositeSink([FailingSink(), recording], name="fanout")
    scribe = Scribe(project_name="demo-project", sinks=[composite])

    with scribe.run("training") as run:
        result = run.event("run.note", message="fanout capture")

    assert any(issubclass(item.category, DeprecationWarning) for item in caught)
    assert result.status.value == "degraded"
    assert recording.actions
    assert any(
        delivery.sink_name == "fanout"
        and "failing: cannot store record" in delivery.detail
        for delivery in result.deliveries
    )
