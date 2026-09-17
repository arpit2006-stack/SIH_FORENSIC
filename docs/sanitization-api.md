# Secure Drive Sanitization Module — REST API Specification
**SIH 2026 — Problem Statement 26149**

> [!WARNING]
> **SIH Prototype Notice:** This API interface is developed for air-gapped forensic workstation environments. Real destructive execution (`/api/sanitization/execute` with `executionMode: "REAL_EXECUTION"`) permanently destroys data on targeted media.

---

## 1. Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/devices` | List all discovered physical & mock storage devices |
| `GET` | `/api/devices/:id` | Get detailed metadata & capabilities for a specific device |
| `POST` | `/api/devices/:id/analyze` | Run storage intelligence & generate sanitization policy |
| `POST` | `/api/sanitization/plan` | Generate sanitization policy for a target path |
| `POST` | `/api/sanitization/dry-run` | Execute non-destructive dry run (default mode) |
| `POST` | `/api/sanitization/execute` | Execute sanitization under strict human safety authorization |
| `GET` | `/api/sanitization/:opId/status` | Query execution telemetry and status |
| `GET` | `/api/sanitization/:opId/verification` | Retrieve independent verification checks & FORGE score |
| `GET` | `/api/sanitization/:opId/proof` | Retrieve cryptographic Erasure Proof & SHA-256 hash |
| `GET` | `/api/sanitization/:opId/report` | Retrieve full machine-readable JSON forensic report |
| `GET` | `/api/sanitization/audit/verify` | Validate cryptographic SHA-256 audit chain integrity |

---

## 2. Request & Response Schemas

### `GET /api/devices`
**Query Parameters**:
- `includeMock` (bool, default `true`): Include registered mock devices for demonstration.

**Sample Response**:
```json
{
  "status": "SUCCESS",
  "devices": [
    {
      "devicePath": "/dev/mock_nvme0n1",
      "controllerPath": "/dev/mock_nvme0",
      "type": "NVME_SSD",
      "vendor": "Samsung",
      "model": "Samsung SSD 980 PRO 1TB (MOCK)",
      "serial": "S5GXNF0R876543",
      "firmware": "5B2QGXA7",
      "capacityBytes": 1000204886016,
      "logicalBlockSize": 512,
      "physicalBlockSize": 4096,
      "interface": "NVMe",
      "filesystems": [],
      "mounted": false,
      "mountPoints": [],
      "removable": false,
      "systemDisk": false,
      "encryption": false,
      "sanitizeCapabilities": {
        "cryptoEraseSupported": true,
        "blockEraseSupported": true,
        "overwriteSupported": true,
        "sanitizeCommandSupported": true,
        "noDeallocateModifiesMedia": true,
        "rawCapabilities": { "sanicap": 7 }
      },
      "warnings": []
    }
  ]
}
```

---

### `POST /api/sanitization/dry-run`
**Request Body**:
```json
{
  "devicePath": "/dev/mock_nvme0n1",
  "method": "CRYPTO_ERASE",
  "operatorId": "OP-EXAMINER-1",
  "caseId": "CASE-2026-09"
}
```

**Response**:
```json
{
  "status": "SUCCESS",
  "dryRun": {
    "mode": "DRY_RUN",
    "operationId": "dryrun-b2910f",
    "device": "/dev/mock_nvme0n1",
    "controller": "/dev/mock_nvme0",
    "method": "CRYPTO_ERASE",
    "command": "nvme sanitize /dev/mock_nvme0 --sanact=start-crypto-erase",
    "destructive": true,
    "executed": false,
    "verificationPlan": [
      "Poll NVMe Sanitize Status Log until completion",
      "Verify Sanitize Status Code (SSTAT) equals 0x101/0x102/0x103",
      "Sample 10 block regions across logical block space",
      "Confirm block entropy equals 0.0 or wipe pattern match",
      "Re-validate device identity to prevent mismatch"
    ],
    "simulated": true
  }
}
```

---

### `POST /api/sanitization/execute`
**Request Body (`SafetyAuthorization`)**:
```json
{
  "operatorId": "OP-EXAMINER-1",
  "caseId": "CASE-2026-09",
  "reason": "Court-ordered digital evidence sanitization",
  "devicePath": "/dev/mock_nvme0n1",
  "modelConfirmation": "Samsung SSD 980 PRO 1TB (MOCK)",
  "serialConfirmation": "S5GXNF0R876543",
  "selectedMethod": "CRYPTO_ERASE",
  "explicitDestructiveConfirmation": true,
  "executionMode": "REAL_EXECUTION"
}
```

**Response (`SanitizationReport`)**:
```json
{
  "status": "SUCCESS",
  "report": {
    "reportType": "ERASURE",
    "status": "COMPLETED",
    "caseId": "CASE-2026-09",
    "operatorId": "OP-EXAMINER-1",
    "operationId": "op-39ae901",
    "timestamp": "2026-09-13T12:00:00Z",
    "method": "CRYPTO_ERASE",
    "verification": {
      "status": "VERIFIED",
      "checks": [
        { "checkName": "Command Execution Status", "passed": true, "details": "SUCCESS" },
        { "checkName": "Controller Sanitize Status Log", "passed": true, "details": "SSTAT: 0x101" },
        { "checkName": "Device Identity Consistency", "passed": true, "details": "Consistent" },
        { "checkName": "Sample Block Verification", "passed": true, "details": "Sampled 10 blocks. Zeroed: 10." }
      ],
      "controllerStatusCode": "0x101"
    },
    "assurance": {
      "score": 95,
      "maxScore": 100,
      "level": "EXEMPLARY",
      "rationale": "Full hardware controller purge, zero-entropy sample verification, and unbroken audit chain."
    },
    "proof": {
      "operationId": "op-39ae901",
      "proofHash": "c57922427c60ac459768373c318c4081457b8907d62ce0117465010073135e0b",
      "previousAuditHash": "67dc27f002779fc441542d8ce4e6141aa0cfa0665cf90d617709a5430a17cd44"
    },
    "auditReference": "95da0294312ec31815f85353d5f352dbaddec76548751cf27ec16d0c8c5a31da",
    "missingEvidence": [],
    "recommendation": "Drive sanitization successfully verified. Media is cleared for re-use or decommission."
  }
}
```

---

## 3. Error Responses

| Code | HTTP Status | Description |
|---|---|---|
| `DEVICE_IS_SYSTEM_DISK` | 400 | Device is active root/boot/swap OS host drive |
| `DEVICE_MOUNTED` | 400 | Device contains mounted partitions |
| `DEVICE_IDENTITY_MISMATCH` | 400 | Model, serial, or capacity mismatch |
| `AUTHORIZATION_REQUIRED` | 400 | Missing operator ID, case ID, or justification |
| `DESTRUCTIVE_CONFIRMATION_MISSING` | 400 | `explicitDestructiveConfirmation: true` not provided |
| `UNSUPPORTED_SANITIZATION` | 400 | Storage controller lacks support for selected sanitize action |
| `PRIVILEGE_REQUIRED` | 400 | Process lacks OS root / Administrator rights for block access |
| `DEVICE_NOT_FOUND` | 404 | Target block path does not exist on host |
