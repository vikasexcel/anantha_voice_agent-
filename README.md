# MVCAP AI Voice Phone Tree

AI voice receptionist for **Miami Valley Community Action Partnership (MVCAP)**. Answers inbound calls via Telnyx → LiveKit SIP, looks up staff and keyword rules in Supabase, and transfers or speaks scripted responses.

**Routing is data-driven.** Extensions and keyword rules live in Supabase. The LLM does not memorize the script.

## Status

| Phase | Status |
|-------|--------|
| 1 Scaffold (greeting agent) | Done |
| 2 Data (Supabase + seed) | Done |
| 3 Agent logic (tools / flows) | Next |
| 4 Transfers + hours | Pending |
| 5 Testing | Pending |
| 6 Observability | Pending |
| 7 Docs polish | Pending |

Source of truth (read before changing routing):

- `docs/MiamiValleyActionPartnership_AnsweringScript-LiveKit.docx`
- `docs/MVCAP_ITFrontDesk_Directory_for_AnswerNet.pdf`
- `docs/OPEN_QUESTIONS.md`

## Repo layout

```
agent/                 LiveKit Agents worker (Python)
config/                Non-secret defaults (hours, transfer mode notes)
docs/                  Client script + directory + open questions
scripts/seed_from_docs.py
supabase/migrations/   Schema
tests/                 Seed + (later) routing tests
```

## Quick start (Phase 1)

Requires **Python 3.11** (3.14 is too new for `onnxruntime` / Silero VAD).

```bash
/usr/local/bin/python3.11 -m venv .venv   # or any 3.11+
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill LIVEKIT_*, DEEPGRAM_API_KEY, OPENAI_API_KEY, CARTESIA_API_KEY (or chosen providers)

python -m agent.main dev
```

Inbound SIP calls dispatched to agent name `mvcap-receptionist` should hear:

> Thank you for calling Miami Valley Community Action Partnership. This is [AGENT_DISPLAY_NAME]. How may I help you?

## Telnyx + LiveKit trunk setup

High-level (client already provisioned; keep secrets in `.env` only):

1. **Telnyx** — Buy/assign the MVCAP number. Create a SIP connection pointing to LiveKit’s SIP endpoint (from LiveKit Cloud → SIP).
2. **LiveKit SIP inbound trunk** — Accept traffic from Telnyx. Map the DID to a dispatch rule.
3. **Dispatch rule** — Room prefix + agent `mvcap-receptionist` (matches `WorkerOptions.agent_name` in `agent/main.py`).
4. **Outbound / transfer trunk** — Needed for Phase 4 (`TransferSIPParticipant`). Format depends on `TRANSFER_MODE` (see open questions).
5. **Worker** — Run `python -m agent.main start` in production with LiveKit credentials.

Exact portal clicks vary; use LiveKit Cloud SIP docs and Telnyx SIP trunk docs for current UI.

## Phase 2: Supabase + seed

1. Create a Supabase project. Apply migration:

```bash
# via Supabase CLI, or paste SQL in the SQL editor:
# supabase/migrations/001_initial_schema.sql
```

2. Put `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in `.env`.

3. Parse docs and (optionally) upsert:

```bash
python scripts/seed_from_docs.py --dry-run
# review scripts/output/seed_review.json and flagged ambiguities
python scripts/seed_from_docs.py --apply
```

4. Run tests:

```bash
pytest tests/test_seed.py -q
```

## Editing rules without redeploy

Update rows in `keyword_rules` and `staff` in Supabase. The agent looks them up at call time. Do not hardcode extensions in Python.

## Blocked on client

See `docs/OPEN_QUESTIONS.md` (extension mismatches, x821, Greene→x601, transfer URI format, after-hours message, transfer failure behavior).
