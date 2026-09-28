"""P0-7: audit-log tamper evidence, in-memory AND on-disk."""
import sys, sqlite3, os, tempfile
sys.path.insert(0, r"A:\SIH\SIH_FORENSIC\backend")
from sanitization.audit import SanitizationAuditLogger
from sanitization.models import SanitizeEventType

db = os.path.join(tempfile.mkdtemp(), "audit.db")
log = SanitizationAuditLogger(db_path=db)
for i in range(3):
    log.log_event(f"OP-{i}", "CASE-1", "OP-A", SanitizeEventType.SANITIZATION_COMPLETED,
                  {"devicePath": f"/dev/sd{i}", "model": "M", "serial": f"S{i}",
                   "capacityBytes": 1000, "storageType": "HDD"},
                  "SUCCESS", {"note": "clean"})
print("A) baseline in-memory verify:", log.verify_chain_integrity())

# --- Tamper 1: mutate an in-memory past event by one character
log._events[1].result = "SUCCESS "   # one byte added
print("B) in-memory single-byte tamper detected:", log.verify_chain_integrity())
log._events[1].result = "SUCCESS"

# --- Tamper 2: mutate the PERSISTED sqlite row (the thing a court would examine)
con = sqlite3.connect(db)
before = con.execute("SELECT result, details FROM sanitization_audit_events LIMIT 1 OFFSET 1").fetchone()
con.execute("UPDATE sanitization_audit_events SET result='FAILED' WHERE operation_id='OP-1'")
con.commit()
after = con.execute("SELECT result FROM sanitization_audit_events LIMIT 1 OFFSET 1").fetchone()
con.close()
print("C) sqlite row mutated:", before[0], "->", after[0])
print("   same-process verify_chain_integrity():", log.verify_chain_integrity(), "  <- reads _events, not the DB")

# --- Fresh process/instance: what a verifier would actually do
fresh = SanitizationAuditLogger(db_path=db)
print("D) FRESH logger over the tampered DB, verify_chain_integrity():", fresh.verify_chain_integrity())
print("   events loaded from DB:", len(fresh._events))
print("   -> any DB loader method?", [m for m in dir(fresh) if 'load' in m.lower() or 'read' in m.lower()] or "NONE")
