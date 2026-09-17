"""Data models and type definitions for Secure Drive Sanitization Module.

Defines schemas for DeviceInfo, StorageType, SanitizeCapabilityInfo,
SanitizationPolicy, SafetyAuthorization, VerificationResult, ErasureProof,
ForgeAssuranceScore, AuditEvent, and SanitizationReport.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class StorageType(str, Enum):
    NVME_SSD = "NVME_SSD"
    SATA_SSD = "SATA_SSD"
    HDD = "HDD"
    USB = "USB"
    UNKNOWN = "UNKNOWN"


class SanitizeMethod(str, Enum):
    CRYPTO_ERASE = "CRYPTO_ERASE"
    BLOCK_ERASE = "BLOCK_ERASE"
    OVERWRITE = "OVERWRITE"
    ATA_SECURITY_ERASE = "ATA_SECURITY_ERASE"
    ATA_ENHANCED_SECURITY_ERASE = "ATA_ENHANCED_SECURITY_ERASE"
    UNSUPPORTED = "UNSUPPORTED"


class AssuranceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class OperationMode(str, Enum):
    DRY_RUN = "DRY_RUN"
    REAL_EXECUTION = "REAL_EXECUTION"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    FAILED = "FAILED"


class SanitizeEventType(str, Enum):
    DEVICE_DISCOVERED = "DEVICE_DISCOVERED"
    CAPABILITIES_READ = "CAPABILITIES_READ"
    SANITIZATION_PLANNED = "SANITIZATION_PLANNED"
    DRY_RUN_EXECUTED = "DRY_RUN_EXECUTED"
    AUTHORIZATION_GRANTED = "AUTHORIZATION_GRANTED"
    SANITIZATION_STARTED = "SANITIZATION_STARTED"
    SANITIZATION_COMPLETED = "SANITIZATION_COMPLETED"
    SANITIZATION_FAILED = "SANITIZATION_FAILED"
    VERIFICATION_STARTED = "VERIFICATION_STARTED"
    SANITIZATION_VERIFIED = "SANITIZATION_VERIFIED"
    SANITIZATION_NOT_VERIFIED = "SANITIZATION_NOT_VERIFIED"
    ERASURE_PROOF_CREATED = "ERASURE_PROOF_CREATED"


class SanitizationErrorCode(str, Enum):
    DEVICE_IDENTITY_MISMATCH = "DEVICE_IDENTITY_MISMATCH"
    DEVICE_IS_SYSTEM_DISK = "DEVICE_IS_SYSTEM_DISK"
    DEVICE_MOUNTED = "DEVICE_MOUNTED"
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    DESTRUCTIVE_CONFIRMATION_MISSING = "DESTRUCTIVE_CONFIRMATION_MISSING"
    UNSUPPORTED_SANITIZATION = "UNSUPPORTED_SANITIZATION"
    INSUFFICIENT_ASSURANCE = "INSUFFICIENT_ASSURANCE"
    PRIVILEGE_REQUIRED = "PRIVILEGE_REQUIRED"
    DEVICE_NOT_FOUND = "DEVICE_NOT_FOUND"
    COMMAND_TIMEOUT = "COMMAND_TIMEOUT"
    EXECUTION_FAILED = "EXECUTION_FAILED"


class SanitizationException(Exception):
    """Base exception for sanitization failures."""

    def __init__(self, code: SanitizationErrorCode, message: str, details: dict[str, Any] | None = None):
        super().__init__(f"[{code.value}] {message}")
        self.code = code
        self.message = message
        self.details = details or {}


def current_iso_timestamp() -> str:
    """Return the current UTC timestamp formatted in ISO 8601 with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(data: Any) -> str:
    """Serialize dictionary or dataclass to deterministic, sorted, whitespace-stripped JSON string."""
    if hasattr(data, "to_dict"):
        data = data.to_dict()
    elif isinstance(data, (dict, list)):
        pass
    else:
        try:
            data = asdict(data)
        except TypeError:
            pass
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


@dataclass
class SanitizeCapabilityInfo:
    crypto_erase_supported: bool = False
    block_erase_supported: bool = False
    overwrite_supported: bool = False
    sanitize_command_supported: bool = False
    no_deallocate_modifies_media: bool = False
    raw_capabilities: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cryptoEraseSupported": self.crypto_erase_supported,
            "blockEraseSupported": self.block_erase_supported,
            "overwriteSupported": self.overwrite_supported,
            "sanitizeCommandSupported": self.sanitize_command_supported,
            "noDeallocateModifiesMedia": self.no_deallocate_modifies_media,
            "rawCapabilities": self.raw_capabilities,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SanitizeCapabilityInfo:
        return cls(
            crypto_erase_supported=bool(data.get("cryptoEraseSupported", False)),
            block_erase_supported=bool(data.get("blockEraseSupported", False)),
            overwrite_supported=bool(data.get("overwriteSupported", False)),
            sanitize_command_supported=bool(data.get("sanitizeCommandSupported", False)),
            no_deallocate_modifies_media=bool(data.get("noDeallocateModifiesMedia", False)),
            raw_capabilities=data.get("rawCapabilities", {}),
        )


@dataclass
class DeviceInfo:
    device_path: str
    controller_path: str | None = None
    storage_type: StorageType = StorageType.UNKNOWN
    vendor: str = ""
    model: str = ""
    serial: str = ""
    firmware: str = ""
    capacity_bytes: int = 0
    logical_block_size: int = 512
    physical_block_size: int = 4096
    interface: str = "UNKNOWN"
    filesystems: list[str] = field(default_factory=list)
    mounted: bool = False
    mount_points: list[str] = field(default_factory=list)
    removable: bool = False
    system_disk: bool = False
    encryption: bool = False
    sanitize_capabilities: SanitizeCapabilityInfo | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "devicePath": self.device_path,
            "controllerPath": self.controller_path,
            "type": self.storage_type.value,
            "vendor": self.vendor,
            "model": self.model,
            "serial": self.serial,
            "firmware": self.firmware,
            "capacityBytes": self.capacity_bytes,
            "logicalBlockSize": self.logical_block_size,
            "physicalBlockSize": self.physical_block_size,
            "interface": self.interface,
            "filesystems": self.filesystems,
            "mounted": self.mounted,
            "mountPoints": self.mount_points,
            "removable": self.removable,
            "systemDisk": self.system_disk,
            "encryption": self.encryption,
            "sanitizeCapabilities": self.sanitize_capabilities.to_dict() if self.sanitize_capabilities else None,
            "warnings": self.warnings,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceInfo:
        cap_data = data.get("sanitizeCapabilities")
        return cls(
            device_path=data.get("devicePath", ""),
            controller_path=data.get("controllerPath"),
            storage_type=StorageType(data.get("type", StorageType.UNKNOWN.value)),
            vendor=data.get("vendor", ""),
            model=data.get("model", ""),
            serial=data.get("serial", ""),
            firmware=data.get("firmware", ""),
            capacity_bytes=int(data.get("capacityBytes", 0)),
            logical_block_size=int(data.get("logicalBlockSize", 512)),
            physical_block_size=int(data.get("physicalBlockSize", 4096)),
            interface=data.get("interface", "UNKNOWN"),
            filesystems=list(data.get("filesystems", [])),
            mounted=bool(data.get("mounted", False)),
            mount_points=list(data.get("mountPoints", [])),
            removable=bool(data.get("removable", False)),
            system_disk=bool(data.get("systemDisk", False)),
            encryption=bool(data.get("encryption", False)),
            sanitize_capabilities=SanitizeCapabilityInfo.from_dict(cap_data) if cap_data else None,
            warnings=list(data.get("warnings", [])),
        )


@dataclass
class SafetyAuthorization:
    operator_id: str
    case_id: str
    reason: str
    device_path: str
    model_confirmation: str
    serial_confirmation: str
    selected_method: SanitizeMethod
    explicit_destructive_confirmation: bool
    execution_mode: OperationMode = OperationMode.DRY_RUN
    timestamp: str = field(default_factory=current_iso_timestamp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operatorId": self.operator_id,
            "caseId": self.case_id,
            "reason": self.reason,
            "devicePath": self.device_path,
            "modelConfirmation": self.model_confirmation,
            "serialConfirmation": self.serial_confirmation,
            "selectedMethod": self.selected_method.value,
            "explicitDestructiveConfirmation": self.explicit_destructive_confirmation,
            "executionMode": self.execution_mode.value,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SafetyAuthorization:
        return cls(
            operator_id=data.get("operatorId", ""),
            case_id=data.get("caseId", ""),
            reason=data.get("reason", ""),
            device_path=data.get("devicePath", ""),
            model_confirmation=data.get("modelConfirmation", ""),
            serial_confirmation=data.get("serialConfirmation", ""),
            selected_method=SanitizeMethod(data.get("selectedMethod", SanitizeMethod.UNSUPPORTED.value)),
            explicit_destructive_confirmation=bool(data.get("explicitDestructiveConfirmation", False)),
            execution_mode=OperationMode(data.get("executionMode", OperationMode.DRY_RUN.value)),
            timestamp=data.get("timestamp", current_iso_timestamp()),
        )


@dataclass
class SanitizationPolicy:
    recommended_method: SanitizeMethod
    supported_methods: list[SanitizeMethod]
    assurance: AssuranceLevel
    reason: str
    verification_plan: list[str]
    warnings: list[str] = field(default_factory=list)
    verification_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendedMethod": self.recommended_method.value,
            "supportedMethods": [m.value for m in self.supported_methods],
            "assurance": self.assurance.value,
            "reason": self.reason,
            "verificationPlan": self.verification_plan,
            "warnings": self.warnings,
            "verificationRequired": self.verification_required,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SanitizationPolicy:
        return cls(
            recommended_method=SanitizeMethod(data.get("recommendedMethod", SanitizeMethod.UNSUPPORTED.value)),
            supported_methods=[SanitizeMethod(m) for m in data.get("supportedMethods", [])],
            assurance=AssuranceLevel(data.get("assurance", AssuranceLevel.NONE.value)),
            reason=data.get("reason", ""),
            verification_plan=list(data.get("verificationPlan", [])),
            warnings=list(data.get("warnings", [])),
            verification_required=bool(data.get("verificationRequired", True)),
        )


@dataclass
class VerificationCheck:
    check_name: str
    passed: bool
    details: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkName": self.check_name,
            "passed": self.passed,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VerificationCheck:
        return cls(
            check_name=data.get("checkName", ""),
            passed=bool(data.get("passed", False)),
            details=data.get("details", ""),
        )


@dataclass
class VerificationResult:
    status: VerificationStatus
    checks: list[VerificationCheck] = field(default_factory=list)
    controller_status_code: str | None = None
    details: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "checks": [c.to_dict() for c in self.checks],
            "controllerStatusCode": self.controller_status_code,
            "details": self.details,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VerificationResult:
        return cls(
            status=VerificationStatus(data.get("status", VerificationStatus.NOT_VERIFIED.value)),
            checks=[VerificationCheck.from_dict(c) for c in data.get("checks", [])],
            controller_status_code=data.get("controllerStatusCode"),
            details=data.get("details", ""),
            timestamp=data.get("timestamp", current_iso_timestamp()),
        )


@dataclass
class AssuranceFactor:
    name: str
    score: int
    max_score: int
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "maxScore": self.max_score,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssuranceFactor:
        return cls(
            name=data.get("name", ""),
            score=int(data.get("score", 0)),
            max_score=int(data.get("maxScore", 0)),
            description=data.get("description", ""),
        )


@dataclass
class ForgeAssuranceScore:
    score: int
    max_score: int = 100
    level: str = "INSUFFICIENT"
    factors: dict[str, AssuranceFactor] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "maxScore": self.max_score,
            "level": self.level,
            "factors": {k: v.to_dict() for k, v in self.factors.items()},
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ForgeAssuranceScore:
        factors_dict = {}
        for k, v in data.get("factors", {}).items():
            factors_dict[k] = AssuranceFactor.from_dict(v)
        return cls(
            score=int(data.get("score", 0)),
            max_score=int(data.get("maxScore", 100)),
            level=data.get("level", "INSUFFICIENT"),
            factors=factors_dict,
            rationale=data.get("rationale", ""),
        )


@dataclass
class ErasureProof:
    operation_id: str
    case_id: str
    operator_id: str
    device_path: str
    model: str
    serial: str
    firmware: str
    capacity: int
    interface: str
    sanitization_method: SanitizeMethod
    requested_timestamp: str
    start_timestamp: str
    completion_timestamp: str
    controller_result: dict[str, Any]
    verification_result: VerificationResult
    verification_checks: list[VerificationCheck]
    warnings: list[str]
    previous_audit_hash: str
    proof_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operationId": self.operation_id,
            "caseId": self.case_id,
            "operatorId": self.operator_id,
            "devicePath": self.device_path,
            "model": self.model,
            "serial": self.serial,
            "firmware": self.firmware,
            "capacity": self.capacity,
            "interface": self.interface,
            "sanitizationMethod": self.sanitization_method.value,
            "requestedTimestamp": self.requested_timestamp,
            "startTimestamp": self.start_timestamp,
            "completionTimestamp": self.completion_timestamp,
            "controllerResult": self.controller_result,
            "verificationResult": self.verification_result.to_dict(),
            "verificationChecks": [c.to_dict() for c in self.verification_checks],
            "warnings": self.warnings,
            "previousAuditHash": self.previous_audit_hash,
            "proofHash": self.proof_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ErasureProof:
        return cls(
            operation_id=data.get("operationId", ""),
            case_id=data.get("caseId", ""),
            operator_id=data.get("operatorId", ""),
            device_path=data.get("devicePath", ""),
            model=data.get("model", ""),
            serial=data.get("serial", ""),
            firmware=data.get("firmware", ""),
            capacity=int(data.get("capacity", 0)),
            interface=data.get("interface", ""),
            sanitization_method=SanitizeMethod(data.get("sanitizationMethod", SanitizeMethod.UNSUPPORTED.value)),
            requested_timestamp=data.get("requestedTimestamp", ""),
            start_timestamp=data.get("startTimestamp", ""),
            completion_timestamp=data.get("completionTimestamp", ""),
            controller_result=data.get("controllerResult", {}),
            verification_result=VerificationResult.from_dict(data.get("verificationResult", {})),
            verification_checks=[VerificationCheck.from_dict(c) for c in data.get("verificationChecks", [])],
            warnings=list(data.get("warnings", [])),
            previous_audit_hash=data.get("previousAuditHash", ""),
            proof_hash=data.get("proofHash", ""),
        )


@dataclass
class AuditEvent:
    event_id: str
    operation_id: str
    case_id: str
    operator_id: str
    timestamp: str
    event_type: str
    device_identity: dict[str, Any]
    result: str
    details: dict[str, Any]
    previous_hash: str
    event_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id,
            "operationId": self.operation_id,
            "caseId": self.case_id,
            "operatorId": self.operator_id,
            "timestamp": self.timestamp,
            "eventType": self.event_type,
            "deviceIdentity": self.device_identity,
            "result": self.result,
            "details": self.details,
            "previousHash": self.previous_hash,
            "eventHash": self.event_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEvent:
        return cls(
            event_id=data.get("eventId", ""),
            operation_id=data.get("operationId", ""),
            case_id=data.get("caseId", ""),
            operator_id=data.get("operatorId", ""),
            timestamp=data.get("timestamp", ""),
            event_type=data.get("eventType", ""),
            device_identity=data.get("deviceIdentity", {}),
            result=data.get("result", ""),
            details=data.get("details", {}),
            previous_hash=data.get("previousHash", ""),
            event_hash=data.get("eventHash", ""),
        )


@dataclass
class SanitizationReport:
    report_type: str
    case_id: str
    operator_id: str
    operation_id: str
    timestamp: str
    device: DeviceInfo
    policy: SanitizationPolicy
    method: SanitizeMethod
    execution: dict[str, Any]
    verification: VerificationResult
    assurance: ForgeAssuranceScore
    proof: ErasureProof | None
    audit_reference: str
    status: str = "COMPLETED"
    missing_evidence: list[str] = field(default_factory=list)
    recommendation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "reportType": self.report_type,
            "status": self.status,
            "caseId": self.case_id,
            "operatorId": self.operator_id,
            "operationId": self.operation_id,
            "timestamp": self.timestamp,
            "device": self.device.to_dict(),
            "policy": self.policy.to_dict(),
            "method": self.method.value,
            "execution": self.execution,
            "verification": self.verification.to_dict(),
            "assurance": self.assurance.to_dict(),
            "proof": self.proof.to_dict() if self.proof else None,
            "auditReference": self.audit_reference,
            "missingEvidence": self.missing_evidence,
            "recommendation": self.recommendation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SanitizationReport:
        proof_data = data.get("proof")
        return cls(
            report_type=data.get("reportType", "ERASURE"),
            status=data.get("status", "COMPLETED"),
            case_id=data.get("caseId", ""),
            operator_id=data.get("operatorId", ""),
            operation_id=data.get("operationId", ""),
            timestamp=data.get("timestamp", ""),
            device=DeviceInfo.from_dict(data.get("device", {})),
            policy=SanitizationPolicy.from_dict(data.get("policy", {})),
            method=SanitizeMethod(data.get("method", SanitizeMethod.UNSUPPORTED.value)),
            execution=data.get("execution", {}),
            verification=VerificationResult.from_dict(data.get("verification", {})),
            assurance=ForgeAssuranceScore.from_dict(data.get("assurance", {})),
            proof=ErasureProof.from_dict(proof_data) if proof_data else None,
            audit_reference=data.get("auditReference", ""),
            missing_evidence=list(data.get("missingEvidence", [])),
            recommendation=data.get("recommendation"),
        )
