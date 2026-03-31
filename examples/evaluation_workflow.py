"""Example evaluation workflow using Scribe."""

from __future__ import annotations

from pathlib import Path

from scribe import LocalJsonlSink, MetricEmission, Scribe


def main() -> None:
    scribe = Scribe(
        project_name="nova-vision",
        sinks=[LocalJsonlSink(Path(".scribe"))],
    )

    with scribe.run("resnet50-eval") as run:
        with run.stage("load-checkpoint") as stage:
            stage.register_artifact(
                "checkpoint",
                Path("./artifacts/model.ckpt"),
                allow_missing=True,
            )

        with run.stage("evaluate") as stage:
            result = stage.emit_metrics(
                [
                    MetricEmission("eval.accuracy", 0.91, aggregation_scope="dataset"),
                    MetricEmission("eval.loss", 0.27, aggregation_scope="dataset"),
                ]
            )
            stage.event(
                "evaluation.completed",
                message=f"evaluation finished with batch status={result.status}",
            )
            stage.register_artifact(
                "evaluation-report",
                Path("./artifacts/eval-report.json"),
                allow_missing=True,
            )


if __name__ == "__main__":
    main()
