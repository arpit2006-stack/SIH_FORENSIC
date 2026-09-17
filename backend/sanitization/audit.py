"""Sanitization Audit Interface and Cryptographic Event Logger.

Maintains a tamper-evident, SHA-256 hash-chained log for all 12 defined
sanitization lifecycle events. Provides an exportable interface for integration
with the teammate's global forensic audit system.
"""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from typing import Any

from sanitization.models import (
    AuditEvent,
    DeviceInfo,
    SanitizeEventType,
    canonical_json,
    current_iso_timestamp,
)

GENESIS_HASH = "0" * 64


class SanitizationAuditLogger:
    """Tamper-evident audit event logger with SHA-256 hash chaining."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path
        self._events: list[AuditEvent] = []
        self._last_hash = GENESIS_HASH
        if self.db_path:
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        if not self.db_path:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sanitization_audit_events (
                    event_id TEXT PRIMARY KEY,
                    operation_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    operator_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    device_identity TEXT NOT NULL,
                    result TEXT NOT NULL,
                    details TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL
                )
                """
            )
            conn.commit()

    @property
    def latest_hash(self) -> str:
        return self._last_hash

    def log_event(
        self,
        operation_id: str,
        case_id: str,
        operator_id: str,
        event_type: SanitizeEventType,
        device: DeviceInfo | dict[str, Any],
        result: str,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Record and cryptographically chain a new sanitization audit event."""
        event_id = str(uuid.uuid4())
        ts = current_iso_timestamp()
        details_dict = details or {}

        if isinstance(device, DeviceInfo):
            dev_identity = {
                "devicePath": device.device_path,
                "model": device.model,
                "serial": device.serial,
                "capacityBytes": device.capacity_bytes,
                "storageType": device.storage_type.value,
            }
        else:
            dev_identity = device

        core_payload = {
            "eventId": event_id,
            "operationId": operation_id,
            "caseId": case_id,
            "operatorId": operator_id,
            "timestamp": ts,
            "eventType": event_type.value,
            "deviceIdentity": dev_identity,
            "result": result,
            "details": details_dict,
            "previousHash": self._last_hash,
        }

        canonical_str = canonical_json(core_payload)
        hasher = hashlib.sha256()
        hasher.update(canonical_str.encode("utf-8"))
        hasher.update(self._last_hash.encode("utf-8"))
        event_hash = hasher.hexdigest()

        event = AuditEvent(
            event_id=event_id,
            operation_id=operation_id,
            case_id=case_id,
            operator_id=operator_id,
            timestamp=ts,
            event_type=event_type.value,
            device_identity=dev_identity,
            result=result,
            details=details_dict,
            previous_hash=self._last_hash,
            event_hash=event_hash,
        )

        self._events.append(event)
        self._last_hash = event_hash

        if self.db_path:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO sanitization_audit_events
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.operation_id,
                        event.case_id,
                        event.operator_id,
                        event.timestamp,
                        event.event_type,
                        canonical_json(event.device_identity),
                        event.result,
                        canonical_json(event.details),
                        event.previous_hash,
                        event.event_hash,
                    ),
                )
                conn.commit()

        return event

    def get_events_for_operation(self, operation_id: str) -> list[AuditEvent]:
        return [e for e in self._events if e.operation_id == operation_id]

    def verify_chain_integrity(self) -> tuple[bool, str | None]:
        """Verify the integrity of the entire cryptographic event chain."""
        expected_prev = GENESIS_HASH
        for idx, event in enumerate(self._events):
            if event.previous_hash != expected_prev:
                return False, f"Chain broken at index {idx} ({event.event_id}): previous_hash mismatch"

            core_payload = {
                "eventId": event.event_id,
                "operationId": event.operation_id,
                "caseId": event.case_id,
                "operatorId": event.operator_id,
                "timestamp": event.timestamp,
                "eventType": event.event_type,
                "deviceIdentity": event.device_identity,
                "result": event.result,
                "details": event.details,
                "previousHash": event.previous_hash,
            }
            canonical_str = canonical_json(core_payload)
            hasher = hashlib.sha256()
            hasher.update(canonical_str.encode("utf-8"))
            hasher.update(expected_prev.encode("utf-8"))
            calculated_hash = hasher.hexdigest()

            if calculated_hash != event.event_hash:
                return False, f"Tamper detected at event {event.event_id}: hash recalculation failed"

            expected_prev = event.event_hash

        return True, None
