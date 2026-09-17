"""Sanitization JSON Report Generator.

Produces comprehensive, standardized forensic JSON reports for both certified
erasures and explicitly unverified operations (SANITIZATION_NOT_VERIFIED).
"""

from __future__ import annotations

import json
from typing import Any

from sanitization.models import (
    DeviceInfo,
    ErasureProof,
    ForgeAssuranceScore,
    SanitizationPolicy,
    SanitizationReport,
    SanitizeMethod,
    VerificationResult,
    VerificationStatus,
    current_iso_timestamp,
)


class SanitizationReportGenerator:
    """Generates machine-readable forensic erasure reports."""

    @classmethod
    def generate_report(
        cls,
        case_id: str,
        operator_id: str,
        operation_id: str,
        device: DeviceInfo,
        policy: SanitizationPolicy,
        method: SanitizeMethod,
        execution_result: dict[str, Any],
        verification_result: VerificationResult,
        assurance_score: ForgeAssuranceScore,
        proof: ErasureProof | None,
        audit_reference: str,
        missing_evidence: list[str] | None = None,
        recommendation: str | None = None,
    ) -> SanitizationReport:
        # Determine top-level report status
        if verification_result.status == VerificationStatus.VERIFIED:
            status = "COMPLETED"
        elif verification_result.status == VerificationStatus.NOT_VERIFIED:
            status = "SANITIZATION_NOT_VERIFIED"
        else:
            status = "FAILED"

        report = SanitizationReport(
            report_type="ERASURE",
            status=status,
            case_id=case_id,
            operator_id=operator_id,
            operation_id=operation_id,
            timestamp=current_iso_timestamp(),
            device=device,
            policy=policy,
            method=method,
            execution=execution_result,
            verification=verification_result,
            assurance=assurance_score,
            proof=proof,
            audit_reference=audit_reference,
            missing_evidence=missing_evidence or [],
            recommendation=recommendation or (
                "Drive sanitization successfully verified."
                if status == "COMPLETED"
                else "Physical destruction recommended."
            ),
        )
        return report

    @classmethod
    def to_json(cls, report: SanitizationReport, indent: int = 2) -> str:
        """Serialize report to indented human/machine readable JSON."""
        return json.dumps(report.to_dict(), indent=indent, ensure_ascii=False)
