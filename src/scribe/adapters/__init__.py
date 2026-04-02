"""Default adapter implementations."""

from scribe.adapters.kafka import KafkaSink
from scribe.adapters.local import LocalJsonlSink, LocalOutbox
from scribe.adapters.s3 import S3ObjectSink

__all__ = ["KafkaSink", "LocalJsonlSink", "LocalOutbox", "S3ObjectSink"]
