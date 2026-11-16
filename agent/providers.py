"""Build STT / LLM / TTS from config (LiveKit Inference or direct plugins)."""

from __future__ import annotations

from typing import Any

from agent.config import Settings


def build_stt(settings: Settings, *, keyterms: list[str] | None = None) -> Any:
    if settings.provider_mode == "livekit_inference":
        from livekit.agents import inference

        extra: dict[str, Any] = {}
        if keyterms:
            # Deepgram nova-3 keyterm biasing (Inference DeepgramOptions)
            extra["keyterm"] = keyterms[:100]
        return inference.STT(
            model=settings.stt_model,
            language=settings.stt_language,
            extra_kwargs=extra,
        )

    # openai_direct fallback
    from livekit.plugins import openai

    model = settings.stt_model or "gpt-4o-transcribe"
    if model.startswith("nova") or "/" in model:
        model = "gpt-4o-transcribe"
    return openai.STT(model=model, language=settings.stt_language or "en")


def build_llm(settings: Settings) -> Any:
    if settings.provider_mode == "livekit_inference":
        from livekit.agents import inference

        extra: dict[str, Any] = {
            "temperature": settings.llm_temperature,
            "max_completion_tokens": settings.llm_max_tokens,
        }
        return inference.LLM(model=settings.llm_model, extra_kwargs=extra)

    from livekit.plugins import openai

    model = settings.llm_model
    if "/" in model:
        model = model.split("/", 1)[-1]
    return openai.LLM(
        model=model or "gpt-4o-mini",
        temperature=settings.llm_temperature,
        max_completion_tokens=settings.llm_max_tokens,
    )


def build_tts(settings: Settings) -> Any:
    if settings.provider_mode == "livekit_inference":
        from livekit.agents import inference

        extra: dict[str, Any] = {}
        if settings.tts_emotion:
            extra["emotion"] = settings.tts_emotion
        return inference.TTS(
            model=settings.tts_model,
            voice=settings.tts_voice,
            language=settings.tts_language or "en",
            extra_kwargs=extra,
        )

    from livekit.plugins import openai

    kwargs: dict[str, Any] = {
        "model": "gpt-4o-mini-tts",
        "voice": settings.tts_voice or "marin",
    }
    if settings.tts_instructions:
        kwargs["instructions"] = settings.tts_instructions
    return openai.TTS(**kwargs)


def build_turn_detector(settings: Settings) -> Any:
    """LiveKit turn detector (preferred) or VAD-only."""
    mode = settings.turn_detector
    if mode == "vad":
        return "vad"
    if mode == "multilingual_plugin":
        from livekit.plugins.turn_detector.multilingual import MultilingualModel

        return MultilingualModel()
    # Default: Inference TurnDetector (cloud v1). Skip local mini preload (~450MB)
    # so worker processes initialize within the default timeout on laptops.
    from livekit.agents import inference

    return inference.TurnDetector(
        version=settings.turn_detector_version,  # type: ignore[arg-type]
        local_fallback=False,
    )


def stt_tts_descriptor(settings: Settings) -> str:
    """Human-readable stack for logs (no secrets)."""
    return (
        f"mode={settings.provider_mode} "
        f"stt={settings.stt_model}:{settings.stt_language} "
        f"llm={settings.llm_model} "
        f"tts={settings.tts_model}:{settings.tts_voice[:8]}…"
    )
