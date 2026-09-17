"""Sanitization Operation Service.

Central orchestrator connecting API/CLI, Device Discovery, Storage Intelligence,
Policy Engine, Safety Gate, Adapters, Verification Engine, Erasure Proof,
FORGE Assurance Scoring, Audit Logger, and Reporting.
"""

from __future__ import annotations

import uuid
from typing import Any

from sanitization.adapters.ata import AtaSanitizationAdapter
from sanitization.adapters.base import SanitizationAdapter
from sanitization.adapters.mock import MockSanitizationAdapter
from sanitization.adapters.nvme import NvmeSanitizationAdapter
from sanitization.adapters.unsupported import UnsupportedSanitizationAdapter
from sanitization.assurance import ForgeAssuranceService
from sanitization.audit import SanitizationAuditLogger
from sanitization.discovery import DeviceDiscoveryManager
from sanitization.intelligence import StorageIntelligence
from sanitization.models import (
    AssuranceLevel,
    DeviceInfo,
    ErasureProof,
    ForgeAssuranceScore,
    OperationMode,
    SafetyAuthorization,
    SanitizationErrorCode,
    SanitizationException,
    SanitizationPolicy,
    SanitizationReport,
    SanitizeEventType,
    SanitizeMethod,
    VerificationResult,
    VerificationStatus,
    current_iso_timestamp,
)
from sanitization.policy import StoragePolicyEngine
from sanitization.proof import ErasureProofService
from sanitization.reporting import SanitizationReportGenerator
from sanitization.safety import SafetyGate
from sanitization.verification import ErasureVerificationEngine


class SanitizationOperationService:
    """End-to-end sanitization workflow service."""

    def __init__(
        self,
        discovery_manager: DeviceDiscoveryManager | None = None,
        mock_adapter: MockSanitizationAdapter | None = None,
        audit_logger: SanitizationAuditLogger | None = None,
    ):
        self.mock_adapter = mock_adapter or MockSanitizationAdapter()
        self.discovery = discovery_manager or DeviceDiscoveryManager(
            mock_adapter=self.mock_adapter,
            enable_mock_devices=True,
        )
        self.audit = audit_logger or SanitizationAuditLogger()

        # Hardware adapters list in order of precedence
        self.adapters: list[SanitizationAdapter] = [
            self.mock_adapter,
            NvmeSanitizationAdapter(),
            AtaSanitizationAdapter(),
            UnsupportedSanitizationAdapter(),
        ]

        # In-memory store for operations: op_id -> SanitizationReport
        self._operations: dict[str, SanitizationReport] = {}

    def get_adapter_for_device(self, device: DeviceInfo) -> SanitizationAdapter:
        """Find the matching hardware adapter for a given device."""
        for adapter in self.adapters:
            if adapter.supports_device(device):
                return adapter
        return self.adapters[-1]  # Fallback to Unsupported adapter

    def list_devices(self, include_mock: bool = True) -> list[DeviceInfo]:
        """Discover connected devices and enrich with controller capabilities."""
        devices = self.discovery.discover_devices(include_mock=include_mock)
        enriched: list[DeviceInfo] = []
        for dev in devices:
            # Enrich capabilities if needed
            dev = StorageIntelligence.enrich_device_capabilities(dev)
            enriched.append(dev)
        return enriched

    def get_device(self, device_path: str) -> DeviceInfo | None:
        """Retrieve and enrich a single device by path."""
        dev = self.discovery.find_device_by_path(device_path)
        if dev:
            return StorageIntelligence.enrich_device_capabilities(dev)
        return None

    def plan_sanitization(
        self,
        device_path: str,
        requested_assurance: AssuranceLevel = AssuranceLevel.HIGH,
    ) -> tuple[DeviceInfo, SanitizationPolicy]:
        """Evaluate policy for the given device."""
        dev = self.get_device(device_path)
        if not dev:
            raise SanitizationException(
                SanitizationErrorCode.DEVICE_NOT_FOUND,
                f"Device '{device_path}' could not be located.",
                {"devicePath": device_path},
            )

        policy = StoragePolicyEngine.evaluate_policy(dev, requested_assurance=requested_assurance)
        op_id = f"plan-{uuid.uuid4().hex[:8]}"
        self.audit.log_event(
            operation_id=op_id,
            case_id="PRE-PLAN",
            operator_id="SYSTEM",
            event_type=SanitizeEventType.SANITIZATION_PLANNED,
            device=dev,
            result="SUCCESS",
            details={
                "recommendedMethod": policy.recommended_method.value,
                "assurance": policy.assurance.value,
                "supportedMethods": [m.value for m in policy.supported_methods],
            },
        )
        return dev, policy

    def execute_dry_run(
        self,
        device_path: str,
        method: SanitizeMethod | None = None,
        operator_id: str = "OP-PREVIEW",
        case_id: str = "CASE-PREVIEW",
    ) -> dict[str, Any]:
        """Execute non-destructive dry run generating intended command and verification plan."""
        dev, policy = self.plan_sanitization(device_path)
        chosen_method = method or policy.recommended_method

        if chosen_method == SanitizeMethod.UNSUPPORTED:
            raise SanitizationException(
                SanitizationErrorCode.UNSUPPORTED_SANITIZATION,
                f"Device '{device_path}' has no supported sanitization method.",
                {"device": device_path},
            )

        adapter = self.get_adapter_for_device(dev)
        plan = adapter.generate_plan(dev, chosen_method)
        operation_id = f"dryrun-{uuid.uuid4().hex[:8]}"
        plan["operationId"] = operation_id
        plan["caseId"] = case_id
        plan["operatorId"] = operator_id

        # Log DRY_RUN_EXECUTED audit event
        self.audit.log_event(
            operation_id=operation_id,
            case_id=case_id,
            operator_id=operator_id,
            event_type=SanitizeEventType.DRY_RUN_EXECUTED,
            device=dev,
            result="SUCCESS",
            details=plan,
        )

        return plan

    def execute_sanitization(
        self,
        authorization: SafetyAuthorization,
    ) -> SanitizationReport:
        """Execute end-to-end sanitization workflow."""
        # Check mode: if DRY_RUN, route to execute_dry_run
        if authorization.execution_mode == OperationMode.DRY_RUN:
            dry_plan = self.execute_dry_run(
                device_path=authorization.device_path,
                method=authorization.selected_method,
                operator_id=authorization.operator_id,
                case_id=authorization.case_id,
            )
            dev = self.get_device(authorization.device_path)
            policy = StoragePolicyEngine.evaluate_policy(dev)
            report = SanitizationReportGenerator.generate_report(
                case_id=authorization.case_id,
                operator_id=authorization.operator_id,
                operation_id=dry_plan["operationId"],
                device=dev,
                policy=policy,
                method=authorization.selected_method,
                execution_result=dry_plan,
                verification_result=VerificationResult(
                    status=VerificationStatus.NOT_VERIFIED,
                    details="Dry-run completed. Hardware was not modified.",
                ),
                assurance_score=ForgeAssuranceScore(score=0, level="INSUFFICIENT", rationale="Dry run only"),
                proof=None,
                audit_reference=self.audit.latest_hash,
                recommendation="Review dry-run plan. To wipe device, supply explicit destructive confirmation.",
            )
            self._operations[dry_plan["operationId"]] = report
            return report

        operation_id = f"op-{uuid.uuid4().hex[:10]}"
        requested_ts = authorization.timestamp or current_iso_timestamp()

        # Step 1: Initial Discovery
        target_dev = self.get_device(authorization.device_path)
        if not target_dev:
            raise SanitizationException(
                SanitizationErrorCode.DEVICE_NOT_FOUND,
                f"Target device '{authorization.device_path}' not found.",
                {"devicePath": authorization.device_path},
            )

        policy = StoragePolicyEngine.evaluate_policy(target_dev)

        # Step 2: Safety Gate Validation
        SafetyGate.validate_authorization(authorization, target_dev)
        self.audit.log_event(
            operation_id=operation_id,
            case_id=authorization.case_id,
            operator_id=authorization.operator_id,
            event_type=SanitizeEventType.AUTHORIZATION_GRANTED,
            device=target_dev,
            result="GRANTED",
            details={
                "method": authorization.selected_method.value,
                "reason": authorization.reason,
            },
        )

        # Step 3: Pre-Execution Re-Discovery and Multi-Attribute Identity Consistency Check
        fresh_dev = self.get_device(authorization.device_path)
        if not fresh_dev:
            raise SanitizationException(
                SanitizationErrorCode.DEVICE_NOT_FOUND,
                f"Device '{authorization.device_path}' disconnected immediately prior to execution.",
            )
        SafetyGate.verify_pre_execution_integrity(target_dev, fresh_dev)

        # Step 4: Adapter Execution
        adapter = self.get_adapter_for_device(fresh_dev)
        self.audit.log_event(
            operation_id=operation_id,
            case_id=authorization.case_id,
            operator_id=authorization.operator_id,
            event_type=SanitizeEventType.SANITIZATION_STARTED,
            device=fresh_dev,
            result="STARTED",
            details={"method": authorization.selected_method.value},
        )

        start_ts = current_iso_timestamp()
        try:
            exec_result = adapter.execute_sanitize(fresh_dev, authorization.selected_method, authorization)
            completion_ts = current_iso_timestamp()
            self.audit.log_event(
                operation_id=operation_id,
                case_id=authorization.case_id,
                operator_id=authorization.operator_id,
                event_type=SanitizeEventType.SANITIZATION_COMPLETED,
                device=fresh_dev,
                result="SUCCESS",
                details=exec_result,
            )
        except SanitizationException as exc:
            completion_ts = current_iso_timestamp()
            self.audit.log_event(
                operation_id=operation_id,
                case_id=authorization.case_id,
                operator_id=authorization.operator_id,
                event_type=SanitizeEventType.SANITIZATION_FAILED,
                device=fresh_dev,
                result="FAILED",
                details={"error": str(exc), "code": exc.code.value},
            )
            # Create failure report
            failed_res = VerificationResult(
                status=VerificationStatus.FAILED,
                details=f"Command execution error: {exc.message}",
            )
            assurance = ForgeAssuranceScore(score=0, level="INSUFFICIENT", rationale="Execution failed")
            report = SanitizationReportGenerator.generate_report(
                case_id=authorization.case_id,
                operator_id=authorization.operator_id,
                operation_id=operation_id,
                device=fresh_dev,
                policy=policy,
                method=authorization.selected_method,
                execution_result={"status": "FAILED", "error": str(exc)},
                verification_result=failed_res,
                assurance_score=assurance,
                proof=None,
                audit_reference=self.audit.latest_hash,
                missing_evidence=["Successful command execution"],
                recommendation="Inspect hardware connections and kernel logs.",
            )
            self._operations[operation_id] = report
            return report

        # Step 5: Post-Sanitization Verification
        self.audit.log_event(
            operation_id=operation_id,
            case_id=authorization.case_id,
            operator_id=authorization.operator_id,
            event_type=SanitizeEventType.VERIFICATION_STARTED,
            device=fresh_dev,
            result="STARTED",
            details={},
        )

        re_discovered = self.get_device(authorization.device_path)
        verif_result, missing_evidence, recommendation = ErasureVerificationEngine.verify_erasure(
            device=fresh_dev,
            re_discovered=re_discovered,
            method=authorization.selected_method,
            execution_result=exec_result,
            adapter=adapter,
        )

        if verif_result.status == VerificationStatus.VERIFIED:
            self.audit.log_event(
                operation_id=operation_id,
                case_id=authorization.case_id,
                operator_id=authorization.operator_id,
                event_type=SanitizeEventType.SANITIZATION_VERIFIED,
                device=fresh_dev,
                result="VERIFIED",
                details=verif_result.to_dict(),
            )
        elif verif_result.status == VerificationStatus.NOT_VERIFIED:
            self.audit.log_event(
                operation_id=operation_id,
                case_id=authorization.case_id,
                operator_id=authorization.operator_id,
                event_type=SanitizeEventType.SANITIZATION_NOT_VERIFIED,
                device=fresh_dev,
                result="NOT_VERIFIED",
                details={"missingEvidence": missing_evidence, "details": verif_result.details},
            )
        else:
            self.audit.log_event(
                operation_id=operation_id,
                case_id=authorization.case_id,
                operator_id=authorization.operator_id,
                event_type=SanitizeEventType.SANITIZATION_FAILED,
                device=fresh_dev,
                result="FAILED",
                details=verif_result.to_dict(),
            )

        # Step 6: Cryptographic Erasure Proof (Generated whenever execution completes)
        proof = None
        if verif_result.status in (VerificationStatus.VERIFIED, VerificationStatus.NOT_VERIFIED):
            ctrl_status = adapter.get_sanitize_status(fresh_dev)
            proof = ErasureProofService.generate_proof(
                operation_id=operation_id,
                case_id=authorization.case_id,
                operator_id=authorization.operator_id,
                device=fresh_dev,
                method=authorization.selected_method,
                requested_timestamp=requested_ts,
                start_timestamp=start_ts,
                completion_timestamp=completion_ts,
                controller_result=ctrl_status,
                verification_result=verif_result,
                warnings=fresh_dev.warnings,
                previous_audit_hash=self.audit.latest_hash,
            )
            self.audit.log_event(
                operation_id=operation_id,
                case_id=authorization.case_id,
                operator_id=authorization.operator_id,
                event_type=SanitizeEventType.ERASURE_PROOF_CREATED,
                device=fresh_dev,
                result="SUCCESS",
                details={"proofHash": proof.proof_hash},
            )

        # Step 7: FORGE Erasure Assurance Score
        chain_ok, _ = self.audit.verify_chain_integrity()
        identity_consistent = True
        if re_discovered:
            ok, _ = self.discovery.verify_identity_consistency(fresh_dev, re_discovered)
            identity_consistent = ok

        ctrl_status = adapter.get_sanitize_status(fresh_dev)
        assurance = ForgeAssuranceService.calculate_score(
            device=fresh_dev,
            method=authorization.selected_method,
            verification_result=verif_result,
            controller_result=ctrl_status,
            identity_consistent=identity_consistent,
            audit_chain_valid=chain_ok,
        )

        # Step 8: Machine-Readable JSON Report
        report = SanitizationReportGenerator.generate_report(
            case_id=authorization.case_id,
            operator_id=authorization.operator_id,
            operation_id=operation_id,
            device=fresh_dev,
            policy=policy,
            method=authorization.selected_method,
            execution_result=exec_result,
            verification_result=verif_result,
            assurance_score=assurance,
            proof=proof,
            audit_reference=self.audit.latest_hash,
            missing_evidence=missing_evidence,
            recommendation=recommendation,
        )

        self._operations[operation_id] = report
        return report

    def get_operation_report(self, operation_id: str) -> SanitizationReport | None:
        return self._operations.get(operation_id)
