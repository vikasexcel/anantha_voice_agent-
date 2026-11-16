"""Agent function tools. Routing data comes from directory — not the prompt."""

from __future__ import annotations

import asyncio
import logging
import time

from livekit.agents import RunContext, function_tool

from agent.directory import find_staff as directory_find_staff

# Same tree as main so Console worker logs show tool results.
logger = logging.getLogger("mvcap-agent")


@function_tool
async def find_staff(context: RunContext, query: str) -> dict:
    """Look up MVCAP staff by person name, department, or role/title.

    ALWAYS call this before answering about a person, department, job title,
    or role (sales manager, billing, CFO, HR, first name, last name). Do not
    say "I don't have that" until this tool returns empty matches.

    Args:
        query: Name, department, or role phrase from the caller (as heard).

    Returns:
        Structured matches with name, title, and whether a transfer is available.
        If clarify is set or multiple matches: ask the caller which person.
        If matches is empty, follow the note/suggestions — do not invent names.
        Never say extension numbers out loud.
    """
    filler_spoken = asyncio.Event()

    async def _maybe_filler() -> None:
        try:
            await asyncio.sleep(1.0)
            if filler_spoken.is_set():
                return
            await context.session.say(
                "One moment.",
                allow_interruptions=True,
                add_to_chat_ctx=False,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            return

    task = asyncio.create_task(_maybe_filler())
    t0 = time.perf_counter()
    try:
        result = await asyncio.to_thread(directory_find_staff, query)
        result = dict(result)
        result["lookup_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        # Log query + counts only (no secrets). Helps Console debugging.
        names = [m.get("name") for m in result.get("matches") or []]
        logger.info(
            "find_staff query=%r matches=%s names=%s suggestions=%s",
            query,
            result.get("match_count"),
            names,
            len(result.get("suggestions") or []),
        )
        return result
    finally:
        filler_spoken.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
