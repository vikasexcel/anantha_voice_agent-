"""Phase 1 LiveKit agent: answer inbound SIP and speak the MVCAP greeting.

Run:
  python -m agent.main dev
  python -m agent.main start
"""

from __future__ import annotations

import logging

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
from agent.prompts import build_system_prompt
from agent.providers import build_llm, build_stt, build_tts

logger = logging.getLogger("mvcap-agent")


class MVCAPReceptionist(Agent):
    """Voice receptionist. Tools and routing land in Phase 3+."""

    def __init__(self, instructions: str) -> None:
        super().__init__(instructions=instructions)


async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings(require_livekit=True, require_supabase=False)
    logger.info("Job started room=%s", ctx.room.name)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    instructions = build_system_prompt(
        agent_display_name=settings.agent_display_name,
        website=settings.mvcap_website,
    )
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=build_stt(settings),
        llm=build_llm(settings),
        tts=build_tts(settings),
    )

    await session.start(agent=MVCAPReceptionist(instructions), room=ctx.room)

    # Speak the scripted greeting immediately after answer.
    await session.say(settings.greeting, allow_interruptions=True)


def main() -> None:
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            # SIP inbound rooms are dispatched to this agent name via LiveKit dispatch rule.
            agent_name="mvcap-receptionist",
        )
    )


if __name__ == "__main__":
    main()
