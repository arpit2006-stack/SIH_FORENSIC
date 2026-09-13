"""Cryptographic Erasure Proof Service.

Generates a canonical, tamper-evident JSON payload linked via SHA-256 hash chaining
to the audit log, certifying sanitization execution and independent verification results.
"""

from __future__ import annotations

import hashlib
from typing import Any

from sanitization.models import (
    DeviceInfo,
    ErasureProof,
    SanitizeMethod,
    VerificationResult,
    canonical_json,
    current_iso_timestamp,
)


class ErasureProofService:
    """Generates and cryptographically verifies Erasure Proof records."""

    @classmethod
    def generate_proof(
        cls,
        operation_id: str,
        case_id: str,
        operator_id: str,
        device: DeviceInfo,
        method: SanitizeMethod,
        requested_timestamp: str,
        start_timestamp: str,
        completion_timestamp: str,
        controller_result: dict[str, Any],
        verification_result: VerificationResult,
        warnings: list[str],
        previous_audit_hash: str,
    ) -> ErasureProof:
        """Construct canonical erasure proof object and generate SHA-256 hash linked to previous audit hash."""
        # Assemble core proof attributes without hash
        proof_core = {
            "operationId": operation_id,
            "caseId": case_id,
            "operatorId": operator_id,
            "devicePath": device.device_path,
            "model": device.model,
            "serial": device.serial,
            "firmware": device.firmware,
            "capacity": device.capacity_bytes,
            "interface": device.interface,
            "sanitizationMethod": method.value,
            "requestedTimestamp": requested_timestamp,
            "startTimestamp": start_timestamp,
            "completionTimestamp": completion_timestamp,
            "controllerResult": controller_result,
            "verificationResult": verification_result.to_dict(),
            "verificationChecks": [c.to_dict() for c in verification_result.checks],
            "warnings": warnings,
            "previousAuditHash": previous_audit_hash,
        }

        # Canonicalize and hash
        canonical_str = canonical_json(proof_core)
        hasher = hashlib.sha256()
        hasher.update(canonical_str.encode("utf-8"))
        hasher.update(previous_audit_hash.encode("utf-8"))
        proof_hash = hasher.hexdigest()

        return ErasureProof(
            operation_id=operation_id,
            case_id=case_id,
            operator_id=operator_id,
            device_path=device.device_path,
            model=device.model,
            serial=device.serial,
            firmware=device.firmware,
            capacity=device.capacity_bytes,
            interface=device.interface,
            sanitization_method=method,
            requested_timestamp=requested_timestamp,
            start_timestamp=start_timestamp,
            completion_timestamp=completion_timestamp,
            controller_result=controller_result,
            verification_result=verification_result,
            verification_checks=verification_result.checks,
            warnings=warnings,
            previous_audit_hash=previous_audit_hash,
            proof_hash=proof_hash,
        )

    @classmethod
    def verify_proof_hash(cls, proof: ErasureProof) -> bool:
        """Re-compute and verify the SHA-256 cryptographic hash of an ErasureProof."""
        proof_core = {
            "operationId": proof.operation_id,
            "caseId": proof.case_id,
            "operatorId": proof.operator_id,
            "devicePath": proof.device_path,
            "model": proof.model,
            "serial": proof.serial,
            "firmware": proof.firmware,
            "capacity": proof.capacity,
            "interface": proof.interface,
            "sanitizationMethod": proof.sanitization_method.value,
            "requestedTimestamp": proof.requested_timestamp,
            "startTimestamp": proof.start_timestamp,
            "completionTimestamp": proof.completion_timestamp,
            "controllerResult": proof.controller_result,
            "verificationResult": proof.verification_result.to_dict(),
            "verificationChecks": [c.to_dict() for c in proof.verification_checks],
            "warnings": proof.warnings,
            "previousAuditHash": proof.previous_audit_hash,
        }

        canonical_str = canonical_json(proof_core)
        hasher = hashlib.sha256()
        hasher.update(canonical_str.encode("utf-8"))
        hasher.update(proof.previous_audit_hash.encode("utf-8"))
        expected_hash = hasher.hexdigest()

        return expected_hash == proof.proof_hash
