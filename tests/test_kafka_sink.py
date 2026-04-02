from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from scribe import KafkaSink, PayloadFamily, Scribe


class FakeFuture:
    def __init__(self) -> None:
        self.timeout: float | None = None

    def get(self, *, timeout: float) -> None:
        self.timeout = timeout


class ProducerCall(TypedDict):
    topic: str
    key: bytes
    value: bytes
    future: FakeFuture


class FakeProducer:
    def __init__(self) -> None:
        self.calls: list[ProducerCall] = []
        self.futures: list[FakeFuture] = []

    def send(self, topic: str, *, key: bytes, value: bytes) -> FakeFuture:
        future = FakeFuture()
        self.calls.append({"topic": topic, "key": key, "value": value, "future": future})
        self.futures.append(future)
        return future


def test_kafka_sink_publishes_record_payload_to_family_topic() -> None:
    producer = FakeProducer()
    sink = KafkaSink(producer=producer, topic_prefix="observability", delivery_timeout_seconds=3.0)
    scribe = Scribe(project_name="demo-project", sinks=[sink])

    with scribe.run("training") as run:
        result = run.event("run.note", message="captured to kafka")

    assert result.status.value == "success"
    matching_call = next(
        call
        for call in producer.calls
        if call["topic"] == "observability.record"
        and json.loads(call["value"].decode("utf-8"))["payload"]["payload"]["event_key"]
        == "run.note"
    )
    assert matching_call["key"].startswith(b"run:")
    payload = json.loads(matching_call["value"].decode("utf-8"))
    assert payload["family"] == PayloadFamily.RECORD.value
    assert matching_call["future"].timeout == 3.0


def test_kafka_sink_uses_artifact_ref_as_message_key(tmp_path: Path) -> None:
    producer = FakeProducer()
    sink = KafkaSink(producer=producer, topic_prefix="scribe", delivery_timeout_seconds=5.0)
    scribe = Scribe(project_name="demo-project", sinks=[sink])
    artifact_path = tmp_path / "model.bin"
    artifact_path.write_bytes(b"checkpoint")

    with scribe.run("training") as run:
        result = run.register_artifact("checkpoint", artifact_path, artifact_ref="artifact.model")

    assert result.status.value == "success"
    artifact_call = next(call for call in producer.calls if call["topic"] == "scribe.artifact")
    assert artifact_call["key"] == b"artifact:artifact.model"
    payload = json.loads(artifact_call["value"].decode("utf-8"))
    assert payload["family"] == PayloadFamily.ARTIFACT.value
    assert payload["payload"]["manifest"]["artifact_ref"] == "artifact:artifact.model"
