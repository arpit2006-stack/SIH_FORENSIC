# Product Requirements Document (PRD)
**Module:** Secure Drive & Targeted File Sanitization Engine
**Project Codename:** Project ForensiWipe
**Target Environment:** 100% Air-Gapped / Offline Digital Forensic Workstation
**Applicable Standards:** NIST SP 800-88 Rev 1, IEEE 2883-2022, DoD 5220.22-M, ISO/IEC 27037, Section 63 BSA 2023
**Revision:** v3.0 — Enterprise Architecture & Legal Chain of Custody Specification

---

## 1. Executive Summary

This Product Requirements Document (PRD) defines the architectural, functional, security, and evidentiary requirements for **Module 1 (Physical Media Sanitization)** and **Module 2 (Targeted File & Slack Space Sanitization)** of the ForensiWipe platform.

ForensiWipe provides defense-grade, court-admissible data sanitization across physical storage devices (NVMe SSDs, SATA SSDs, HDDs, USB flash memory, external drives) and active filesystem objects. The engine eliminates data remanence across accessible LBA ranges, wear-leveled blocks, overprovisioned sectors, and cluster slack spaces.

Every operation is governed by a **deterministic, storage-aware policy engine**, audited through a **tamper-evident SHA-256 / HMAC cryptographic ledger**, and certified under **Section 63(4) of the Bharatiya Sakshya Adhiniyam (BSA), 2023** and **ISO/IEC 27037:2012**.

---

## 2. Core Architectural Invariant & Legal Principles

```text
DISCOVER
   ↓
IDENTIFY
   ↓
CHECK PRIVILEGES
   ↓
CHECK CAPABILITIES
   ↓
SELECT DOCUMENTED INTERFACE
   ↓
VALIDATE TARGET
   ↓
REQUEST EXPLICIT AUTHORIZATION
   ↓
REVALIDATE TARGET (ANTI-HOTSWAP)
   ↓
EXECUTE
   ↓
VERIFY
   ↓
AUDIT & CERTIFY
```

### Mandatory Legal & Forensic Invariants:
1. **Zero Silent Fallback (NIST SP 800-88 / IEEE 2883)**: If a requested hardware-level sanitize command (e.g., NVMe Cryptographic Purge or ATA Enhanced Security Erase) is rejected by the device controller or unsupported, the engine **MUST FAIL SAFELY** with a typed diagnostic exception. It must **NEVER** silently downgrade to filesystem formatting, OS deletion, or simple zero-fill without explicit operator re-authorization. Falsely certifying a Purge when only a Clear was performed constitutes evidence spoliation and legal perjury.
2. **Pre-Execution Target Revalidation (Anti-Hot-Swap Gate)**: Hot-plugging USB drives or external docks on Windows and Linux can dynamically re-assign drive letters and device indices (e.g., `PhysicalDrive1` $\to$ `PhysicalDrive2` or `/dev/sdb` $\to$ `/dev/sdc`). Immediately before issuing destructive commands, the engine must re-interrogate the bus to confirm that serial number, capacity, and vendor match the initial authorization. Any discrepancy halts execution immediately.
3. **Host System/Boot Disk Gating**: Active operating system partitions, boot loaders (`EFI`, `IsBoot`), and system volumes (`C:`, `/`, `/boot`, `/etc`) are strictly locked by a kernel-level safety gate to prevent self-destruction of the forensic examination workstation.
4. **Operation-Specific Privilege (Principle of Least Privilege)**: Discovery and metadata inspection run in unprivileged mode. Elevated tokens (`UAC Administrator` on Windows, `root/CAP_SYS_RAWIO` on Linux) are checked and required only for direct controller IOCTLs and raw sector access.
5. **No Undocumented Backdoors**: All commands are restricted to published, standardized storage protocols (NVMe Express Base Specification 2.0, ATA/ATAPI Command Set ACS-4, USB Mass Storage Class, SCSI Primary Commands).

---

## 3. Subsystem Architecture & Functional Requirements

```
backend/sanitization/
├── discovery.py       # Universal Multi-OS Device Discovery (Windows, Linux, macOS)
├── privilege.py       # Operation-Specific Privilege & Token Elevation Manager
├── models.py          # Domain Models, Typings & Canonical Serialization
├── policy.py          # Storage-Aware Deterministic Policy Engine
├── safety.py          # Multi-Stage Safety Gates & Identity Interlocks
├── service.py         # End-to-End Orchestrator (Dry-Run, Live Run, Revalidation)
├── verification.py    # Stratified Sector Sampling & Shannon Entropy Analysis
├── proof.py           # Cryptographic Erasure Proof & Merkle Chain Hash
├── audit.py           # Immutable HMAC-SHA256 Audit Logger
├── file_eraser.py     # Targeted File, Directory & 4KB Cluster Slack Scrubber
├── intelligence.py    # Firmware & SMART Health Telemetry Inspector
└── adapters/          # Documented Storage Controller Adapters
    ├── nvme.py        # NVMe Sanitize / Format Controller IOCTLs
    ├── ata.py         # ATA Security Erase / Enhanced Security Erase
    ├── mock.py        # Offline Forensic Testbench & Virtual Sector Emulator
    └── unsupported.py # Safe Terminal Adapter for Non-Compliant Devices
```

---

### Subsystem 1: Universal Device Discovery & Identity (`discovery.py`)

* **FR1.1 — Multi-OS Hardware Probing**:
  * **Windows**: Dynamically interrogates storage subsystem via PowerShell (`Get-Disk`, `Get-Partition`) and Win32 IOCTLs (`IOCTL_STORAGE_QUERY_PROPERTY`). Captures physical disk number, bus type (NVMe, SATA, USB, SCSI), friendly name, serial number, partition styles, and assigned drive letters.
  * **Linux**: Parses `lsblk -J -b` JSON hierarchy and `/sys/block` directly. Resolves base block devices from partitions (e.g. `/dev/nvme0n1p2` $\to$ `/dev/nvme0n1`). Reads `/proc/mounts` and `/proc/swaps` to identify active root volumes.
  * **macOS**: Queries `diskutil list -plist` and `diskutil info -plist /` to map APFS containers, physical parent disks, and system volumes (`/System/Volumes/Data`).
* **FR1.2 — Typed `DeviceInfo` Normalization**: Every detected device is mapped into an immutable `DeviceInfo` object containing:
  * `device_path`: Hardware target string (e.g. `\\.\PhysicalDrive1`, `/dev/nvme0n1`, `/dev/sdb`).
  * `storage_type`: Normalized enum (`NVME_SSD`, `SATA_SSD`, `HDD`, `USB`, `UNKNOWN`).
  * `serial`: Raw factory hardware serial number (cleaned of controller padding).
  * `capacity_bytes`, `logical_block_size` (e.g. 512B), `physical_block_size` (e.g. 4096B).
  * `system_disk`: Boolean flag set to `True` if device hosts boot/OS filesystems.
  * `mounted`: Boolean flag with active mount points list.
* **FR1.3 — Dynamic Re-Discovery**: Exposes `revalidate_target()` to freshly query the operating system immediately prior to destructive execution.

---

### Subsystem 2: Deterministic Storage Policy Engine (`policy.py`)

The policy engine maps hardware architecture to certified sanitization standards without human guesswork:

| Storage Class | Certified Standard | Recommended Method | Technical Mechanism | Assurance Level |
| :--- | :--- | :--- | :--- | :--- |
| **NVMe SSD** | IEEE 2883-2022 / NIST Purge | `CRYPTO_ERASE` | NVMe Sanitize Controller Command with Cryptographic Erase (`0x04`). Replaces internal Media Encryption Key (MEK), rendering all NAND blocks unreadable instantly. | **HIGH** |
| **NVMe SSD (No MEK)** | IEEE 2883-2022 / NIST Purge | `BLOCK_ERASE` | NVMe Sanitize Command with Block Erase (`0x02`). Sends electrical pulse resetting all accessible, spare, and overprovisioned flash cells. | **HIGH** |
| **SATA SSD** | NIST SP 800-88 Purge | `ATA_ENHANCED_SECURITY_ERASE` | Firmware-level erase modifying all logical and wear-leveled flash blocks, including vendor-specific reserves. | **HIGH** |
| **Magnetic HDD** | NIST SP 800-88 Clear | `ATA_SECURITY_ERASE` or `OVERWRITE` | Overwrites magnetic domains across all user-addressable tracks with certified bit patterns. | **HIGH / MEDIUM** |
| **USB Removable** | NIST SP 800-88 Clear | `OVERWRITE` | Multi-pass zero/pattern overwrite across full physical LBA space. Flags warning regarding unaddressable wear-leveling reserves. | **LOW / MEDIUM** |

* **FR2.1 — Policy Evaluation**: `StoragePolicyEngine.evaluate_policy(device)` returns a `SanitizationPolicy` containing supported methods, recommended method, assurance level, technical rationale, and a step-by-step verification plan.

---

### Subsystem 3: Multi-Stage Safety Gates & Interlocks (`safety.py`)

* **FR3.1 — Two-Stage Cryptographic Confirmation**:
  * Step 1: Operator enters valid `case_id`, `operator_id`, and judicial `reason`.
  * Step 2: Operator must type the **exact target serial number** into the safety interlock.
* **FR3.2 — Target Model Verification**:
  * Compares operator confirmation against actual hardware model. Strips mount brackets (e.g., `(D:)`) automatically to prevent false identity mismatch triggers.
* **FR3.3 — Mounted Filesystem Disarm**:
  * For removable USB drives on Windows, executes `fsutil volume dismount` cleanly.
  * If unmount fails or device is locked, raises `DEVICE_MOUNTED` exception; never executes against an actively mounted filesystem.
* **FR3.4 — System Disk Hard Block**:
  * Raises `DEVICE_IS_SYSTEM_DISK` if target is identified as `system_disk=True`. Bypassing this check is physically prevented.

---

### Subsystem 4: Hardware Controller Adapters (`adapters/`)

* **FR4.1 — NVMe Adapter (`adapters/nvme.py`)**:
  * Queries NVMe Controller Identify Data structure (`OACS` bit 2) to check `Sanitize Capabilities`.
  * Issues `IOCTL_STORAGE_MANAGE_DATA_SET_ATTRIBUTES` or raw NVMe Command via Windows Storage IOCTLs / Linux `/dev/nvmeX` ioctl.
  * Polls Sanitize Status Log (`Log ID 0x81`) until `Sanitize Progress` reaches 100% and status returns `0x101` (Crypto Erase Successful) or `0x102` (Block Erase Successful).
* **FR4.2 — ATA Adapter (`adapters/ata.py`)**:
  * Inspects ATA Identify Word 128 (Security Status). Confirms drive is not frozen or password-locked.
  * Sets temporary security password, issues `ATA SECURITY ERASE UNIT` / `ENHANCED`, and verifies completion registers.
* **FR4.3 — Physical Sector Overwrite Engine**:
  * Direct block-level streaming using unbuffered sector I/O (`FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH` on Windows; `O_DIRECT` on Linux).
  * Streams 1MB chunk buffers:
    * Pass 1: Constant `0x00` (Zero Fill).
    * Pass 2: Constant `0xFF` (One Fill).
    * Pass 3: Cryptographic PRNG random bytes (`secrets.token_bytes`).
* **FR4.4 — Mock Adapter (`adapters/mock.py`)**:
  * Full in-memory and file-backed virtual sector emulator for offline forensic lab testing and validation without risking hardware.

---

### Subsystem 5: Targeted File & Cluster Slack Eraser (`file_eraser.py`)

* **FR5.1 — Multi-Pass File Shredding**: Overwrites active file byte space with multi-pass zero/pattern/random passes.
* **FR5.2 — Forensic Slack Space Scrubbing (4KB Cluster Boundary)**:
  * Calculates file cluster overhang: $\text{Slack Bytes} = (\text{Cluster Size} - (\text{File Size} \pmod{\text{Cluster Size}})) \pmod{\text{Cluster Size}}$.
  * Opens low-level file stream and writes pattern bytes into the slack boundary between logical EOF and physical cluster allocation end, wiping residual metadata remnants.
* **FR5.3 — File Metadata Scrubbing**: Truncates file length to 0 bytes, renames file to random hexadecimal characters, and unlinks it from the directory table.

---

### Subsystem 6: Forensic Verification & Entropy Analysis (`verification.py`)

* **FR6.1 — Stratified LBA Sampling**:
  * Reads sample blocks across **Head** (first 1024 sectors), **Body** (10 stratified intervals across capacity), and **Tail** (final 1024 sectors).
* **FR6.2 — Shannon Entropy Verification**:
  * Computes entropy $H$ for each sampled block:
    $$H = -\sum_{i=0}^{255} p_i \log_2(p_i)$$
  * For Zero Fill / NIST Clear: requires $H \equiv 0.0$ (or within $10^{-6}$).
  * For Block Erase: verifies all blocks return `0x00` or factory deallocated pattern.
  * Any detected non-zero pattern immediately raises `VERIFICATION_FAILED`.

---

### Subsystem 7: Immutable Audit Ledger & Section 63 BSA Certification (`audit.py`, `proof.py`)

* **FR7.1 — HMAC-SHA256 Merkle Chaining**:
  * Every lifecycle event (`DEVICE_DISCOVERED`, `AUTHORIZATION_GRANTED`, `DEVICE_REVALIDATION_PASSED`, `SANITIZATION_COMPLETED`, `SANITIZATION_VERIFIED`) is recorded in an append-only ledger (`audit_ledger.jsonl`).
  * Each record includes `previous_hash`, generating a cryptographically verifiable Merkle chain:
    $$\text{Hash}_n = \text{SHA256}(\text{CanonicalJSON}(\text{Event}_n) \mathbin{\Vert} \text{Hash}_{n-1})$$
* **FR7.2 — Tamper-Evident Erasure Proof (`proof.py`)**:
  * Generates signed, standalone JSON proof containing hardware parameters, controller return codes, verification results, operator details, and cryptographic custody hash.
* **FR7.3 — Section 63(4) BSA Digital Evidence Certificate**:
  * Exports formatted legal certificate per Section 63(4) of the Bharatiya Sakshya Adhiniyam, 2023.
  * Includes dual-signature attestation fields for the forensic operator and independent technical examiner.

---

## 4. Error Model & Fault Matrix (`models.py`)

Platform failures are normalized into standardized, human-readable error categories:

| Error Code | Trigger Condition | Mandatory System Action |
| :--- | :--- | :--- |
| `DEVICE_IDENTITY_MISMATCH` | Confirmation serial/model doesn't match hardware | Abort. No writes issued. Log security alert. |
| `DEVICE_REVALIDATION_FAILED` | Pre-execution re-probe detects disk swap or index shift | Abort immediately. Log `ANTI_SWAP_HALT`. |
| `DEVICE_IS_SYSTEM_DISK` | Target hosts active OS / boot filesystems | Hard block. Refuse execution. |
| `DEVICE_MOUNTED` | Target has active filesystem mounts that cannot unmount | Block execution until cleanly dismounted. |
| `UNSUPPORTED_SANITIZATION` | Controller lacks capability for requested method | Fail safely. Ban silent fallback. |
| `VERIFICATION_FAILED` | Sampled sectors contain residual data or entropy $> 0$ | Flag `SANITIZATION_FAILED`. Log non-compliant blocks. |
| `PRIVILEGE_REQUIRED` | Process lacks administrative IOCTL token | Prompt operator for elevation; do not attempt bypass. |

---

## 5. Technology Stack & Interface Specifications

| Layer | Technologies / Dependencies |
| :--- | :--- |
| **Core Runtime** | Python 3.10+ (Standard Library: `ctypes`, `subprocess`, `hashlib`, `hmac`, `secrets`, `dataclasses`) |
| **Mathematical Analysis** | `numpy`, `scipy` (Shannon Entropy, Stratified sampling distributions) |
| **Windows Hardware I/O** | Win32 API via `ctypes` (`CreateFileW`, `DeviceIoControl`, `FSCTL_LOCK_VOLUME`, `FSCTL_DISMOUNT_VOLUME`) |
| **Linux Hardware I/O** | Direct block device `/dev/*` ioctls (`SG_IO`, `NVME_IOCTL_ADMIN_CMD`, `BLKDISCARD`) |
| **HTTP / REST API Daemon**| FastAPI / Starlette, Uvicorn (Port 8000) |
| **Frontend Presentation** | Next.js 14, React 18, Tailwind CSS, Lucide Icons, TypeScript |

---

## 6. Traceability Matrix (Requirements to Implementation)

| PRD Requirement | Implemented In Source File | Verification Test |
| :--- | :--- | :--- |
| Universal Discovery & System Disk Detection | `backend/sanitization/discovery.py` | `tests/test_device_discovery.py` |
| Operation-Specific Privilege Checking | `backend/sanitization/privilege.py` | `tests/test_privilege.py` |
| Deterministic Storage Policy Engine | `backend/sanitization/policy.py` | `tests/test_policy.py` |
| Two-Stage Safety Gate & Interlocks | `backend/sanitization/safety.py` | `tests/test_safety.py` |
| Pre-Execution Target Revalidation | `backend/sanitization/service.py` | `tests/test_sanitization_service.py` |
| NVMe Hardware Sanitize / Purge IOCTL | `backend/sanitization/adapters/nvme.py` | `tests/test_nvme_adapter.py` |
| ATA Security Erase Adapter | `backend/sanitization/adapters/ata.py` | `tests/test_ata_adapter.py` |
| Multi-Pass Sector Overwrite Engine | `backend/sanitization/adapters/mock.py`, `service.py` | `tests/test_overwrite.py` |
| Targeted File & 4KB Slack Scrubber | `backend/sanitization/file_eraser.py` | `audit_evidence/t_p0_slack_trim.py` |
| Stratified Entropy Verification | `backend/sanitization/verification.py` | `tests/test_verification.py` |
| HMAC-SHA256 Cryptographic Audit Ledger | `backend/sanitization/audit.py` | `tests/test_audit.py` |
| Tamper-Evident Erasure Proof & Certificate | `backend/sanitization/proof.py`, `reporting.py` | `tests/test_proof.py` |
