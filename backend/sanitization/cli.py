"""Command-Line Interface for Secure Drive Sanitization Module.

Provides offline terminal commands for device discovery, policy analysis,
dry-run execution, safety authorization, and audit log verification.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from sanitization.api import start_sanitization_server
from sanitization.models import (
    OperationMode,
    SafetyAuthorization,
    SanitizationErrorCode,
    SanitizationException,
    SanitizeMethod,
)
from sanitization.reporting import SanitizationReportGenerator
from sanitization.service import SanitizationOperationService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ForensiWipe — Secure Drive Sanitization Module (SIH PS 26149)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. list-devices
    p_list = subparsers.add_parser("list-devices", help="Discover and display attached block storage devices")
    p_list.add_argument("--no-mock", action="store_true", help="Exclude simulated mock devices")
    p_list.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # 2. analyze
    p_analyze = subparsers.add_parser("analyze", help="Inspect device hardware capabilities and evaluate sanitization policy")
    p_analyze.add_argument("device_path", help="Path to device (e.g. /dev/mock_nvme0n1 or \\\\.\\PhysicalDrive1)")
    p_analyze.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # 3. dry-run
    p_dry = subparsers.add_parser("dry-run", help="Execute safe, non-destructive sanitization dry-run (Default mode)")
    p_dry.add_argument("device_path", help="Path to device")
    p_dry.add_argument("--method", choices=["CRYPTO_ERASE", "BLOCK_ERASE", "OVERWRITE"], help="Sanitization method")
    p_dry.add_argument("--operator-id", default="OP-TERMINAL", help="Operator ID")
    p_dry.add_argument("--case-id", default="CASE-TERMINAL", help="Case ID")

    # 4. execute
    p_exec = subparsers.add_parser("execute", help="Execute hardware sanitization (requires explicit authorization)")
    p_exec.add_argument("device_path", help="Path to device")
    p_exec.add_argument("--method", required=True, choices=["CRYPTO_ERASE", "BLOCK_ERASE", "OVERWRITE"], help="Method")
    p_exec.add_argument("--operator-id", required=True, help="Investigator / Operator ID")
    p_exec.add_argument("--case-id", required=True, help="Forensic Case ID")
    p_exec.add_argument("--reason", required=True, help="Sanitization justification / court order")
    p_exec.add_argument("--model-confirm", required=True, help="Exact model name confirmation")
    p_exec.add_argument("--serial-confirm", required=True, help="Exact serial number confirmation")
    p_exec.add_argument("--destructive-confirm", action="store_true", help="Explicit confirmation of destructive erasure")
    p_exec.add_argument("--real", action="store_true", help="Engage REAL_EXECUTION mode (default is DRY_RUN)")

    # 5. verify-audit
    p_audit = subparsers.add_parser("verify-audit", help="Verify cryptographic SHA-256 audit chain integrity")

    # 6. serve
    p_serve = subparsers.add_parser("serve", help="Launch local REST API HTTP server")
    p_serve.add_argument("--port", type=int, default=8000, help="Port to bind (default 8000)")
    p_serve.add_argument("--host", default="127.0.0.1", help="Host address")

    args = parser.parse_args()
    service = SanitizationOperationService()

    try:
        if args.command == "list-devices":
            devices = service.list_devices(include_mock=not args.no_mock)
            if args.json:
                print(json.dumps([d.to_dict() for d in devices], indent=2))
            else:
                print(f"\n{'DEVICE PATH':<24} {'TYPE':<12} {'CAPACITY':<10} {'SYSTEM':<8} {'MOUNTED':<8} {'MODEL'}")
                print("=" * 85)
                for d in devices:
                    cap_gb = f"{d.capacity_bytes / (1024**3):.1f} GB"
                    sys_str = "YES (SYS)" if d.system_disk else "No"
                    mnt_str = "YES" if d.mounted else "No"
                    print(f"{d.device_path:<24} {d.storage_type.value:<12} {cap_gb:<10} {sys_str:<8} {mnt_str:<8} {d.model}")
                print()
            return 0

        elif args.command == "analyze":
            dev, policy = service.plan_sanitization(args.device_path)
            if args.json:
                print(json.dumps({"device": dev.to_dict(), "policy": policy.to_dict()}, indent=2))
            else:
                print(f"\nDevice Analysis: {dev.device_path}")
                print(f"Model:           {dev.model}")
                print(f"Serial:          {dev.serial}")
                print(f"Storage Type:    {dev.storage_type.value}")
                print(f"Capacity:        {dev.capacity_bytes / (1024**3):.2f} GB")
                print(f"System Disk:     {'YES (PROTECTED)' if dev.system_disk else 'No'}")
                print(f"Mounted:         {'YES' if dev.mounted else 'No'}")
                print("-" * 50)
                print(f"Recommended Method: {policy.recommended_method.value}")
                print(f"Assurance Level:    {policy.assurance.value}")
                print(f"Rationale:          {policy.reason}")
                print("Verification Plan:")
                for step in policy.verification_plan:
                    print(f"  * {step}")
                if policy.warnings:
                    print("Warnings:")
                    for w in policy.warnings:
                        print(f"  ! {w}")
                print()
            return 0

        elif args.command == "dry-run":
            method = SanitizeMethod(args.method) if args.method else None
            plan = service.execute_dry_run(
                device_path=args.device_path,
                method=method,
                operator_id=args.operator_id,
                case_id=args.case_id,
            )
            print(json.dumps(plan, indent=2))
            return 0

        elif args.command == "execute":
            mode = OperationMode.REAL_EXECUTION if args.real else OperationMode.DRY_RUN
            auth = SafetyAuthorization(
                operator_id=args.operator_id,
                case_id=args.case_id,
                reason=args.reason,
                device_path=args.device_path,
                model_confirmation=args.model_confirm,
                serial_confirmation=args.serial_confirm,
                selected_method=SanitizeMethod(args.method),
                explicit_destructive_confirmation=args.destructive_confirm,
                execution_mode=mode,
            )
            report = service.execute_sanitization(auth)
            print(SanitizationReportGenerator.to_json(report, indent=2))
            return 0

        elif args.command == "verify-audit":
            valid, err = service.audit.verify_chain_integrity()
            if valid:
                print(f"[OK] Audit chain integrity verified. Latest Hash: {service.audit.latest_hash}")
                return 0
            else:
                print(f"[FAIL] Audit integrity failed: {err}")
                return 1

        elif args.command == "serve":
            print(f"Starting ForensiWipe Sanitization API on {args.host}:{args.port}...")
            server = start_sanitization_server(port=args.port, host=args.host)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                server.server_close()
                print("\nServer stopped.")
            return 0

    except SanitizationException as exc:
        print(f"\n[ERROR: {exc.code.value}] {exc.message}", file=sys.stderr)
        if exc.details:
            print(json.dumps(exc.details, indent=2), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"\n[UNEXPECTED ERROR] {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
