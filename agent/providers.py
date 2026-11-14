"""Build STT / LLM / TTS plugins from env-configurable providers."""

from __future__ import annotations

from typing import Any

from agent.config import Settings


def build_stt(settings: Settings) -> Any:
    provider = settings.stt_provider
    if provider == "deepgram":
        from livekit.plugins import deepgram

        return deepgram.STT(model=settings.stt_model)
    raise ValueError(f"Unsupported STT_PROVIDER: {provider}")


def build_llm(settings: Settings) -> Any:
    provider = settings.llm_provider
    if provider == "openai":
        from livekit.plugins import openai

        return openai.LLM(model=settings.llm_model)
    if provider == "anthropic":
        from livekit.plugins import anthropic

        return anthropic.LLM(model=settings.llm_model or "claude-sonnet-4-5")
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def build_tts(settings: Settings) -> Any:
    provider = settings.tts_provider
    if provider == "cartesia":
        from livekit.plugins import cartesia

        kwargs: dict[str, Any] = {}
        if settings.tts_model:
            kwargs["model"] = settings.tts_model
        if settings.tts_voice:
            kwargs["voice"] = settings.tts_voice
        return cartesia.TTS(**kwargs)
    if provider in {"elevenlabs", "eleven"}:
        from livekit.plugins import elevenlabs

        kwargs = {}
        if settings.tts_voice:
            kwargs["voice_id"] = settings.tts_voice
        return elevenlabs.TTS(**kwargs)
    raise ValueError(f"Unsupported TTS_PROVIDER: {provider}")
