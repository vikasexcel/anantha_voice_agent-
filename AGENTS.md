# MVCAP AI Voice Phone Tree — Agent Instructions

This file is the project brief for Cursor agents. Client source-of-truth docs are in `/docs`. Read them before writing routing code. Do not invent routing rules.

## Goal

Build an AI voice receptionist for Miami Valley Community Action Partnership (MVCAP). It answers inbound calls and:

1. If the caller asks for a staff member by name, transfers to that person’s extension.
2. For everything else, listens for keywords and either speaks a fixed message, asks a follow-up (usually “which county?”), refers to a website/external number, or transfers to an extension or external number.

This replaces the human answering service (IT Front Desk / AnswerNet).

## Stack

- LiveKit (SIP + Agents, Python `livekit-agents`)
- Telnyx (number + SIP trunk)
- Supabase (staff, keyword_rules, status_updates, call_logs)
- STT/LLM/TTS via LiveKit plugins (configurable: Deepgram / OpenAI|Anthropic / Cartesia|ElevenLabs)
- Secrets only in `.env`

## Core design principle

**Routing must be deterministic and data-driven. The LLM must not memorize extensions or the script.**

- Extensions, keyword rules, and messages live in Supabase and are looked up through tools.
- The system prompt holds only tone, greeting, global rules, and tool usage.
- The client must be able to edit a rule or extension in Supabase without redeploying code.

## Client docs (source of truth)

- `docs/MiamiValleyActionPartnership_AnsweringScript-LiveKit.docx`
- `docs/MVCAP_ITFrontDesk_Directory_for_AnswerNet.pdf`
- `docs/OPEN_QUESTIONS.md` — known inconsistencies; do **not** silently resolve

## Behavior rules (must follow)

- Greeting: “Thank you for calling Miami Valley Community Action Partnership. This is [name]. How may I help you?”
- Never say extensions out loud.
- Unavailable staff → leave detailed voice message.
- Push website www.miamivalleycap.org where the script says so.
- Services not provided → website + 211.
- Internal-only escalation (“DO NOT SHARE EXTERNALLY / DO NOT TRANSFER”) → never speak or transfer.
- Attorney/legal, elected officials, police/emergency, leadership, finance → x157.
- Press → news@mvcap.com; Appeals → appeals@mvcap.com; HR → HR@mvcap.com unless named.
- Domestic violence → 937-456-6891 fast path.
- Multi-step flows exactly as written (Utility Assistance, Summer/Winter Crisis, Homeless, Food, Clothing, Transportation, PRC/Rental/Mortgage).
- Fallback: clarify → website → 211.

## Build phases (in order; commit after each)

1. Scaffold — greeting agent
2. Data — migrations + seed from docs
3. Agent logic — tools + flows
4. Transfers — extensions, external, hours, failure fallback
5. Testing — unit + scripted + text simulator
6. Observability — call_logs, retries, latency
7. Docs — README, edit rules, deploy, OPEN_QUESTIONS

## Constraints

- No hardcoded extensions/phone numbers in code; Supabase or config only.
- No secrets in the repo.
- If ambiguous → `docs/OPEN_QUESTIONS.md`, do not guess.
