# Open questions (do not silently resolve)

Known inconsistencies between the answering script and the staff directory, plus undefined behaviors. Implement as **config / DB values that are easy to change**, not hardcoded guesses.

| # | Issue | Script / note | Directory / reality | Current handling |
|---|--------|---------------|---------------------|------------------|
| 1 | Katie O’Donoghue / Keianna Young extensions | Script escalations: Katie x174, Keianna x135 (also marked DO NOT SHARE / DO NOT TRANSFER) | Both listed as **x157** | Seed uses **directory** for `staff.extension`. Escalation contacts remain non-transferable / never spoken. Flagged in seed review. |
| 2 | Utility Assistance x821 | Disconnection → **x821**; otherwise → x102 | **x821 not in directory**; x102 is (Ashley King / Sara Seeley) | Seed stores x821 on the Utility Assistance flow branch as written. Marked `ambiguous` until client confirms who/where x821 rings. |
| 3 | Greene County → x601 | Script: Greene County services transfer **x601** | Directory: x601 = **Jennifer Scantland**, Darke County Office Assistant | Seed keeps script target x601. Flagged — confirm whether Greene should use a different extension. |
| 4 | Staff with no extension | — | Candis Adams, Jade Martin, Donna Robinson, Tacola Shinn, Skylar Thompson, Cailyn Thompson | `extension` null. Agent uses `NO_EXTENSION_FALLBACK` / `NO_EXTENSION_MESSAGE` (main line or voicemail offer). |
| 5 | Transfer target format | Unknown | SIP URI vs main+ext vs DID | `TRANSFER_MODE` in `.env`: `sip_uri` \| `main_plus_ext` \| `did` plus `TRANSFER_SIP_DOMAIN` / `TRANSFER_MAIN_NUMBER`. |
| 6 | After-hours / lunch / holiday | Hours Mon–Fri 8:00–4:30, closed 12–1; holiday behavior undefined | — | Configurable hours check + `AFTER_HOURS_MESSAGE` placeholder. Holiday calendar not yet provided. |
| 7 | Transfer failure / no answer | Undefined | — | `TRANSFER_FAILURE_MESSAGE` placeholder until client defines retry / voicemail / 211. |

## Additional ambiguities found while seeding

Updated by `scripts/seed_from_docs.py` when it flags rows. Review `scripts/output/seed_review.json` after each dry-run.

- **Home Energy Assistance Program (HEAP** — keyword line appears truncated (missing closing `)`) in the docx extract; treated as alias of Utility Assistance / HEAP.
- **David Walker** — IT contractor; directory says do not share externally → `shareable=false`.
- **Internal escalation lines** in Appeals / HR / Jobs / Employment — never expose as transfer targets even if extensions differ from directory.

## Client decisions needed before production

1. Confirm Katie / Keianna real transfer extensions (or confirm escalations stay non-transfer only).
2. Confirm what x821 is (queue, hunt group, person).
3. Confirm Greene County transfer target.
4. Confirm `TRANSFER_MODE` and SIP URI pattern for the PBX.
5. Provide holiday calendar and preferred after-hours / lunch messaging.
6. Define transfer no-answer / failure path.
