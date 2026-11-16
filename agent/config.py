"""Runtime configuration from environment + config/defaults.toml. No secrets hardcoded."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS_PATH = ROOT / "config" / "defaults.toml"

_DEFAULT_TTS_INSTRUCTIONS = (
    "Speak like a warm, polished front-desk receptionist at a professional firm. "
    "Calm, confident, friendly, natural pacing, clear pronunciation. "
    "Short sentences. No robotic or exaggerated tone."
)


def _load_toml_defaults() -> dict:
    if not DEFAULTS_PATH.exists():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover
        return {}
    with DEFAULTS_PATH.open("rb") as f:
        return tomllib.load(f)


def _req(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _opt(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip() or default


def _opt_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return float(raw)


def _opt_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    agent_display_name: str
    provider_mode: str
    stt_model: str
    stt_language: str
    llm_model: str
    llm_temperature: float
    llm_max_tokens: int
    tts_model: str
    tts_voice: str
    tts_language: str
    tts_emotion: str
    tts_instructions: str
    min_endpointing_delay: float
    max_endpointing_delay: float
    min_interruption_duration: float
    allow_interruptions: bool
    preemptive_generation: bool
    turn_detector: str
    turn_detector_version: str
    supabase_url: str
    supabase_service_role_key: str
    transfer_mode: str
    transfer_sip_domain: str
    transfer_main_number: str
    transfer_failure_message: str
    timezone: str
    business_hours_start: str
    business_hours_end: str
    lunch_start: str
    lunch_end: str
    after_hours_message: str
    no_extension_fallback: str
    no_extension_message: str
    mvcap_website: str
    helplink_number: str

    @property
    def greeting(self) -> str:
        return (
            "Thank you for calling Miami Valley Community Action Partnership. "
            f"This is {self.agent_display_name}. How may I help you?"
        )


@lru_cache(maxsize=1)
def get_settings(*, require_livekit: bool = True, require_supabase: bool = False) -> Settings:
    defaults = _load_toml_defaults()
    agent_cfg = defaults.get("agent", {})
    providers = defaults.get("providers", {})
    stt_cfg = defaults.get("stt", {})
    llm_cfg = defaults.get("llm", {})
    tts_cfg = defaults.get("tts", {})
    turn_cfg = defaults.get("turn", {})

    livekit_url = _req("LIVEKIT_URL") if require_livekit else _opt("LIVEKIT_URL")
    livekit_api_key = _req("LIVEKIT_API_KEY") if require_livekit else _opt("LIVEKIT_API_KEY")
    livekit_api_secret = (
        _req("LIVEKIT_API_SECRET") if require_livekit else _opt("LIVEKIT_API_SECRET")
    )
    supabase_url = _req("SUPABASE_URL") if require_supabase else _opt("SUPABASE_URL")
    supabase_key = (
        _req("SUPABASE_SERVICE_ROLE_KEY")
        if require_supabase
        else _opt("SUPABASE_SERVICE_ROLE_KEY")
    )

    return Settings(
        livekit_url=livekit_url,
        livekit_api_key=livekit_api_key,
        livekit_api_secret=livekit_api_secret,
        agent_display_name=_opt(
            "AGENT_DISPLAY_NAME", agent_cfg.get("display_name", "Alex")
        ),
        provider_mode=_opt(
            "PROVIDER_MODE", providers.get("mode", "livekit_inference")
        ).lower(),
        stt_model=_opt("STT_MODEL", stt_cfg.get("model", "deepgram/nova-3")),
        stt_language=_opt("STT_LANGUAGE", stt_cfg.get("language", "en")),
        llm_model=_opt("LLM_MODEL", llm_cfg.get("model", "openai/gpt-4.1-mini")),
        llm_temperature=_opt_float(
            "LLM_TEMPERATURE", float(llm_cfg.get("temperature", 0.3))
        ),
        llm_max_tokens=int(
            _opt_float("LLM_MAX_TOKENS", float(llm_cfg.get("max_tokens", 72)))
        ),
        tts_model=_opt("TTS_MODEL", tts_cfg.get("model", "cartesia/sonic-3")),
        tts_voice=_opt(
            "TTS_VOICE",
            tts_cfg.get("voice", "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"),
        ),
        tts_language=_opt("TTS_LANGUAGE", tts_cfg.get("language", "en")),
        tts_emotion=_opt("TTS_EMOTION", tts_cfg.get("emotion", "calm")),
        tts_instructions=_opt(
            "TTS_INSTRUCTIONS",
            tts_cfg.get("instructions", _DEFAULT_TTS_INSTRUCTIONS),
        ),
        min_endpointing_delay=_opt_float(
            "MIN_ENDPOINTING_DELAY",
            float(turn_cfg.get("min_endpointing_delay", 0.35)),
        ),
        max_endpointing_delay=_opt_float(
            "MAX_ENDPOINTING_DELAY",
            float(turn_cfg.get("max_endpointing_delay", 1.8)),
        ),
        min_interruption_duration=_opt_float(
            "MIN_INTERRUPTION_DURATION",
            float(turn_cfg.get("min_interruption_duration", 0.3)),
        ),
        allow_interruptions=_opt_bool(
            "ALLOW_INTERRUPTIONS",
            bool(turn_cfg.get("allow_interruptions", True)),
        ),
        preemptive_generation=_opt_bool(
            "PREEMPTIVE_GENERATION",
            bool(turn_cfg.get("preemptive_generation", True)),
        ),
        turn_detector=_opt(
            "TURN_DETECTOR", turn_cfg.get("turn_detector", "inference")
        ).lower(),
        turn_detector_version=_opt(
            "TURN_DETECTOR_VERSION",
            str(turn_cfg.get("turn_detector_version", "v1")),
        ),
        supabase_url=supabase_url,
        supabase_service_role_key=supabase_key,
        transfer_mode=_opt("TRANSFER_MODE", "sip_uri").lower(),
        transfer_sip_domain=_opt("TRANSFER_SIP_DOMAIN"),
        transfer_main_number=_opt("TRANSFER_MAIN_NUMBER"),
        transfer_failure_message=_opt(
            "TRANSFER_FAILURE_MESSAGE",
            "I'm sorry, I wasn't able to complete that transfer. "
            "Please try again later, or visit www.miamivalleycap.org.",
        ),
        timezone=_opt("TIMEZONE", "America/New_York"),
        business_hours_start=_opt("BUSINESS_HOURS_START", "08:00"),
        business_hours_end=_opt("BUSINESS_HOURS_END", "16:30"),
        lunch_start=_opt("LUNCH_START", "12:00"),
        lunch_end=_opt("LUNCH_END", "13:00"),
        after_hours_message=_opt(
            "AFTER_HOURS_MESSAGE",
            "Thank you for calling Miami Valley Community Action Partnership. "
            "Our offices are currently closed. Hours are Monday through Friday, "
            "8:00 a.m. to 4:30 p.m., closed for lunch from 12:00 to 1:00. "
            "Please visit www.miamivalleycap.org or call back during business hours. "
            "For additional resources, dial 211.",
        ),
        no_extension_fallback=_opt("NO_EXTENSION_FALLBACK", "main_line"),
        no_extension_message=_opt(
            "NO_EXTENSION_MESSAGE",
            "I'm sorry, I don't have a direct line for that person. "
            "I can transfer you to the main office, or you can leave a message — "
            "which would you prefer?",
        ),
        mvcap_website=_opt("MVCAP_WEBSITE", "https://www.miamivalleycap.org"),
        helplink_number=_opt("HELPLINK_NUMBER", "211"),
    )
