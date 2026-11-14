# MVCAP AI Voice Phone Tree: Project Brief for Cursor

See `AGENTS.md` (canonical agent instructions) and `docs/` for client source-of-truth files.

## Client docs

- `docs/MiamiValleyActionPartnership_AnsweringScript-LiveKit.docx`
- `docs/MVCAP_ITFrontDesk_Directory_for_AnswerNet.pdf`
- `docs/OPEN_QUESTIONS.md`

## Architecture

```
Caller -> Telnyx number -> SIP trunk -> LiveKit SIP inbound trunk + dispatch rule
      -> LiveKit Agent worker (Python)
            STT -> LLM (with tools) -> TTS
            tools -> Supabase (staff, rules, status_updates, call_logs)
      -> transfer: LiveKit TransferSIPParticipant (SIP REFER) -> Telnyx -> MVCAP PBX / external number
```

## Core principle

Routing is deterministic and data-driven. The LLM must not memorize extensions or the script.

## Phases

1. Scaffold — greeting agent
2. Data — Supabase migrations + seed
3. Agent logic — tools + multi-step flows
4. Transfers — extensions, external, hours, failure fallback
5. Testing — unit + scripted + text simulator
6. Observability — call logs, retries, latency
7. Docs — README, edit rules, deploy guide

Full rules and constraints: `AGENTS.md`.
