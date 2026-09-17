# Secure Drive Sanitization Module — Safety & Safeguards Specification
**SIH 2026 — Problem Statement 26149**

> [!CAUTION]
> **CRITICAL WARNING:** Media sanitization is irreversible. Executing physical drive sanitization commands permanently obliterates magnetic domains and flash transistor charges. No recovery mechanism, deep carving tool, or forensic reconstruction technique can restore sanitized blocks.

---

## 1. Safety Architecture

The module implements **five mandatory defensive gates** before any hardware command reaches a storage controller:

```
[Target Device Request]
          |
          v
[1. System Host Drive Filter]   ----(Target is /, /boot, swap, C:)----> [ABORT: DEVICE_IS_SYSTEM_DISK]
          |
          v
[2. Mounted Filesystem Check]   ----(Partitions mounted)------------> [ABORT: DEVICE_MOUNTED]
          |
          v
[3. Operator Identity Match]    ----(Serial / Model Mismatch)---------> [ABORT: DEVICE_IDENTITY_MISMATCH]
          |
          v
[4. Destructive Confirmation]   ----(explicitConfirm != true)---------> [ABORT: DESTRUCTIVE_CONFIRMATION_MISSING]
          |
          v
[5. Pre-Execution Re-Check]     ----(Attribute drift / swap)----------> [ABORT: DEVICE_IDENTITY_MISMATCH]
          |
          v
[Execution on Controller]
```

---

## 2. Active Host Disk Protection

To prevent accidental wipe of the workstation running the forensic engine:
1. **Linux System Device Detection**:
   - Parses `/proc/mounts` to identify block devices backing `/`, `/boot`, `/boot/efi`, `/etc`, `/var`, `/usr`.
   - Parses `/proc/swaps` to identify active swap partitions.
   - Resolves partition nodes (e.g. `/dev/nvme0n1p2`) to base controllers (`/dev/nvme0n1`).
   - Flags target devices with `systemDisk = True` and rejects all sanitization attempts.
2. **Windows System Device Detection**:
   - Queries PowerShell `Get-Disk` for `IsBoot` and `IsSystem` flags.
   - Queries `Get-Partition` to detect active drive letter `C:`.
   - Rejects any operation targeting the physical drive hosting the Windows installation.
3. **macOS System Device Detection**:
   - Queries `diskutil info -plist /` and `mount` to identify the base physical disk backing the active APFS root container or `/System/Volumes/Data`.
   - Flags the boot disk (e.g. `/dev/disk0`) with `systemDisk = True` and rejects all sanitization attempts.

---

## 3. Human Authorization Requirements

Every execution payload (`SafetyAuthorization`) requires explicit investigator intent:
* `operatorId`: Identifier of the examiner.
* `caseId`: Official case tracking number.
* `reason`: Legal or administrative justification.
* `devicePath`: Target path (e.g. `/dev/nvme1n1`).
* `modelConfirmation`: Case-insensitive exact string match of the physical hardware model.
* `serialConfirmation`: Case-insensitive exact string match of the physical hardware serial number.
* `selectedMethod`: Must match one of the controller's supported methods.
* `explicitDestructiveConfirmation`: Boolean `true` explicitly verifying permanent data destruction.

---

## 4. Hardware Verification vs. Execution Success

A critical design requirement is separating **Execution Success** from **Sanitization Verification**:
* **Command Return Code 0 $\neq$ Erasure Verified**: A controller process may return 0 simply because the asynchronous command was received.
* **Controller Status Log**: The controller's internal NVMe Sanitize Status Log (`SSTAT`) must be polled until it reports code `0x101`, `0x102`, or `0x103`.
* **Independent Block Sampling**: The engine samples 10 block regions across the addressable LBA space (start, 25%, 50%, 75%, end) and calculates Shannon entropy:
  $$H(X) = -\sum_{i=1}^{256} P(x_i) \log_2 P(x_i)$$
  If non-zero residual user bytes or dirty forensic patterns are discovered, the engine terminates with status:
  ```json
  {
    "status": "SANITIZATION_NOT_VERIFIED",
    "missingEvidence": ["Sample block verification: residual or unverified data blocks detected"],
    "recommendation": "Device cannot be certified as sanitized. Retain custody and utilize approved external physical destruction procedure."
  }
  ```

---

## 5. Mock / Demonstration Mode

To evaluate and demonstrate the full sanitization lifecycle safely during SIH presentations without risking laptop or test bench SSDs, the engine includes a hardware-free simulation engine (`MockSanitizationAdapter` and `MockNVMeDevice`).

This allows end-to-end evaluation of:
* Capability discovery
* Deterministic policy formulation
* Dry-run preview
* Strict authorization validation
* Hardware controller failure simulation
* Residual data / unverified detection
* Tamper-evident cryptographic proof and SHA-256 audit chaining.

---

## 6. SIH Prototype Disclaimer

This software was developed as a submission for **Smart India Hackathon 2026 (Problem Statement 26149)**.
* It is an experimental academic/hackathon prototype.
* It has not undergone formal laboratory certification under NIST SP 800-88 Rev. 1 or IEEE 2883-2022.
* Production deployments must utilize certified test media and follow official institutional Standard Operating Procedures (SOPs).
