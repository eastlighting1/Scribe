"""Example training workflow using Scribe."""

from __future__ import annotations

from pathlib import Path

from scribe import EventEmission, LocalJsonlSink, MetricEmission, Scribe


def main() -> None:
    scribe = Scribe(
        project_name="nova-vision",
        sinks=[LocalJsonlSink(Path(".scribe"))],
    )

    with scribe.run("resnet50-baseline") as run:
        run.event("run.note", message="baseline training started")

        with run.stage("prepare-data") as stage:
            stage.emit_metrics(
                [
                    MetricEmission("data.rows", 128_000, aggregation_scope="dataset"),
                    MetricEmission("data.features", 512, aggregation_scope="dataset"),
                ]
            )

        with run.stage("train") as stage:
            for step in range(3):
                with stage.operation(f"step-{step}") as operation:
                    operation.metric("training.loss", 0.9 - (step * 0.1), aggregation_scope="step")
                    operation.span("model.forward", span_kind="model_call")

            stage.emit_events(
                [
                    EventEmission("epoch.started", "epoch 1 started"),
                    EventEmission("epoch.completed", "epoch 1 completed"),
                ]
            )
            stage.register_artifact(
                "checkpoint",
                Path("./artifacts/model.ckpt"),
                allow_missing=True,
            )


if __name__ == "__main__":
    main()
