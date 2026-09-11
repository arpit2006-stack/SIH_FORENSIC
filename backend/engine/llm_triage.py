"""Phase 3 (FR3.3-FR3.4): Deterministic Gating and Local Air-Gapped Artifact Triage.

Air-gapped: ZERO network connections, ZERO remote API imports.
All inference runs on localhost via llama-cpp-python over a quantized GGUF model.

Pipeline:
  1. DeterministicPatternFilter scans text with compiled regex + optional YARA rules.
  2. If hits exist, LocalForensicLLM classifies and summarises.
  3. Disagreement gating: if LLM contradicts the pattern filter, the artifact is
     flagged DISPUTED_MANUAL_REVIEW. No hits → LOW_PRIORITY_GENERAL, no LLM call.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category / Priority enums (strings for JSON interop)
# ---------------------------------------------------------------------------
CATEGORIES = frozenset({
    "FINANCIAL", "IDENTITY", "CREDENTIAL", "SYSTEM_LOG", "UNCLASSIFIED",
    "DISPUTED_MANUAL_REVIEW", "LOW_PRIORITY_GENERAL",
})
PRIORITIES = frozenset({"P1_CRITICAL", "P2_HIGH", "P3_LOW"})

# Default category→priority mapping used when the LLM is bypassed.
_DEFAULT_PRIORITY = {
    "FINANCIAL": "P1_CRITICAL",
    "IDENTITY": "P1_CRITICAL",
    "CREDENTIAL": "P1_CRITICAL",
    "SYSTEM_LOG": "P3_LOW",
    "UNCLASSIFIED": "P3_LOW",
    "LOW_PRIORITY_GENERAL": "P3_LOW",
    "DISPUTED_MANUAL_REVIEW": "P2_HIGH",
}


# ---------------------------------------------------------------------------
# 1. Deterministic Rule & Pattern Gate  (FR3.4)
# ---------------------------------------------------------------------------
def _luhn_valid(digits: str) -> bool:
    """Validate a card number string via the Luhn algorithm."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# Pre-compiled regex patterns for Indian financial/identity/credential artifacts.
_PATTERNS: dict[str, re.Pattern] = {
    # --- Financial ---
    "IFSC_CODE": re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
    "CREDIT_CARD": re.compile(
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|"
        r"3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"
    ),
    "TRANSACTION_LEDGER": re.compile(
        r"(?:debit|credit|txn|transaction|ledger|settlement|"
        r"NEFT|RTGS|IMPS|UPI)[:\s]",
        re.IGNORECASE,
    ),
    # --- Identity ---
    "PAN_CARD": re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    "PASSPORT": re.compile(r"\b[A-Z][0-9]{7}\b"),  # Indian passport format
    "AADHAAR": re.compile(r"\b[2-9][0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b"),
    "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "PHONE_IN": re.compile(r"\b(?:\+91[\s-]?)?[6-9][0-9]{9}\b"),
    # --- Credentials / System Keys ---
    "PRIVATE_KEY": re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
    ),
    "AWS_ACCESS_KEY": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "AWS_SECRET_KEY": re.compile(r"\b[A-Za-z0-9/+=]{40}\b"),
    "API_TOKEN": re.compile(
        r"(?:api[_-]?key|api[_-]?token|bearer|authorization)[:\s=]+\S{16,}",
        re.IGNORECASE,
    ),
    "GENERIC_SECRET": re.compile(
        r"(?:password|passwd|secret|token)[:\s=]+\S{8,}",
        re.IGNORECASE,
    ),
}

# Map pattern names → baseline categories.
_PATTERN_CATEGORY: dict[str, str] = {
    "IFSC_CODE": "FINANCIAL",
    "CREDIT_CARD": "FINANCIAL",
    "TRANSACTION_LEDGER": "FINANCIAL",
    "PAN_CARD": "IDENTITY",
    "PASSPORT": "IDENTITY",
    "AADHAAR": "IDENTITY",
    "EMAIL": "IDENTITY",
    "PHONE_IN": "IDENTITY",
    "PRIVATE_KEY": "CREDENTIAL",
    "AWS_ACCESS_KEY": "CREDENTIAL",
    "AWS_SECRET_KEY": "CREDENTIAL",
    "API_TOKEN": "CREDENTIAL",
    "GENERIC_SECRET": "CREDENTIAL",
}


@dataclass
class PatternResult:
    """Output of the deterministic filter."""
    filter_hits: List[str]
    baseline_category: str  # majority vote across matched pattern categories


class DeterministicPatternFilter:
    """Scans extracted text using pre-compiled regex rules (and optional YARA)
    for Indian financial, identification, and credential artifacts.

    Returns pattern hit names and a baseline category.
    """

    def __init__(self, extra_yara_path: Optional[str] = None):
        self._patterns = _PATTERNS
        self._yara_rules = None
        if extra_yara_path and os.path.isfile(extra_yara_path):
            try:
                import yara  # noqa: WPS433
                self._yara_rules = yara.compile(filepath=extra_yara_path)
                log.info("YARA rules loaded from %s", extra_yara_path)
            except Exception as exc:
                log.warning("YARA compilation failed (%s); regex-only mode", exc)

    def scan(self, text: str) -> PatternResult:
        """Run every regex + optional YARA over *text*. Luhn-validates card hits."""
        hits: list[str] = []

        for name, pat in self._patterns.items():
            for m in pat.finditer(text):
                matched = m.group()
                # For credit cards, require Luhn validity.
                if name == "CREDIT_CARD":
                    digits = re.sub(r"\D", "", matched)
                    if not _luhn_valid(digits):
                        continue
                # For AWS_SECRET_KEY, require proximity to "aws" context.
                if name == "AWS_SECRET_KEY":
                    start = max(0, m.start() - 80)
                    context = text[start:m.start()].lower()
                    if "aws" not in context and "secret" not in context:
                        continue
                hits.append(name)
                break  # one match per pattern type is sufficient

        # Optional YARA pass.
        if self._yara_rules is not None:
            try:
                yara_matches = self._yara_rules.match(data=text.encode("utf-8", "replace"))
                for ym in yara_matches:
                    tag = f"YARA:{ym.rule}"
                    if tag not in hits:
                        hits.append(tag)
            except Exception as exc:
                log.warning("YARA scan error: %s", exc)

        # Baseline category: majority-vote across the categories of matched patterns.
        if not hits:
            return PatternResult(filter_hits=[], baseline_category="UNCLASSIFIED")

        cat_counts: dict[str, int] = {}
        for h in hits:
            cat = _PATTERN_CATEGORY.get(h, "UNCLASSIFIED")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        baseline = max(cat_counts, key=lambda c: cat_counts[c])
        return PatternResult(filter_hits=hits, baseline_category=baseline)


# ---------------------------------------------------------------------------
# 2. Air-Gapped LLM Orchestrator  (FR3.3)
# ---------------------------------------------------------------------------
# Structured prompt template.  The model MUST return valid JSON.
_SYSTEM_PROMPT = (
    "You are a forensic evidence classifier. Given extracted text from a recovered "
    "disk artifact, respond ONLY with a JSON object having exactly these keys:\n"
    '  "category": one of FINANCIAL, IDENTITY, CREDENTIAL, SYSTEM_LOG, UNCLASSIFIED\n'
    '  "priority": one of P1_CRITICAL, P2_HIGH, P3_LOW\n'
    '  "plain_english_summary": a concise 1-2 sentence summary of the content\n'
    "Do NOT output anything outside the JSON object."
)

_USER_TEMPLATE = "Classify the following recovered artifact text:\n\n{text}"


def _detect_vram_mb() -> int:
    """Best-effort VRAM query without network calls. Returns 0 if no GPU is found."""
    # nvidia-smi on PATH?
    if not shutil.which("nvidia-smi"):
        return 0
    try:
        import subprocess  # noqa: WPS433
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            return int(lines[0].strip()) if lines else 0
    except Exception:
        pass
    return 0


def _safe_parse_llm_json(raw: str) -> dict:
    """Extract the first JSON object from the LLM response, handling markdown fences and junk."""
    # Strip markdown code fences if present.
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (with optional language tag) and closing fence.
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Try direct parse first.
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Fallback: find first { ... } substring.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(cleaned[start:end + 1])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # Irrecoverable: return empty dict so caller uses fallback.
    log.warning("LLM output was not valid JSON; falling back to deterministic category")
    return {}


def _normalise_llm_output(parsed: dict) -> dict:
    """Clamp the LLM's JSON into the allowed enum values; fill missing keys."""
    cat = str(parsed.get("category", "UNCLASSIFIED")).upper().strip()
    if cat not in CATEGORIES:
        cat = "UNCLASSIFIED"
    pri = str(parsed.get("priority", "P3_LOW")).upper().strip()
    if pri not in PRIORITIES:
        pri = _DEFAULT_PRIORITY.get(cat, "P3_LOW")
    summary = str(parsed.get("plain_english_summary", ""))[:500]
    return {"category": cat, "priority": pri, "plain_english_summary": summary}


class LocalForensicLLM:
    """Interfaces with llama-cpp-python loading an air-gapped GGUF model.

    Dynamic offloading: if dedicated VRAM is detected, sets n_gpu_layers = -1
    (offload everything); otherwise n_gpu_layers = 0 (pure CPU) with n_threads = 4.

    The model path defaults to ``models/<first .gguf found>`` or a known filename.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        n_ctx: int = 2048,
        n_threads: int = 4,
        max_tokens: int = 512,
        temperature: float = 0.0,
    ):
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._llm = None  # lazy: constructed on first call

        # Resolve model path.
        if model_path is None:
            model_path = self._find_gguf()
        self._model_path = model_path

        # Determine GPU offloading.
        vram = _detect_vram_mb()
        if vram > 0:
            self._n_gpu_layers = -1  # offload all layers
            log.info("VRAM detected (%d MB); GPU offload enabled (n_gpu_layers=-1)", vram)
        else:
            self._n_gpu_layers = 0
            log.info("No dedicated VRAM; CPU-only mode (n_threads=%d)", n_threads)

        self._n_ctx = n_ctx
        self._n_threads = n_threads

    # -- model discovery --------------------------------------------------- #
    @staticmethod
    def _find_gguf(search_dir: str = "models") -> str:
        """Locate the first .gguf file under *search_dir*."""
        p = Path(search_dir)
        if p.is_dir():
            for f in sorted(p.iterdir()):
                if f.suffix.lower() == ".gguf":
                    return str(f)
        # Fallback to a well-known default name.
        default = os.path.join(search_dir, "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf")
        return default

    # -- lazy init --------------------------------------------------------- #
    def _ensure_loaded(self) -> None:
        if self._llm is not None:
            return
        if not os.path.isfile(self._model_path):
            raise FileNotFoundError(
                f"GGUF model not found at '{self._model_path}'. "
                "Place a quantized GGUF model (e.g. Qwen2.5-1.5B-Instruct-Q4_K_M.gguf) "
                "in the models/ directory."
            )
        from llama_cpp import Llama  # noqa: WPS433  (air-gapped, localhost only)

        self._llm = Llama(
            model_path=self._model_path,
            n_ctx=self._n_ctx,
            n_gpu_layers=self._n_gpu_layers,
            n_threads=self._n_threads,
            verbose=False,
        )
        log.info("GGUF model loaded: %s (gpu_layers=%d)", self._model_path, self._n_gpu_layers)

    # -- inference --------------------------------------------------------- #
    def classify(self, text: str) -> dict:
        """Send *text* through the local GGUF model and return normalised JSON.

        Returns ``{"category": ..., "priority": ..., "plain_english_summary": ...}``
        with safe fallbacks if the model produces garbage.
        """
        self._ensure_loaded()

        # Truncate text to fit context window (leave room for system + output).
        max_input_chars = (self._n_ctx - self.max_tokens - 100) * 3  # rough char→token
        truncated = text[:max_input_chars] if len(text) > max_input_chars else text

        try:
            response = self._llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _USER_TEMPLATE.format(text=truncated)},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            raw = response["choices"][0]["message"]["content"]  # type: ignore[index]
        except Exception as exc:
            log.error("LLM inference failed: %s", exc)
            return _normalise_llm_output({})

        parsed = _safe_parse_llm_json(raw)
        return _normalise_llm_output(parsed)


# ---------------------------------------------------------------------------
# 3. Disagreement Gating Logic  (FR3.4)
# ---------------------------------------------------------------------------
# Singleton-ish holders (created once per process, reused across calls).
_filter_instance: Optional[DeterministicPatternFilter] = None
_llm_instance: Optional[LocalForensicLLM] = None


def _get_filter() -> DeterministicPatternFilter:
    global _filter_instance
    if _filter_instance is None:
        _filter_instance = DeterministicPatternFilter()
    return _filter_instance


def _get_llm() -> LocalForensicLLM:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LocalForensicLLM()
    return _llm_instance


def triage_artifact(
    artifact_text: str,
    *,
    det_filter: Optional[DeterministicPatternFilter] = None,
    llm: Optional[LocalForensicLLM] = None,
) -> Dict:
    """Triage a single recovered artifact's extracted text.

    Pipeline:
      1. Deterministic pattern scan.
      2. If hits → LLM classification → agreement check.
      3. No hits → LOW_PRIORITY_GENERAL (no LLM call, save compute).

    Returns a dict with keys:
      - ``category``: final resolved category
      - ``priority``: P1/P2/P3
      - ``plain_english_summary``: LLM-generated or static fallback
      - ``deterministic_hits``: list of pattern names
      - ``deterministic_category``: baseline from the pattern filter
      - ``llm_category``: raw LLM output category (or None if LLM was not invoked)
      - ``agreement``: "MATCH" | "DISPUTED" | "LLM_SKIPPED"
    """
    filt = det_filter or _get_filter()
    pr = filt.scan(artifact_text)

    result: Dict = {
        "deterministic_hits": pr.filter_hits,
        "deterministic_category": pr.baseline_category,
        "llm_category": None,
        "agreement": "LLM_SKIPPED",
    }

    # ---- No deterministic hits → LOW_PRIORITY_GENERAL, skip LLM ----
    if not pr.filter_hits:
        result.update(
            category="LOW_PRIORITY_GENERAL",
            priority="P3_LOW",
            plain_english_summary="No sensitive patterns detected; classified as low priority.",
        )
        return result

    # ---- Deterministic hits exist → invoke LLM ----
    try:
        llm_engine = llm or _get_llm()
        llm_out = llm_engine.classify(artifact_text)
    except FileNotFoundError:
        # No GGUF model available — fall back to deterministic-only.
        log.warning("GGUF model not found; using deterministic classification only")
        result.update(
            category=pr.baseline_category,
            priority=_DEFAULT_PRIORITY.get(pr.baseline_category, "P2_HIGH"),
            plain_english_summary="LLM unavailable; classification based on deterministic patterns only.",
            agreement="LLM_UNAVAILABLE",
        )
        return result

    result["llm_category"] = llm_out["category"]

    # ---- Agreement gating ----
    if llm_out["category"] == pr.baseline_category:
        # Perfect agreement: accept LLM output verbatim.
        result.update(
            category=llm_out["category"],
            priority=llm_out["priority"],
            plain_english_summary=llm_out["plain_english_summary"],
            agreement="MATCH",
        )
    else:
        # Disagreement: override to DISPUTED_MANUAL_REVIEW.
        log.warning(
            "DISPUTED: deterministic=%s vs LLM=%s — flagging for manual review",
            pr.baseline_category,
            llm_out["category"],
        )
        result.update(
            category="DISPUTED_MANUAL_REVIEW",
            priority="P2_HIGH",
            plain_english_summary=(
                f"CONFLICT: Pattern filter says {pr.baseline_category}, "
                f"LLM says {llm_out['category']}. "
                f"LLM summary: {llm_out['plain_english_summary']}"
            ),
            agreement="DISPUTED",
        )

    return result


# ---------------------------------------------------------------------------
# Self-check: python -m engine.llm_triage
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # ----- Test 1: Mock PAN record -----
    pan_text = (
        "Subject: Taxpayer verification\n"
        "Name: Rajesh Kumar\n"
        "PAN: ABCDE1234F\n"
        "Date of Birth: 15-03-1985\n"
        "Address: 42 MG Road, Bengaluru 560001\n"
        "Phone: +91 9876543210\n"
        "This document confirms the identity of the taxpayer for FY2025-26.\n"
    )
    filt = DeterministicPatternFilter()
    pr = filt.scan(pan_text)
    assert "PAN_CARD" in pr.filter_hits, f"PAN not detected: {pr.filter_hits}"
    assert pr.baseline_category == "IDENTITY", f"Expected IDENTITY, got {pr.baseline_category}"
    print(f"PAN scan: hits={pr.filter_hits} category={pr.baseline_category}")

    # Test triage_artifact without a real GGUF model (deterministic-only fallback).
    res_pan = triage_artifact(pan_text, det_filter=filt)
    assert res_pan["deterministic_category"] == "IDENTITY"
    assert res_pan["category"] in CATEGORIES
    assert res_pan["priority"] in PRIORITIES
    print(f"PAN triage: category={res_pan['category']} priority={res_pan['priority']} "
          f"agreement={res_pan['agreement']}")

    # ----- Test 2: Generic random log (no sensitive patterns) -----
    generic_log = (
        "2026-09-11 14:22:01 INFO  kernel: cpu0: resumed from idle\n"
        "2026-09-11 14:22:02 INFO  kernel: eth0: link up\n"
        "2026-09-11 14:22:03 INFO  systemd: Started session 42 of user admin\n"
        "2026-09-11 14:22:04 DEBUG sshd: received packet type 21\n"
        "2026-09-11 14:22:05 INFO  crond: running job /etc/cron.d/cleanup\n"
    )
    pr_log = filt.scan(generic_log)
    assert not pr_log.filter_hits, f"Generic log should have no hits: {pr_log.filter_hits}"
    assert pr_log.baseline_category == "UNCLASSIFIED"

    res_log = triage_artifact(generic_log, det_filter=filt)
    assert res_log["category"] == "LOW_PRIORITY_GENERAL"
    assert res_log["priority"] == "P3_LOW"
    assert res_log["agreement"] == "LLM_SKIPPED"
    print(f"Log triage: category={res_log['category']} priority={res_log['priority']} "
          f"agreement={res_log['agreement']}")

    # ----- Test 3: Financial artifact -----
    finance_text = (
        "Bank: State Bank of India\n"
        "IFSC: SBIN0001234\n"
        "Transaction: NEFT transfer of INR 50,000 on 2026-08-15\n"
        "Beneficiary: Acme Corp Ltd.\n"
    )
    pr_fin = filt.scan(finance_text)
    assert "IFSC_CODE" in pr_fin.filter_hits
    assert pr_fin.baseline_category == "FINANCIAL"
    res_fin = triage_artifact(finance_text, det_filter=filt)
    assert res_fin["deterministic_category"] == "FINANCIAL"
    print(f"Finance triage: category={res_fin['category']} priority={res_fin['priority']}")

    # ----- Test 4: Credential artifact -----
    cred_text = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGy...\n"
        "-----END RSA PRIVATE KEY-----\n"
    )
    pr_cred = filt.scan(cred_text)
    assert "PRIVATE_KEY" in pr_cred.filter_hits
    assert pr_cred.baseline_category == "CREDENTIAL"
    print(f"Credential scan: hits={pr_cred.filter_hits}")

    # ----- Test 5: Luhn validation -----
    assert _luhn_valid("4111111111111111"), "Visa test number must pass Luhn"
    assert not _luhn_valid("4111111111111112"), "Modified digit must fail Luhn"

    # ----- Test 6: Safe JSON parsing -----
    assert _safe_parse_llm_json('{"category":"FINANCIAL","priority":"P1_CRITICAL","plain_english_summary":"ok"}') \
           == {"category": "FINANCIAL", "priority": "P1_CRITICAL", "plain_english_summary": "ok"}
    assert _safe_parse_llm_json('```json\n{"category":"IDENTITY"}\n```') == {"category": "IDENTITY"}
    assert _safe_parse_llm_json("garbage output") == {}
    assert _safe_parse_llm_json('Sure! Here is the JSON: {"category":"CREDENTIAL"} hope it helps!') \
           == {"category": "CREDENTIAL"}
    print("JSON parser handles clean, fenced, embedded, and garbage outputs")

    # ----- Test 7: Normalisation -----
    assert _normalise_llm_output({})["category"] == "UNCLASSIFIED"
    assert _normalise_llm_output({"category": "BOGUS"})["category"] == "UNCLASSIFIED"
    assert _normalise_llm_output({"category": "FINANCIAL", "priority": "INVALID"})["priority"] == "P1_CRITICAL"
    print("Normalisation clamps enums correctly")

    print()
    print("[STATE_TRANSITION: NODE_04_COMPLETE -> PROCEED_TO_NODE_05]")
