"""CLI entry point for replaying durable outbox entries."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any

from scribe.adapters.kafka import KafkaSink
from scribe.adapters.local.jsonl import LocalJsonlSink
from scribe.adapters.s3 import S3ObjectSink
from scribe.replay.service import replay_outbox
from scribe.sinks import Sink


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scribe-replay-outbox")
    parser.add_argument("--outbox-root", required=True)
    parser.add_argument("--sink-kind", required=True, choices=("local-jsonl", "s3", "kafka"))
    parser.add_argument("--sink-name", required=True)
    parser.add_argument("--target-sink-name", default=None)
    parser.add_argument("--storage-root")
    parser.add_argument("--bucket")
    parser.add_argument("--prefix")
    parser.add_argument("--topic-prefix")
    parser.add_argument("--delivery-timeout-seconds", type=float, default=10.0)
    parser.add_argument("--dead-letter-after-failures", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _build_sink(args: argparse.Namespace) -> Sink:
    target_name = args.target_sink_name or args.sink_name
    if args.sink_kind == "local-jsonl":
        if not args.storage_root:
            raise SystemExit("--storage-root is required for local-jsonl replay.")
        return LocalJsonlSink(args.storage_root, name=target_name)
    if args.sink_kind == "s3":
        if not args.bucket:
            raise SystemExit("--bucket is required for s3 replay.")
        return S3ObjectSink(
            bucket=args.bucket,
            prefix=args.prefix or "scribe",
            name=target_name,
        )
    if not args.topic_prefix:
        raise SystemExit("--topic-prefix is required for kafka replay.")
    return KafkaSink(
        topic_prefix=args.topic_prefix,
        delivery_timeout_seconds=args.delivery_timeout_seconds,
        name=target_name,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    sink = _build_sink(args)
    result = replay_outbox(
        outbox_root=args.outbox_root,
        sinks=[sink],
        sink_name=args.sink_name,
        acknowledge_successes=not args.dry_run,
        dead_letter_after_failures=args.dead_letter_after_failures,
    )
    print(
        f"replayed={result.total_count} "
        f"succeeded={result.success_count} "
        f"skipped={result.skipped_count} "
        f"failed={result.failure_count}"
    )
    return 0 if result.failure_count == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
