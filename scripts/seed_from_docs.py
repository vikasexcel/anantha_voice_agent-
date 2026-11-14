#!/usr/bin/env python3
"""Parse MVCAP answering script (docx) + staff directory (PDF) into seed data.

Usage:
  python scripts/seed_from_docs.py --dry-run
  python scripts/seed_from_docs.py --apply

Does not invent routing. Ambiguous rows are flagged in scripts/output/seed_review.json
and listed for docs/OPEN_QUESTIONS.md review.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOCX_PATH = DOCS / "MiamiValleyActionPartnership_AnsweringScript-LiveKit.docx"
PDF_PATH = DOCS / "MVCAP_ITFrontDesk_Directory_for_AnswerNet.pdf"
OUTPUT_DIR = ROOT / "scripts" / "output"

# Keyword titles as they appear in the script (source of truth order).
# "See: X" rows become alias_of. Do not invent keywords not in the docx.
KNOWN_KEYWORDS: list[str] = [
    "Accounts Payable",
    "AES",
    "Affordable Housing",
    "Air Conditioners – need a window unit",
    "Appeals",
    "Application",
    "Attorney",
    "Board of Trustees",
    "Camden Commons",
    "Car Repairs",
    "CenterPoint Energy",
    "Central Air / Air Conditioners – need a repair",
    "Clothing Assistance",
    "Clothing Bank",
    "Community Services Block Grant (CSBG)",
    "Credit Counseling",
    "CSBG",
    "Darke County",
    "Darke County MHA",
    "Disconnection",
    "Documentation",
    "Domestic Violence",
    "Donnellan Shelter",
    "Down Payment Assistance",
    "Driver’s License Reinstatement",
    "Eagles Nest",
    "Elected Official",
    "Electric Partnership Program (EPP)",
    "Eligibility",
    "Emergency Responders",
    "Emergency Shelter / Emergency Housing",
    "Employment Inquiries",
    "Energy Audit",
    "Eviction",
    "Fan – need a fan",
    "Finance",
    "Financial Counseling",
    "Fiscal",
    "Food",
    "Food Pantry",
    "Fox Run",
    "Furnace",
    "Generational Wealth",
    "Grants",
    "Greene County",
    "Harding Place",
    "HEAP",
    "Home Energy Assistance Program (HEAP",
    "Home Repair",
    "Homeless",
    "Housing Choice Voucher",
    "Housing Counseling",
    "Human Resources",
    "Jobs",
    "Law Enforcement",
    "Lawyer",
    "Lead Abatement",
    "Lead Hazard",
    "Leadership Team",
    "Legal Clinic",
    "Legal Matter",
    "LIHEAP",
    "Low Income Housing",
    "Metropolitan Housing Authority (MHA)",
    "MHA",
    "Micro Enterprise Program",
    "Monitoring",
    "Montgomery County",
    "Mortgage Assistance",
    "Mortgage Counseling",
    "National Fuel",
    "News",
    "Percentage of Income Payment Plan (PIPP)",
    "PIPP (Percentage of Income Payment Plan)",
    "Police",
    "PRC",
    "Preble County",
    "Preble MHA",
    "Press",
    "Prevention, Retention and Contingency (PRC)",
    "Property Taxes",
    "Quote",
    "Refrigerator Requests",
    "Rental Assistance",
    "Section 8 Voucher",
    "Student Enrollment Incentive",
    "Subcontractors",
    "Summer Crisis",
    "Transitional Shelter / Transitional Housing",
    "Transportation",
    "Utility Assistance",
    "VASH Voucher",
    "Veteran Housing",
    "Weatherization",
    "Willow Place",
    "Winter Crisis",
    "Workforce Development",
]

NO_EXTENSION_NAMES = {
    ("Adams", "Candis"),
    ("Martin", "Jade"),
    ("Robinson", "Donna"),
    ("Shinn", "Tacola"),
    ("Thompson", "Skylar"),
    ("Thompson", "Cailyn"),
}

AMBIGUOUS_EXTENSIONS = {
    # Script vs directory mismatches (OPEN_QUESTIONS #1–3)
    "821": "Utility Assistance disconnection target x821 is not in the staff directory.",
    "174": "Script lists Katie O’Donoghue Ly at x174; directory lists x157. Escalation is DO NOT TRANSFER.",
    "135": "Script lists Keianna Young at x135; directory lists x157. Escalation is DO NOT TRANSFER.",
}


@dataclass
class StaffRow:
    last_name: str
    first_legal: str
    first_preferred: str | None
    title: str | None
    extension: str | None
    external_number: str | None
    shareable: bool = True
    notes: str | None = None
    ambiguous: bool = False
    ambiguity_note: str | None = None


@dataclass
class RuleRow:
    keyword: str
    aliases: list[str] = field(default_factory=list)
    action_type: str = "say"
    message: str | None = None
    target: str | None = None
    county_branches: dict[str, Any] | None = None
    followup_question: str | None = None
    flow_definition: dict[str, Any] | None = None
    active: bool = True
    source_notes: str | None = None
    ambiguous: bool = False
    ambiguity_note: str | None = None


@dataclass
class StatusRow:
    effective_date: str
    message: str
    active: bool = True


@dataclass
class SeedPayload:
    staff: list[StaffRow]
    keyword_rules: list[RuleRow]
    status_updates: list[StatusRow]
    flags: list[str] = field(default_factory=list)


def normalize_dashes(text: str) -> str:
    return (
        text.replace("\u2013", "–")
        .replace("\u2014", "—")
        .replace("\u2019", "’")
        .replace("\u2018", "‘")
        .replace("\u201c", "“")
        .replace("\u201d", "”")
    )


def docx_paragraphs(path: Path) -> list[str]:
    from docx import Document

    doc = Document(str(path))
    paras: list[str] = []
    for p in doc.paragraphs:
        line = normalize_dashes(p.text).strip()
        if line:
            paras.append(line)
    # Also pull table cells if any (keyword table may be a Word table)
    for table in doc.tables:
        for row in table.rows:
            cells = [normalize_dashes(c.text).strip() for c in row.cells]
            cells = [c for c in cells if c]
            if not cells:
                continue
            if len(cells) >= 2 and cells[0].lower() != "keyword":
                # Represent as keyword then instruction block
                paras.append(cells[0])
                paras.append("\n".join(cells[1:]))
            else:
                for c in cells:
                    paras.append(c)
    return paras


def pdf_lines(path: Path) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    lines: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        for raw in text.splitlines():
            line = normalize_dashes(raw).strip()
            if line:
                lines.append(line)
    return lines


def parse_status_updates(paras: list[str]) -> list[StatusRow]:
    rows: list[StatusRow] = []
    # After STATUS UPDATES header, alternating Date / Info until OFFICE LOCATIONS
    try:
        start = next(i for i, p in enumerate(paras) if p.upper() == "STATUS UPDATES")
    except StopIteration:
        return rows

    i = start + 1
    # Skip "Date:" / "Info:" labels
    while i < len(paras) and paras[i] not in {"OFFICE LOCATIONS & HOURS", "GENERAL INFORMATION"}:
        line = paras[i]
        if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", line):
            eff = line
            i += 1
            if i < len(paras):
                msg = paras[i]
                # Convert m/d/yyyy → ISO
                m, d, y = eff.split("/")
                iso = date(int(y), int(m), int(d)).isoformat()
                rows.append(StatusRow(effective_date=iso, message=msg, active=True))
        i += 1
    return rows


def _keyword_index(paras: list[str]) -> dict[str, int]:
    """Map known keyword → first paragraph index after Keyword Prompts section."""
    try:
        start = next(i for i, p in enumerate(paras) if p.startswith("Keyword Prompts"))
    except StopIteration:
        start = 0

    index: dict[str, int] = {}
    # Prefer exact match; also try ascii apostrophe variants
    variants = {}
    for kw in KNOWN_KEYWORDS:
        variants[kw] = kw
        variants[kw.replace("’", "'")] = kw
        variants[kw.replace("–", "-")] = kw

    for i, p in enumerate(paras):
        if i < start:
            continue
        if p in variants and variants[p] not in index:
            index[variants[p]] = i
            continue
        # Truncated HEAP line may match with/without paren
        for kw in KNOWN_KEYWORDS:
            if p == kw or p.rstrip(")") == kw.rstrip(")"):
                if kw not in index:
                    index[kw] = i
                break
    return index


def extract_instruction_block(paras: list[str], start_idx: int, next_idx: int | None) -> str:
    end = next_idx if next_idx is not None else len(paras)
    parts = paras[start_idx + 1 : end]
    # Drop trailing section noise
    cleaned: list[str] = []
    for p in parts:
        if p in {"Keyword", "Instructions"}:
            continue
        if p.startswith("IT Front Desk Contact") or "DO NOT SHARE" in p.upper():
            cleaned.append(p)
            continue
        cleaned.append(p)
    return "\n".join(cleaned).strip()


def classify_rule(keyword: str, instruction: str) -> RuleRow:
    text = instruction.strip()
    lower = text.lower()
    row = RuleRow(keyword=keyword, source_notes=text[:500] if text else None)

    # Alias
    see = re.match(r"see(?:\s+also)?:\s*(.+)$", text, re.IGNORECASE | re.DOTALL)
    if see and "\n" not in see.group(1).strip()[:80]:
        target = see.group(1).strip().rstrip(".")
        # First line only for simple aliases
        first_line = text.split("\n", 1)[0]
        see_simple = re.match(r"see(?:\s+also)?:\s*(.+)$", first_line, re.IGNORECASE)
        if see_simple and not re.search(r"\bif\b|\bask\b|\bsay\b", first_line, re.I):
            row.action_type = "alias_of"
            row.target = see_simple.group(1).strip().rstrip(".")
            return row

    # Strip DO NOT SHARE blocks from actionable routing (never transfer those)
    public = re.split(
        r"IT Front Desk Contact.*?DO NOT (?:SHARE|TRANSFER).*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )[0].strip()
    lower_pub = public.lower()

    # Multi-step flows
    flow_keywords = {
        "Utility Assistance",
        "Summer Crisis",
        "Winter Crisis",
        "Homeless",
        "Food",
        "Clothing Assistance",
        "Transportation",
        "Prevention, Retention and Contingency (PRC)",
        "Mortgage Assistance",
        "Rental Assistance",
        "Affordable Housing",
        "Metropolitan Housing Authority (MHA)",
        "Grants",
        "Percentage of Income Payment Plan (PIPP)",
    }
    if keyword in flow_keywords or "ask caller what county" in lower_pub:
        row.action_type = "flow" if keyword in flow_keywords or "ask," in lower_pub else "ask_county"
        row.followup_question = _extract_followup(public)
        row.county_branches = _extract_county_branches(public)
        row.flow_definition = _extract_flow(keyword, public)
        row.message = _extract_say(public)
        # Targets commonly referenced
        ext = _first_extension(public)
        phone = _first_phone(public)
        if ext:
            row.target = ext
            if ext in AMBIGUOUS_EXTENSIONS:
                row.ambiguous = True
                row.ambiguity_note = AMBIGUOUS_EXTENSIONS[ext]
        elif phone:
            row.target = phone
        if "ask caller what county" in lower_pub and row.action_type != "flow":
            row.action_type = "ask_county"
        return row

    # Transfer extension
    ext_match = re.search(
        r"transfer(?:\s+them|\s+all calls)?[^.\n]*?\bx(\d{3,4})\b",
        public,
        re.IGNORECASE,
    )
    if not ext_match:
        ext_match = re.search(r"\bx(\d{3,4})\b", public)
    phone_transfer = re.search(
        r"transfer(?:\s+to)?[^.\n]*?(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})",
        public,
        re.IGNORECASE,
    )
    refer = re.search(
        r"(?:refer|direct)(?:\s+caller)?(?:\s+directly)?(?:\s+to)?[^.\n]*?(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\b211\b)",
        public,
        re.IGNORECASE,
    )

    if "email" in lower_pub and re.search(r"[\w.+-]+@mvcap\.com", public, re.I):
        email = re.search(r"[\w.+-]+@mvcap\.com", public, re.I)
        row.action_type = "refer_external"
        row.target = email.group(0) if email else None
        row.message = _extract_say(public) or public.split("\n")[0][:400]
        return row

    if ext_match and ("transfer" in lower_pub or keyword in {
        "Clothing Bank",
        "Weatherization",
        "Furnace",
        "Refrigerator Requests",
        "Credit Counseling",
        "Financial Counseling",
        "Housing Counseling",
        "Mortgage Counseling",
        "Down Payment Assistance",
        "Generational Wealth",
        "Accounts Payable",
        "Monitoring",
        "Finance",
        "Fiscal",
        "Attorney",
        "Lawyer",
        "Legal Matter",
        "Elected Official",
        "Emergency Responders",
        "Law Enforcement",
        "Police",
        "Leadership Team",
        "Darke County",
        "Darke County MHA",
        "Preble County",
        "Preble MHA",
    }):
        row.action_type = "transfer_extension"
        row.target = ext_match.group(1)
        row.message = _extract_say(public)
        if row.target in AMBIGUOUS_EXTENSIONS:
            row.ambiguous = True
            row.ambiguity_note = AMBIGUOUS_EXTENSIONS[row.target]
        # Greene County uses x601 which directory assigns to Darke
        if keyword == "Greene County" and row.target == "601":
            row.ambiguous = True
            row.ambiguity_note = (
                "Script transfers Greene County to x601; directory assigns x601 to "
                "Jennifer Scantland (Darke County Office Assistant)."
            )
        return row

    if phone_transfer and "transfer" in lower_pub:
        row.action_type = "transfer_external"
        row.target = re.sub(r"[^\d]", "", phone_transfer.group(1))
        row.message = _extract_say(public)
        return row

    if refer or re.search(r"direct(?:\s+caller)?\s+to\s+dial", lower_pub):
        phone = _first_phone(public) or ("211" if "211" in public else None)
        row.action_type = "refer_external"
        row.target = phone
        row.message = _extract_say(public) or public.split("\n")[0][:400]
        return row

    # Default: speak message / ask clarifying questions
    row.action_type = "say"
    row.message = _extract_say(public) or public[:600]
    if "ask the caller additional questions" in lower_pub:
        row.followup_question = "Could you tell me a bit more about what you need help with?"
    return row


def _extract_say(text: str) -> str | None:
    m = re.search(r'Say[,:]?\s*[“"](.+?)[”"]', text, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(r'Say[,:]?\s*[‘\'](.+?)[’\']', text, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return None


def _extract_followup(text: str) -> str | None:
    m = re.search(r'Ask[,:]?\s*[“"](.+?)[”"]', text, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    if re.search(r"ask caller what county", text, re.I):
        return "Which county do you live in?"
    return None


def _first_extension(text: str) -> str | None:
    m = re.search(r"\bx(\d{3,4})\b", text, re.I)
    return m.group(1) if m else None


def _first_phone(text: str) -> str | None:
    if re.search(r"\b211\b", text):
        # Prefer explicit 10-digit if also present for primary action
        pass
    m = re.search(r"(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", text)
    if m:
        return re.sub(r"[^\d]", "", m.group(1))
    if re.search(r"\b211\b", text):
        return "211"
    return None


def _extract_county_branches(text: str) -> dict[str, Any] | None:
    branches: dict[str, Any] = {}
    patterns = [
        (
            r"For\s+(Montgomery|Darke|Greene|Preble)\s+County[^:\n]*[:.]?\s*(.+?)(?=\nFor\s+\w+\s+County|\nFor\s+any other|\nFor\s+all other|\nFor\s+counties|\Z)",
            re.I | re.S,
        ),
    ]
    for pat, flags in patterns:
        for m in re.finditer(pat, text, flags):
            county = m.group(1).title()
            body = m.group(2).strip()
            ext = _first_extension(body)
            phone = _first_phone(body)
            say = _extract_say(body)
            action = "say"
            target = None
            if "transfer" in body.lower() and ext:
                action = "transfer_extension"
                target = ext
            elif "transfer" in body.lower() and phone:
                action = "transfer_external"
                target = phone
            elif "refer" in body.lower() or "211" in body:
                action = "refer_external"
                target = phone or "211"
            branches[county] = {
                "action": action,
                "target": target,
                "message": say,
                "raw": body[:500],
            }
    return branches or None


def _extract_flow(keyword: str, text: str) -> dict[str, Any] | None:
    """Capture yes/no branches for known multi-step keywords."""
    flow: dict[str, Any] = {"keyword": keyword, "steps": []}
    if "ask," in text.lower() or re.search(r'Ask[,:]?\s*[“"]', text):
        q = _extract_followup(text)
        if q:
            flow["steps"].append({"type": "question", "prompt": q})

    yes = re.search(
        r"If\s+YES:\s*(.+?)(?=\nIf\s+NO:|\nNOTE:|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    no = re.search(
        r"If\s+NO:\s*(.+?)(?=\nNOTE:|\nIf\s+YES:|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if yes or no:
        branch: dict[str, Any] = {}
        if yes:
            body = yes.group(1).strip()
            branch["yes"] = {
                "message": _extract_say(body),
                "target": _first_extension(body) or _first_phone(body),
                "raw": body[:800],
            }
        if no:
            body = no.group(1).strip()
            branch["no"] = {
                "message": _extract_say(body),
                "target": _first_extension(body) or _first_phone(body),
                "raw": body[:800],
            }
        flow["steps"].append({"type": "yes_no", "branches": branch})

    note = re.search(r"NOTE:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    if note:
        flow["note"] = note.group(1).strip()[:500]

    counties = _extract_county_branches(text)
    if counties:
        flow["county_branches"] = counties

    return flow if flow.get("steps") or flow.get("county_branches") else None


def parse_keyword_rules(paras: list[str]) -> tuple[list[RuleRow], list[str]]:
    flags: list[str] = []
    index = _keyword_index(paras)
    missing = [kw for kw in KNOWN_KEYWORDS if kw not in index]
    for kw in missing:
        flags.append(f"KEYWORD_NOT_FOUND_IN_DOCX: {kw}")

    # Ordered positions for slicing instruction blocks
    ordered = sorted(((idx, kw) for kw, idx in index.items()), key=lambda x: x[0])
    rules: list[RuleRow] = []
    for i, (idx, kw) in enumerate(ordered):
        next_idx = ordered[i + 1][0] if i + 1 < len(ordered) else None
        instruction = extract_instruction_block(paras, idx, next_idx)
        if not instruction:
            flags.append(f"EMPTY_INSTRUCTION: {kw}")
            rules.append(
                RuleRow(
                    keyword=kw,
                    action_type="say",
                    message=None,
                    ambiguous=True,
                    ambiguity_note="No instruction text captured; review docx manually.",
                )
            )
            continue
        rule = classify_rule(kw, instruction)
        # Utility Assistance x821 flag
        if kw == "Utility Assistance" and rule.flow_definition:
            raw = json.dumps(rule.flow_definition)
            if "821" in raw:
                rule.ambiguous = True
                rule.ambiguity_note = AMBIGUOUS_EXTENSIONS["821"]
        rules.append(rule)

    # Wire simple aliases list onto canonical keywords where helpful
    alias_map = {
        "CSBG": "Community Services Block Grant (CSBG)",
        "HEAP": "Utility Assistance",
        "LIHEAP": "Utility Assistance",
        "Disconnection": "Utility Assistance",
        "Food Pantry": "Food",
        "MHA": "Metropolitan Housing Authority (MHA)",
        "PRC": "Prevention, Retention and Contingency (PRC)",
        "PIPP (Percentage of Income Payment Plan)": "Percentage of Income Payment Plan (PIPP)",
    }
    by_kw = {r.keyword: r for r in rules}
    for alias, canonical in alias_map.items():
        if alias in by_kw and by_kw[alias].action_type != "alias_of":
            # Prefer explicit See: classification; otherwise leave
            pass
        if canonical in by_kw and alias in by_kw:
            if alias not in by_kw[canonical].aliases and alias != canonical:
                by_kw[canonical].aliases.append(alias)

    return rules, flags


def parse_staff(lines: list[str]) -> tuple[list[StaffRow], list[str]]:
    flags: list[str] = []
    rows: list[StaffRow] = []
    # Skip headers
    phone_re = re.compile(
        r"(?P<body>.+?)\s+(?P<ext>\d{3})(?:\s*/\s*(?P<ext_phone>\d{3}[-.\s]?\d{3}[-.\s]?\d{4}))?\s*$"
    )
    external_only_re = re.compile(
        r"(?P<body>.+?)\s+(?P<phone>\d{3}[-.\s]?\d{3}[-.\s]?\d{4})\s*$"
    )

    skip_prefixes = (
        "MVCAP Directory",
        "October",
        "Last First",
        "Extension for",
        "Sharing",
    )

    for line in lines:
        if any(line.startswith(p) for p in skip_prefixes):
            continue
        if line in {"Sharing"}:
            continue

        shareable = True
        notes = None
        if "do not share" in line.lower():
            shareable = False
            notes = "Do not share externally"
            # Remove trailing instruction for parsing
            line = re.sub(r"Do not share externally", "", line, flags=re.I).strip()

        extension = None
        external_number = None
        body = line

        m = phone_re.match(line)
        if m and not re.search(r"@|helpdesk", line, re.I):
            body = m.group("body").strip()
            extension = m.group("ext")
            if m.group("ext_phone"):
                external_number = re.sub(r"[^\d]", "", m.group("ext_phone"))
        else:
            m2 = external_only_re.match(line)
            if m2 and not re.search(r"\b\d{3}\b$", m2.group("body")):
                # External DID only (shelter monitors etc.)
                # Avoid eating title words — require phone-looking end
                body = m2.group("body").strip()
                external_number = re.sub(r"[^\d]", "", m2.group("phone"))

        # Email leftover (David Walker)
        email_m = re.search(r"([\w.+-]+@mvcap\.com)", body, re.I)
        if email_m:
            notes = (notes + "; " if notes else "") + email_m.group(1)
            body = body.replace(email_m.group(1), "").strip()
            body = re.sub(r"\s+", " ", body)

        parts = body.split()
        if len(parts) < 3:
            flags.append(f"STAFF_PARSE_AMBIGUOUS: {line}")
            continue

        # last_name may be hyphenated or two tokens (O'Donoghue Ly, Vaughn-Phipps)
        # Heuristic: first token(s) until we can assign legal + preferred + title
        # Format: Last [Last2] FirstLegal FirstPreferred Title...
        # Special case O'Donoghue Ly
        if parts[0].startswith("O'Donoghue") or parts[0].startswith("O’Donoghue"):
            if len(parts) >= 2 and parts[1] == "Ly":
                last_name = f"{parts[0]} Ly"
                rest = parts[2:]
            else:
                last_name = parts[0]
                rest = parts[1:]
        elif "-" in parts[0]:
            last_name = parts[0]
            rest = parts[1:]
        else:
            last_name = parts[0]
            rest = parts[1:]

        if len(rest) < 2:
            flags.append(f"STAFF_PARSE_AMBIGUOUS: {line}")
            continue

        first_legal = rest[0]
        first_preferred = rest[1]
        title = " ".join(rest[2:]).strip() or None

        # If preferred looks like start of title (same as legal often), OK
        # Detect when we accidentally consumed extension into title
        if title and re.search(r"\b\d{3}\b", title):
            flags.append(f"STAFF_TITLE_HAS_DIGITS: {line}")

        row = StaffRow(
            last_name=last_name.replace("’", "'"),
            first_legal=first_legal,
            first_preferred=first_preferred,
            title=title,
            extension=extension,
            external_number=external_number,
            shareable=shareable,
            notes=notes,
        )

        key = (row.last_name, row.first_legal)
        if key in NO_EXTENSION_NAMES and not row.extension and not row.external_number:
            row.notes = (row.notes + "; " if row.notes else "") + "No extension in directory"
        elif (row.last_name, row.first_preferred) in {
            ("Adams", "Candis"),
            ("Martin", "Jade"),
            ("Robinson", "Donna"),
            ("Shinn", "Tacola"),
            ("Thompson", "Skylar"),
            ("Thompson", "Cailyn"),
        } and not row.extension:
            row.notes = (row.notes + "; " if row.notes else "") + "No extension in directory"

        # Flag Katie / Keianna directory values vs script
        if row.last_name.startswith("O'Donoghue") and row.extension == "157":
            row.ambiguous = True
            row.ambiguity_note = (
                "Directory x157; script internal escalation lists x174 (DO NOT TRANSFER)."
            )
        if row.last_name == "Young" and row.first_preferred == "Keianna" and row.extension == "157":
            row.ambiguous = True
            row.ambiguity_note = (
                "Directory x157; script internal escalation lists x135 (DO NOT TRANSFER)."
            )

        rows.append(row)

    return rows, flags


def build_seed() -> SeedPayload:
    if not DOCX_PATH.exists():
        raise FileNotFoundError(f"Missing {DOCX_PATH}")
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"Missing {PDF_PATH}")

    paras = docx_paragraphs(DOCX_PATH)
    lines = pdf_lines(PDF_PATH)

    status = parse_status_updates(paras)
    rules, rule_flags = parse_keyword_rules(paras)
    staff, staff_flags = parse_staff(lines)

    flags = rule_flags + staff_flags
    # Expected spot-checks
    if len(staff) < 80:
        flags.append(f"LOW_STAFF_COUNT: parsed {len(staff)}")
    if len(rules) < 90:
        flags.append(f"LOW_RULE_COUNT: parsed {len(rules)}")

    return SeedPayload(
        staff=staff,
        keyword_rules=rules,
        status_updates=status,
        flags=flags,
    )


def write_review(payload: SeedPayload) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "seed_review.json"
    data = {
        "counts": {
            "staff": len(payload.staff),
            "keyword_rules": len(payload.keyword_rules),
            "status_updates": len(payload.status_updates),
            "flags": len(payload.flags),
        },
        "flags": payload.flags,
        "ambiguous_staff": [asdict(s) for s in payload.staff if s.ambiguous],
        "ambiguous_rules": [asdict(r) for r in payload.keyword_rules if r.ambiguous],
        "staff": [asdict(s) for s in payload.staff],
        "keyword_rules": [asdict(r) for r in payload.keyword_rules],
        "status_updates": [asdict(s) for s in payload.status_updates],
    }
    path.write_text(json.dumps(data, indent=2))
    return path


def apply_to_supabase(payload: SeedPayload) -> None:
    import os

    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv(ROOT / ".env")
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required for --apply")

    client = create_client(url, key)

    staff_rows = [
        {
            "last_name": s.last_name,
            "first_legal": s.first_legal,
            "first_preferred": s.first_preferred,
            "title": s.title,
            "extension": s.extension,
            "external_number": s.external_number,
            "shareable": s.shareable,
            "notes": s.notes,
        }
        for s in payload.staff
    ]
    # Replace-all strategy for idempotent seed (dev)
    client.table("staff").delete().neq("last_name", "").execute()
    if staff_rows:
        client.table("staff").insert(staff_rows).execute()

    rule_rows = [
        {
            "keyword": r.keyword,
            "aliases": r.aliases,
            "action_type": r.action_type,
            "message": r.message,
            "target": r.target,
            "county_branches": r.county_branches,
            "followup_question": r.followup_question,
            "flow_definition": r.flow_definition,
            "active": r.active,
            "source_notes": r.source_notes,
            "ambiguous": r.ambiguous,
            "ambiguity_note": r.ambiguity_note,
        }
        for r in payload.keyword_rules
    ]
    client.table("keyword_rules").delete().neq("keyword", "").execute()
    if rule_rows:
        client.table("keyword_rules").insert(rule_rows).execute()

    status_rows = [
        {
            "effective_date": s.effective_date,
            "message": s.message,
            "active": s.active,
        }
        for s in payload.status_updates
    ]
    client.table("status_updates").delete().neq("message", "").execute()
    if status_rows:
        client.table("status_updates").insert(status_rows).execute()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Parse only; write review JSON")
    parser.add_argument("--apply", action="store_true", help="Upsert into Supabase")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        args.dry_run = True

    payload = build_seed()
    review_path = write_review(payload)

    print(f"Staff:           {len(payload.staff)}")
    print(f"Keyword rules:   {len(payload.keyword_rules)}")
    print(f"Status updates:  {len(payload.status_updates)}")
    print(f"Flags:           {len(payload.flags)}")
    print(f"Review JSON:     {review_path}")
    for f in payload.flags[:30]:
        print(f"  ! {f}")
    if len(payload.flags) > 30:
        print(f"  … {len(payload.flags) - 30} more")

    if args.apply:
        apply_to_supabase(payload)
        print("Applied to Supabase.")
    else:
        print("Dry-run only (pass --apply to write to Supabase).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
