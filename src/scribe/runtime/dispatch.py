"""Sink dispatch helpers."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from scribe.adapters.local.outbox import LocalOutbox
from scribe.exceptions import PartialSinkFailureError, SinkDispatchError
from scribe.results import CaptureResult, Delivery, DeliveryStatus, PayloadFamily

if TYPE_CHECKING:
    from scribe.runtime.session import RuntimeSession

from scribe.runtime.builders import build_degradation_record
from scribe.utils import iso_utc_now


def _observed_at_for(payload: Any) -> str:
    if hasattr(payload, "created_at"):
        value = payload.created_at
        if isinstance(value, str):
            return value
    if hasattr(payload, "manifest"):
        value = payload.manifest.created_at
        if isinstance(value, str):
            return value
    if hasattr(payload, "envelope"):
        value = payload.envelope.observed_at
        if isinstance(value, str):
            return value
    if hasattr(payload, "captured_at"):
        value = payload.captured_at
        if isinstance(value, str):
            return value
    if hasattr(payload, "observed_at"):
        value = payload.observed_at
        if isinstance(value, str):
            return value
    if hasattr(payload, "started_at"):
        value = payload.started_at
        if isinstance(value, str):
            return value
    return iso_utc_now()


def _final_status(
    deliveries: list[Delivery],
    degradation_reasons: list[str],
) -> DeliveryStatus:
    successful = [d for d in deliveries if d.status == DeliveryStatus.SUCCESS]
    degraded = [d for d in deliveries if d.status == DeliveryStatus.DEGRADED]
    failed = [d for d in deliveries if d.status == DeliveryStatus.FAILURE]
    if successful and not degradation_reasons and not degraded:
        return DeliveryStatus.SUCCESS
    if successful or degraded or degradation_reasons:
        if not successful and not degraded and failed:
            return DeliveryStatus.FAILURE
        return DeliveryStatus.DEGRADED
    return DeliveryStatus.FAILURE


def _dispatch(
    runtime: RuntimeSession,
    *,
    family: PayloadFamily,
    payload: Any,
    degradation_reasons: list[str] | None = None,
    warnings: list[str] | None = None,
) -> CaptureResult:
    deliveries: list[Delivery] = []
    reasons = list(degradation_reasons or [])
    warning_messages = list(warnings or [])
    eligible_sink_count = 0
    failed_captures: list[tuple[str, str, int]] = []

    for sink in runtime.sinks:
        if not sink.supports(family):
            deliveries.append(
                Delivery(
                    sink_name=sink.name,
                    family=family,
                    status=DeliveryStatus.SKIPPED,
                    detail="sink does not support this payload family",
                )
            )
            continue

        eligible_sink_count += 1
        attempts = 0
        last_exc: Exception | None = None
        for attempt in range(1, runtime.config.retry_attempts + 2):
            attempts = attempt
            try:
                sink.capture(family=family, payload=payload)
            except PartialSinkFailureError as exc:
                last_exc = None
                deliveries.append(
                    Delivery(
                        sink_name=sink.name,
                        family=family,
                        status=DeliveryStatus.DEGRADED,
                        detail=str(exc),
                    )
                )
                reasons.append(f"sink_partial_failure:{sink.name}")
                warning_messages.append(
                    f"Sink `{sink.name}` partially failed during `{family}` capture: {exc}"
                )
                break
            except Exception as exc:
                last_exc = exc
                if attempt <= runtime.config.retry_attempts and runtime.config.retry_backoff_seconds > 0:
                    time.sleep(runtime.config.retry_backoff_seconds * (2 ** (attempt - 1)))
            else:
                last_exc = None
                break

        if deliveries and deliveries[-1].sink_name == sink.name and deliveries[-1].status == DeliveryStatus.DEGRADED:
            continue

        if last_exc is not None:
            detail = f"attempts={attempts}; error={last_exc}"
            deliveries.append(
                Delivery(
                    sink_name=sink.name,
                    family=family,
                    status=DeliveryStatus.FAILURE,
                    detail=detail,
                )
            )
            reasons.append(f"sink_failure:{sink.name}")
            warning_messages.append(
                f"Sink `{sink.name}` failed during `{family}` capture after {attempts} attempt(s): {last_exc}"
            )
            failed_captures.append((sink.name, str(last_exc), attempts))
        else:
            deliveries.append(
                Delivery(
                    sink_name=sink.name,
                    family=family,
                    status=DeliveryStatus.SUCCESS,
                )
            )

    if not runtime.sinks:
        reasons.append(f"no_sinks_configured:{family}")
        warning_messages.append("Capture finished without configured sinks.")
    elif eligible_sink_count == 0:
        reasons.append(f"no_sink_support_for_family:{family}")
        warning_messages.append(f"No configured sink supports payload family `{family}`.")

    status = _final_status(deliveries, reasons)
    replay_refs: list[str] = []
    recovered_to_outbox = False
    if failed_captures and runtime.config.outbox_root is not None:
        outbox = LocalOutbox(runtime.config.outbox_root)
        for sink_name, error, attempts in failed_captures:
            try:
                replay_ref = outbox.persist_failure(
                    sink_name=sink_name,
                    family=family,
                    payload=payload,
                    error=error,
                    attempts=attempts,
                )
            except Exception as exc:
                warning_messages.append(
                    f"Failed to persist `{family}` payload for sink `{sink_name}` to the outbox: {exc}"
                )
            else:
                recovered_to_outbox = True
                replay_refs.append(replay_ref)
                reasons.append(f"durably_queued_for_replay:{sink_name}")
                warning_messages.append(
                    f"Failed `{family}` payload for sink `{sink_name}` was queued to the outbox as `{replay_ref}`."
                )

    if status == DeliveryStatus.FAILURE and recovered_to_outbox:
        status = DeliveryStatus.DEGRADED

    result = CaptureResult(
        family=family,
        status=status,
        deliveries=deliveries,
        warnings=warning_messages,
        degradation_reasons=reasons,
        payload=payload,
        recovered_to_outbox=recovered_to_outbox,
        replay_refs=replay_refs,
    )

    active_run_ref = runtime.resolve_context().run_ref
    if (
        status == DeliveryStatus.DEGRADED
        and family is not PayloadFamily.DEGRADATION
        and active_run_ref is not None
    ):
        degradation_payload = build_degradation_record(
            runtime,
            source_family=family.value,
            degradation_reasons=reasons,
            warnings=warning_messages,
            observed_at=_observed_at_for(payload),
        )
        result.degradation_payload = degradation_payload
        try:
            degradation_result = _dispatch(
                runtime,
                family=PayloadFamily.DEGRADATION,
                payload=degradation_payload,
                degradation_reasons=[],
                warnings=[],
            )
        except SinkDispatchError:
            result.warnings.append("Failed to dispatch degradation evidence to any sink.")
        else:
            result.degradation_emitted = any(
                delivery.status == DeliveryStatus.SUCCESS
                for delivery in degradation_result.deliveries
            )
            if degradation_result.recovered_to_outbox:
                result.recovered_to_outbox = True
                result.replay_refs.extend(degradation_result.replay_refs)
                result.warnings.append("Degradation evidence was queued to the outbox for replay.")

    if status == DeliveryStatus.FAILURE:
        raise SinkDispatchError("All sinks failed to capture the payload.")

    return result


def dispatch_record(
    runtime: RuntimeSession,
    record: Any,
    *,
    degradation_reasons: list[str] | None = None,
    warnings: list[str] | None = None,
) -> CaptureResult:
    """Dispatch a canonical record to all sinks."""
    return _dispatch(
        runtime,
        family=PayloadFamily.RECORD,
        payload=record,
        degradation_reasons=degradation_reasons,
        warnings=warnings,
    )


def dispatch_artifact(
    runtime: RuntimeSession,
    manifest: Any,
    *,
    degradation_reasons: list[str] | None = None,
    warnings: list[str] | None = None,
) -> CaptureResult:
    """Dispatch an artifact manifest to all sinks."""
    return _dispatch(
        runtime,
        family=PayloadFamily.ARTIFACT,
        payload=manifest,
        degradation_reasons=degradation_reasons,
        warnings=warnings,
    )


def dispatch_context(
    runtime: RuntimeSession,
    context_payload: Any,
    *,
    degradation_reasons: list[str] | None = None,
    warnings: list[str] | None = None,
) -> CaptureResult:
    """Dispatch a context-family payload to all sinks."""
    return _dispatch(
        runtime,
        family=PayloadFamily.CONTEXT,
        payload=context_payload,
        degradation_reasons=degradation_reasons,
        warnings=warnings,
    )


def dispatch_degradation(
    runtime: RuntimeSession,
    payload: Any,
    *,
    degradation_reasons: list[str] | None = None,
    warnings: list[str] | None = None,
) -> CaptureResult:
    """Dispatch a degradation-family payload to all sinks."""
    return _dispatch(
        runtime,
        family=PayloadFamily.DEGRADATION,
        payload=payload,
        degradation_reasons=degradation_reasons,
        warnings=warnings,
    )
