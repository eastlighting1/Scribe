"""Example artifact registration and binding flow using Scribe."""

from __future__ import annotations

from pathlib import Path

from scribe import LocalJsonlSink, Scribe


def main() -> None:
    scribe = Scribe(
        project_name="nova-vision",
        sinks=[LocalJsonlSink(Path(".scribe"))],
    )

    with scribe.run(
        "artifact-registration",
        code_revision="commit-123",
        config_snapshot={"format": "json", "compression": "none"},
        dataset_ref="validation-split",
    ) as run:
        result = run.register_artifact(
            "evaluation-report",
            Path("./artifacts/eval-report.json"),
            compute_hash=True,
            allow_missing=True,
        )
        run.event(
            "artifact.binding.result",
            message=f"artifact binding finished with status={result.status}",
            attributes={
                "artifact_family": result.family,
                "degraded": result.degraded,
            },
        )


if __name__ == "__main__":
    main()
