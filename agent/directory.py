"""In-memory staff directory loaded from client docs (seed). No full list in prompts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from rapidfuzz import fuzz, process


@dataclass(frozen=True)
class StaffRecord:
    last_name: str
    first_legal: str
    first_preferred: str | None
    title: str | None
    extension: str | None
    external_number: str | None
    shareable: bool
    notes: str | None = None

    @property
    def display_name(self) -> str:
        first = self.first_preferred or self.first_legal
        return f"{first} {self.last_name}".strip()

    @property
    def search_blob(self) -> str:
        parts = [
            self.last_name,
            self.first_legal,
            self.first_preferred or "",
            self.title or "",
        ]
        return " ".join(p for p in parts if p).lower()


# Common caller phrasings → title/role keywords (not inventing people).
ROLE_ALIASES: dict[str, list[str]] = {
    "sales": ["sales"],
    "sales team": ["sales"],
    "sales head": ["sales"],
    "sales manager": ["sales"],
    "business development": ["business development", "sales", "outreach", "fundraising", "marketing"],
    "outreach": ["outreach"],
    "fundraising": ["fundraising", "grants"],
    "marketing": ["marketing"],
    "billing": ["payable", "accounts payable", "accountant", "fiscal", "payroll", "controller"],
    "bill": ["payable", "accounts payable", "accountant", "payroll"],
    "invoice": ["payable", "accounts payable", "payroll"],
    "accounts payable": ["payable", "payroll"],
    "finance": ["cfo", "controller", "fiscal", "accountant", "financial"],
    "cfo": ["cfo"],
    "accounting": ["accountant", "accounting", "fiscal", "controller", "payable"],
    "human resources": ["human resources"],
    "ceo": ["president", "ceo"],
    "president": ["president", "ceo"],
    "coo": ["coo"],
    "utility": ["utility assistance"],
    "utility assistance": ["utility assistance"],
    "weatherization": ["weatherization", "whs"],
    "housing counseling": ["housing counseling", "financial & housing", "financial and housing"],
    "domestic violence": ["domestic violence"],
    "grants": ["grants", "compliance"],
    "hr": ["human resources"],
}

# Roles callers ask for that do NOT exist in the MVCAP directory.
COMMERCIAL_ROLE_PHRASES = (
    "sales",
    "salesperson",
    "account executive",
    "business development",
    "outreach",
    "fundraising",
    "marketing",
)


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s\-']", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=1)
def load_staff() -> tuple[StaffRecord, ...]:
    """Load shareable staff from the docx/PDF seed parser (local source of truth)."""
    from scripts.seed_from_docs import build_seed

    payload = build_seed()
    rows: list[StaffRecord] = []
    for s in payload.staff:
        rows.append(
            StaffRecord(
                last_name=s.last_name,
                first_legal=s.first_legal,
                first_preferred=s.first_preferred,
                title=s.title,
                extension=s.extension,
                external_number=s.external_number,
                shareable=s.shareable,
                notes=s.notes,
            )
        )
    return tuple(rows)


def staff_name_hint(limit: int = 80) -> str:
    """Compact STT vocabulary hint — names only, not full directory dump."""
    names: list[str] = []
    for s in load_staff():
        if not s.shareable:
            continue
        names.append(s.display_name)
        if len(names) >= limit:
            break
    departments = (
        "Utility Assistance, Weatherization, Housing Counseling, Human Resources, "
        "Accounts Payable, Emergency Services, PRC, Domestic Violence, "
        "Darke County, Preble County, Greene County, Montgomery County"
    )
    return (
        "Miami Valley Community Action Partnership staff and departments. "
        f"Departments: {departments}. "
        f"Names: {', '.join(names)}."
    )


def staff_keyterms(limit: int = 80) -> list[str]:
    """Deepgram keyterm list for Inference STT (names + departments)."""
    terms: list[str] = [
        "Miami Valley Community Action Partnership",
        "Utility Assistance",
        "Weatherization",
        "Housing Counseling",
        "Human Resources",
        "Accounts Payable",
        "Emergency Services",
        "Domestic Violence",
        "PRC",
    ]
    for s in load_staff():
        if not s.shareable:
            continue
        terms.append(s.display_name)
        if len(terms) >= limit:
            break
    return terms


def _role_keyword_hits(query: str) -> list[str]:
    """Return title keywords from known role aliases only (no bare 'manager'/'head')."""
    q = _normalize(query)
    hits: list[str] = []
    # Longer aliases first so "sales team" wins over "sales"
    for alias in sorted(ROLE_ALIASES.keys(), key=len, reverse=True):
        # Short aliases (coo/ceo/hr) must be whole words — avoid "coo" in "Cooper"
        if len(alias) <= 3:
            if not re.search(rf"\b{re.escape(alias)}\b", q):
                continue
        elif alias not in q:
            continue
        hits.extend(ROLE_ALIASES[alias])
    # de-dupe, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def _is_commercial_role_query(query: str) -> bool:
    q = _normalize(query)
    return any(k in q for k in COMMERCIAL_ROLE_PHRASES)


def _commercial_role_response(query: str, staff: list[StaffRecord]) -> dict[str, Any]:
    """Honest empty result for sales/BD/marketing — no invented Development Director.

    Directory has zero sales/BD/outreach/fundraising/marketing titles. Closest
    real contacts for partnership/funding callers are Grants and leadership.
    """
    suggestions = []
    for s in staff:
        title = (s.title or "").lower()
        if "grants and compliance" in title or title.strip() == "president & ceo":
            suggestions.append(
                {
                    "name": s.display_name,
                    "title": s.title,
                    "can_transfer": bool(s.extension or s.external_number),
                    "has_extension": bool(s.extension),
                    "extension": s.extension,
                    "reason": "possible grants/partnerships contact — confirm need first",
                }
            )
    return {
        "query": query,
        "matches": [],
        "match_count": 0,
        "suggestions": suggestions,
        "note": (
            "MVCAP has no sales, business development, outreach, fundraising, or "
            "marketing role in the staff directory. Do not invent a Development "
            "Director. Tell the caller we don't have a sales team, ask what they "
            "need, and only offer Grants/Compliance (Kevin Reeves) or the President "
            "(Erin Jeffries) if they mean funding or organizational partnerships."
        ),
    }


def _name_score(query: str, candidate: str) -> float:
    """Best of ratio / partial / WRatio for typo and phonetic tolerance."""
    if not query or not candidate:
        return 0.0
    return float(
        max(
            fuzz.ratio(query, candidate),
            fuzz.partial_ratio(query, candidate) if len(query) >= 4 else 0,
            fuzz.WRatio(query, candidate),
        )
    )


def _is_substring_trap(query: str, candidate: str) -> bool:
    """Block Yannick→Nick style traps without blocking real typos."""
    nq = query.replace(" ", "")
    ch = candidate.replace(" ", "")
    if nq == ch:
        return False
    if len(nq) < 4 or len(ch) < 3:
        return False
    # One is a strict substring of the other and lengths differ a lot
    if (nq in ch or ch in nq) and abs(len(nq) - len(ch)) >= 2:
        # Allow 1-char typos that happen to substring (rare); require edit distance feel
        if fuzz.ratio(nq, ch) < 80:
            return True
    return False


def _match_single_token(token: str, staff: list[StaffRecord], *, min_score: int) -> list[tuple[float, StaffRecord, str]]:
    """First-name-only or last-name-only: return ALL people that match (fuzzy)."""
    hits: list[tuple[float, StaffRecord, str]] = []
    for s in staff:
        firsts = {
            (s.first_preferred or "").lower(),
            s.first_legal.lower(),
        }
        last = s.last_name.lower()
        best = 0.0
        via = "name"
        for f in firsts:
            if not f:
                continue
            if _is_substring_trap(token, f):
                continue
            # Prefer plain ratio for single tokens (WRatio is too loose: Yannick→Mick)
            sc = float(max(fuzz.ratio(token, f), fuzz.QRatio(token, f)))
            if sc > best:
                best = sc
                via = "first"
        if not _is_substring_trap(token, last):
            sc = float(max(fuzz.ratio(token, last), fuzz.QRatio(token, last)))
            if sc > best:
                best = sc
                via = "last"
        # Exact-ish first/last; allow small typos but not unrelated names
        if len(token) <= 3:
            threshold = 95
        elif len(token) == 4:
            threshold = 85
        else:
            threshold = 82
        # Also reject large length mismatches (Yannick vs Mick)
        cand = (
            (s.first_preferred or s.first_legal).lower()
            if via == "first"
            else last
        )
        if abs(len(token) - len(cand)) > 2 and best < 90:
            continue
        if best >= threshold:
            hits.append((best, s, via))
    # Dedupe by display name, keep best score
    by_name: dict[str, tuple[float, StaffRecord, str]] = {}
    for score, s, via in hits:
        key = s.display_name
        prev = by_name.get(key)
        if not prev or score > prev[0]:
            by_name[key] = (score, s, via)
    return sorted(by_name.values(), key=lambda x: x[0], reverse=True)


def find_staff(
    query: str,
    *,
    limit: int = 5,
    min_score: int = 62,
) -> dict[str, Any]:
    """Fuzzy search by person name and/or role/title keywords.

    Returns structured matches. Empty matches means the agent should say it does
    not know / ask a clarifying question — never invent people.
    First- or last-name-only queries return all matches so the agent can ask
    "Do you mean X or Y?".
    """
    q = (query or "").strip()
    if not q:
        return {"query": query, "matches": [], "note": "Empty query.", "match_count": 0}

    staff = [s for s in load_staff() if s.shareable]
    qn = _normalize(q)
    role_keys = _role_keyword_hits(qn)

    # Commercial roles do not exist in this directory — avoid fuzzy false hits.
    if _is_commercial_role_query(qn):
        title_needles = ("sales", "business development", "outreach", "fundraising", "marketing")
        title_hits = [
            s
            for s in staff
            if s.title and any(n in s.title.lower() for n in title_needles)
        ]
        if not title_hits:
            return _commercial_role_response(query, staff)

    scored: dict[str, tuple[float, StaffRecord, str]] = {}

    # Prefer matching against full name phrases, not the whole question
    name_query = re.sub(
        r"\b(who|is|the|your|handles?|team|head|manager|director|please|me|to|a|an)\b",
        " ",
        qn,
    )
    name_query = _normalize(name_query) or qn
    query_tokens = name_query.split()
    single_token_query = len(query_tokens) == 1

    # --- First-name-only / last-name-only (return ALL matches) ---
    if single_token_query and not role_keys:
        token = query_tokens[0]
        single_hits = _match_single_token(token, staff, min_score=min_score)
        for score, s, via in single_hits[: max(limit, 8)]:
            scored[s.display_name] = (float(score), s, via)
    else:
        # Full / multi-token name fuzzy match — index may map one key → many people
        name_index: dict[str, list[StaffRecord]] = {}
        for s in staff:
            keys = {
                s.display_name.lower(),
                f"{s.first_legal} {s.last_name}".lower(),
                f"{(s.first_preferred or s.first_legal).lower()} {s.last_name.lower()}",
                s.last_name.lower(),
                (s.first_preferred or "").lower(),
                s.first_legal.lower(),
            }
            for k in keys:
                if k:
                    name_index.setdefault(k, []).append(s)

        name_hits = process.extract(
            name_query,
            list(name_index.keys()),
            scorer=fuzz.WRatio,
            limit=16,
        )
        for choice, score, _ in name_hits:
            if score < min_score:
                continue
            if len(choice) <= 3 and score < 92:
                continue
            if _is_substring_trap(name_query, choice):
                continue
            for s in name_index[choice]:
                # Prefer full-name choices over bare first/last noise
                adj = float(score)
                if " " in choice:
                    adj += 5
                key = s.display_name
                prev = scored.get(key)
                if not prev or adj > prev[0]:
                    scored[key] = (adj, s, "name")

        # Token path for misspelled first+last (e.g. "Eddy Coper")
        stop = {
            "who", "is", "the", "your", "handles", "handle", "team", "head",
            "manager", "director", "sales", "billing", "please",
        }
        tokens = [t for t in query_tokens if len(t) > 2 and t not in stop]
        if len(tokens) >= 2:
            for s in staff:
                firsts = [
                    (s.first_preferred or "").lower(),
                    s.first_legal.lower(),
                ]
                last = s.last_name.lower()
                first_scores = [
                    _name_score(t, f)
                    for t in tokens
                    for f in firsts
                    if f and not _is_substring_trap(t, f)
                ]
                last_scores = [
                    _name_score(t, last)
                    for t in tokens
                    if not _is_substring_trap(t, last)
                ]
                best_first = max(first_scores) if first_scores else 0.0
                best_last = max(last_scores) if last_scores else 0.0
                if best_first >= 78 and best_last >= 78:
                    score = (best_first + best_last) / 2.0 + 5
                    key = s.display_name
                    prev = scored.get(key)
                    if not prev or score > prev[0]:
                        scored[key] = (float(score), s, "token")

    # Title / role keyword match (alias keywords only)
    wants_manager = "manager" in qn
    wants_director = "director" in qn
    if role_keys:
        for s in staff:
            title = (s.title or "").lower()
            if not title:
                continue
            best = 0.0
            for kw in role_keys:
                if kw in title:
                    best = max(best, 88.0 + min(len(kw), 10))
                else:
                    pr = float(fuzz.partial_ratio(kw, title))
                    if pr >= 90:
                        best = max(best, pr)
            if best < 88:
                continue
            if wants_manager and "manager" in title:
                best += 15
            elif wants_manager and "manager" not in title:
                best -= 8
            if wants_director and "director" in title:
                best += 15
            elif wants_director and "director" not in title:
                best -= 8
            if "ceo" in qn and "ceo" in title:
                best += 20
            elif "ceo" in qn and "vice president" in title:
                best -= 10
            if "president" in qn and "president & ceo" in title:
                best += 20
            elif "president" in qn and "vice president" in title:
                best -= 10
            key = s.display_name
            prev = scored.get(key)
            combined = best
            if prev and prev[2] in ("name", "first", "last", "token"):
                combined = max(prev[0], best + 5)
            if not prev or combined > prev[0]:
                scored[key] = (combined, s, "role")

    ranked = sorted(scored.values(), key=lambda x: x[0], reverse=True)

    # Drop weak incidental fuzz when we have a strong primary hit
    if ranked and ranked[0][0] >= 90:
        ranked = [x for x in ranked if x[0] >= 85 or x[2] == "role"]
    strong_role = [x for x in ranked if x[2] == "role" and x[0] >= 88]
    if strong_role and not single_token_query:
        ranked = [x for x in ranked if x[2] == "role" or x[0] >= 85]

    # For ambiguous first/last-only, keep all name matches up to a higher cap
    cap = 8 if single_token_query else limit
    ranked = ranked[:cap]

    matches = []
    for score, s, how in ranked:
        matches.append(
            {
                "name": s.display_name,
                "legal_name": f"{s.first_legal} {s.last_name}",
                "title": s.title,
                "can_transfer": bool(s.extension or s.external_number),
                "has_extension": bool(s.extension),
                "extension": s.extension,  # backend transfer only — never speak aloud
                "external_number": s.external_number,
                "match_score": round(score, 1),
                "match_via": how,
            }
        )

    clarify = None
    note = None
    # Only ask "Do you mean X or Y?" for first/last-name lookups, not role searches
    name_vias = {"first", "last", "name", "token"}
    if (
        len(matches) > 1
        and single_token_query
        and not role_keys
        and all(m.get("match_via") in name_vias for m in matches)
    ):
        options = " or ".join(m["name"] for m in matches[:4])
        clarify = f"Multiple people match. Ask: Do you mean {options}?"
        note = clarify
    elif not matches:
        note = "No matching staff found. Ask the caller to clarify the name or department."

    return {
        "query": query,
        "matches": matches,
        "note": note,
        "clarify": clarify,
        "match_count": len(matches),
    }
