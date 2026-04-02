from __future__ import annotations

import pytest

from scribe import InMemorySink, Scribe, ValidationError
from scribe.replay.restore import restore_payload
from scribe.serialization.json_ready import to_json_ready
from scribe.spine_bridge import StructuredEventRecord


def test_validate_metric_rejects_unknown_aggregation_scope() -> None:
    scribe = Scribe(project_name="demo-project", sinks=[InMemorySink()])

    with scribe.run("training") as run:
        with pytest.raises(ValidationError):
            run.metric("loss", 0.1, aggregation_scope="not-a-real-scope")


def test_serialize_json_ready_converts_record_to_plain_mapping() -> None:
    sink = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])

    with scribe.run("training") as run:
        run.event("run.note", message="serialize me")

    family, payload = next(
        action
        for action in sink.actions
        if action[0].value == "record" and action[1].payload.event_key == "run.note"
    )
    assert family.value == "record"
    serialized = to_json_ready(payload)

    assert serialized["envelope"]["record_type"] == "structured_event"
    assert serialized["payload"]["event_key"] == "run.note"


def test_compat_restore_payload_rebuilds_and_validates_record() -> None:
    sink = InMemorySink()
    scribe = Scribe(project_name="demo-project", sinks=[sink])

    with scribe.run("training") as run:
        run.event("run.note", message="compat me")

    _, payload = next(
        action
        for action in sink.actions
        if action[0].value == "record" and action[1].payload.event_key == "run.note"
    )
    restored = restore_payload(type(payload).__name__, to_json_ready(payload))

    assert isinstance(restored, StructuredEventRecord)
    assert restored.payload.event_key == "run.note"
