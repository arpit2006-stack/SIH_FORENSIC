# Secure Drive Sanitization Module — Architecture Specification
**SIH 2026 — Problem Statement 26149**
**Component:** Secure Drive Sanitization Subsystem

> [!WARNING]
> **SIH Prototype Notice:** This system is an engineering prototype designed for SIH 2026 evaluation. It is not an officially accredited NIST SP 800-88 Rev. 1 or IEEE 2883-2022 certified commercial media sanitization instrument. Real execution on hardware permanently destroys data.

---

## 1. System Overview & Core Philosophy

The Secure Drive Sanitization Module is engineered under the principle:
> **"Do not build a glorified wrapper around nvme-cli. Understand the storage device, inspect its physical capabilities, select the appropriate supported sanitization strategy, execute it safely with multi-attribute safeguards, verify the result independently, and provide cryptographic evidence of what actually happened."**

```
                     +---------------------------------------+
                     |            REST API / CLI             |
                     +---------------------------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |     SanitizationOperationService      |
                     +---------------------------------------+
                                         |
        +--------------------------------+--------------------------------+
        |                                |                                |
        v                                v                                v
+---------------------+           +-------------------+           +--------------------+
|   Device Discovery  |           |  Policy Engine    |           |    Safety Gate     |
| (Linux/Win/Mac/Mock)|           |  (Deterministic)  |           | (Root/Mounted Lock)|
+---------------------+           +-------------------+           +--------------------+
        |                                                                 |
        v                                                                 v
+------------------+                                           +--------------------+
|  Storage Intel   |                                           |  Hardware Adapters |
| (SANICAP Bits)   |                                           | (NVMe / ATA / Mock)|
+------------------+                                           +--------------------+
                                                                          |
                                                                          v
                                                               +--------------------+
                                                               |  Physical Storage  |
                                                               +--------------------+
                                                                          |
        +--------------------------------+--------------------------------+
        |                                |                                |
        v                                v                                v
+------------------+           +-------------------+           +--------------------+
|   Verification   |           |   Erasure Proof   |           |    FORGE Score     |
| (Log + Sampling) |           |  (Canonical SHA)  |           | (5-Factor Metric)  |
+------------------+           +-------------------+           +--------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |  SanitizationAudit & Forensic Report  |
                     +---------------------------------------+
```

---

## 2. Component Pipeline

1. **Device Discovery (`discovery.py`)**:
   - Cross-platform block device discovery supporting Linux (`/sys/block`, `lsblk`, `udevadm`), Windows (`Get-Disk`, `Get-Partition`), macOS (`diskutil list/info -plist`), and Mock simulation.
   - Collects device path, controller path, serial, model, firmware, capacity, logical/physical block size, filesystem types, mount points, and removable status.
   - Automatically detects active host root `/`, `/boot`, active swap, Windows `C:` partition, and macOS APFS root/system container to protect the host OS.

2. **Storage Intelligence (`intelligence.py`)**:
   - Classifies storage media into `NVME_SSD`, `SATA_SSD`, `HDD`, `USB`, or `UNKNOWN`.
   - Queries hardware controller capabilities (e.g. NVMe `SANICAP` register bits for Crypto Erase, Block Erase, Overwrite, and No-Deallocate Modifies Media).

3. **Storage-Aware Policy Engine (`policy.py`)**:
   - Deterministic, explainable rule engine (zero cloud/AI dependency for safety decisions).
   - Recommends the highest-assurance supported sanitization method (Crypto Erase -> Block Erase -> Overwrite).
   - Generates a granular verification plan.

4. **Safety & Human Authorization Gate (`safety.py`)**:
   - Blocks active system disks (`DEVICE_IS_SYSTEM_DISK`) and mounted partitions (`DEVICE_MOUNTED`).
   - Requires operator ID, forensic case ID, legal reason, exact model string match, and exact serial number match.
   - Re-checks device identity immediately before execution to prevent physical drive swapping.

5. **Sanitization Adapters (`adapters/`)**:
   - `NvmeSanitizationAdapter`: Communicates with NVMe controllers via isolated subprocess argument vectors (never raw shell concatenation), polls the Sanitize Status Log, and performs multi-point block sampling.
   - `AtaSanitizationAdapter`: Implements ATA Security Erase and Overwrite abstractions for SATA SSDs and HDDs.
   - `MockSanitizationAdapter`: Simulates standard, system, mounted, failing, timeout, and unverified devices without touching physical storage (100% SIH-safe demonstration on Linux, Windows, and macOS).
   - `UnsupportedSanitizationAdapter`: Explicitly rejects uncertified devices.

6. **Erasure Verification Engine (`verification.py`)**:
   - Independent 4-stage verification:
     1. Command process exit code check.
     2. Controller Sanitize Status Log (`SSTAT` code `0x101`/`0x102`/`0x103`).
     3. Multi-point sample block read across capacity range computing Shannon entropy (checks for complete zeroing / wipe patterns).
     4. Pre/post device identity persistence check.
   - Returns `VERIFIED`, `NOT_VERIFIED`, or `FAILED`.
   - Never converts `NOT_VERIFIED` into a false success.

7. **Erasure Proof Service (`proof.py`)**:
   - Generates canonicalized JSON representations of execution metadata, controller responses, and verification checks.
   - Computes SHA-256 hash chained to the latest audit log entry:
     $$\text{proofHash} = \text{SHA256}(\text{canonicalProof} + \text{previousAuditHash})$$

8. **FORGE Erasure Assurance Score (`assurance.py`)**:
   - Internal 0–100 deterministic scoring across 5 factors:
     * Controller Completion: 30 pts
     * Supported Method: 25 pts
     * Independent Verification Checks: 20 pts
     * Device Identity Consistency: 10 pts
     * Cryptographic Audit Integrity: 10 pts
   - Levels: Exemplary (90–100), High (75–89), Moderate (50–74), Insufficient (< 50).

9. **Audit Logger (`audit.py`)**:
   - Records all 12 sanitization lifecycle events with SHA-256 hash chaining.
   - Validates event chain integrity on demand.

10. **Forensic JSON Reporting (`reporting.py`)**:
    - Generates complete, machine-readable JSON reports detailing device identity, policy rationale, execution telemetry, verification checks, proof hashes, and corrective recommendations for `SANITIZATION_NOT_VERIFIED` states.
