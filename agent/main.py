"""MVCAP LiveKit voice receptionist.

Run:
  python -m agent.main dev
  python -m agent.main start
"""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)


def _sanitize_openai_api_key() -> None:
    """Strip accidental labels/spaces from OPENAI_API_KEY (never log the value)."""
    import os
    import re

    raw = os.getenv("OPENAI_API_KEY", "")
    if not raw:
        return
    cleaned = raw.strip().strip('"').strip("'")
    cleaned = re.sub(r"(?i)^open\s*ai\s*[:\-]?\s*", "", cleaned).strip()
    match = re.search(r"(sk-[A-Za-z0-9_\-]+)", cleaned)
    if match:
        cleaned = match.group(1)
    if cleaned != raw:
        os.environ["OPENAI_API_KEY"] = cleaned


_sanitize_openai_api_key()

from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.plugins import silero

from agent.config import get_settings
from agent.directory import load_staff, staff_keyterms
from agent.prompts import build_system_prompt
from agent.providers import (
    build_llm,
    build_stt,
    build_tts,
    build_turn_detector,
    stt_tts_descriptor,
)
from agent.tools import find_staff

logger = logging.getLogger("mvcap-agent")


class MVCAPReceptionist(Agent):
    def __init__(self, instructions: str) -> None:
        super().__init__(instructions=instructions, tools=[find_staff])


async def entrypoint(ctx: JobContext) -> None:
    get_settings.cache_clear()
    settings = get_settings(require_livekit=True, require_supabase=False)
    logger.info(
        "Job started room=%s staff=%s %s",
        ctx.room.name,
        len(load_staff()),
        stt_tts_descriptor(settings),
    )

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    instructions = build_system_prompt(
        agent_display_name=settings.agent_display_name,
        website=settings.mvcap_website,
    )

    session = AgentSession(
        vad=silero.VAD.load(),
        turn_detection=build_turn_detector(settings),
        stt=build_stt(settings, keyterms=staff_keyterms()),
        llm=build_llm(settings),
        tts=build_tts(settings),
        min_endpointing_delay=settings.min_endpointing_delay,
        max_endpointing_delay=settings.max_endpointing_delay,
        min_interruption_duration=settings.min_interruption_duration,
        allow_interruptions=settings.allow_interruptions,
        preemptive_generation=settings.preemptive_generation,
    )

    await session.start(agent=MVCAPReceptionist(instructions), room=ctx.room)
    await session.say(
        settings.greeting,
        allow_interruptions=settings.allow_interruptions,
    )


def _preflight_livekit() -> None:
    import os

    required = ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
    missing = [k for k in required if not os.getenv(k, "").strip()]
    if missing:
        raise SystemExit(
            "Missing LiveKit env vars (values not shown): "
            + ", ".join(missing)
            + ". Fill them in .env from LiveKit Cloud → Settings → Keys."
        )
    url = os.environ["LIVEKIT_URL"].strip()
    key = os.environ["LIVEKIT_API_KEY"].strip()
    if not url.startswith(("wss://", "ws://")):
        raise SystemExit("LIVEKIT_URL must start with wss:// (or ws://).")
    if not key.startswith("API"):
        raise SystemExit(
            "LIVEKIT_API_KEY does not look like a LiveKit key (expected to start with API)."
        )


def main() -> None:
    _preflight_livekit()
    get_settings.cache_clear()
    settings = get_settings(require_livekit=True, require_supabase=False)
    count = len(load_staff())
    logger.info(
        "Worker boot staff=%s %s turn=%s",
        count,
        stt_tts_descriptor(settings),
        settings.turn_detector,
    )
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="mvcap-receptionist",
            num_idle_processes=1,
            initialize_process_timeout=60.0,
        )
    )


if __name__ == "__main__":
    main()
