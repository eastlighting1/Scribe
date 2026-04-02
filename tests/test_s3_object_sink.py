from __future__ import annotations

import json
from pathlib import Path

from scribe import PayloadFamily, S3ObjectSink, Scribe


class FakeS3Client:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def put_object(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


def test_s3_object_sink_writes_record_payload_with_family_key_prefix() -> None:
    client = FakeS3Client()
    sink = S3ObjectSink(bucket="demo-bucket", prefix="observability", client=client)
    scribe = Scribe(project_name="demo-project", sinks=[sink])

    with scribe.run("training") as run:
        result = run.event("run.note", message="captured to s3")

    assert result.status.value == "success"
    assert client.calls
    record_call = next(
        call
        for call in client.calls
        if "/record/" in str(call["Key"])
        and json.loads(bytes(call["Body"]).decode("utf-8"))["payload"]["payload"]["event_key"] == "run.note"
    )
    assert record_call["Bucket"] == "demo-bucket"
    assert str(record_call["Key"]).startswith("observability/record/")
    body = json.loads(bytes(record_call["Body"]).decode("utf-8"))
    assert body["family"] == "record"
    assert body["payload"]["payload"]["event_key"] == "run.note"


def test_s3_object_sink_uses_artifact_ref_in_object_key(tmp_path: Path) -> None:
    client = FakeS3Client()
    sink = S3ObjectSink(bucket="demo-bucket", prefix="scribe", client=client)
    scribe = Scribe(project_name="demo-project", sinks=[sink])
    artifact_path = tmp_path / "model.bin"
    artifact_path.write_bytes(b"checkpoint")

    with scribe.run("training") as run:
        result = run.register_artifact("checkpoint", artifact_path, artifact_ref="artifact.model")

    assert result.status.value == "success"
    artifact_call = next(call for call in client.calls if "/artifact/" in str(call["Key"]))
    assert "artifact_artifact.model" in str(artifact_call["Key"])
    body = json.loads(bytes(artifact_call["Body"]).decode("utf-8"))
    assert body["family"] == PayloadFamily.ARTIFACT.value
    assert body["payload"]["manifest"]["artifact_ref"] == "artifact:artifact.model"
