"""Runtime configuration from environment. No secrets hardcoded."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _opt(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip() or default


@dataclass(frozen=True)
class Settings:
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    agent_display_name: str
    stt_provider: str
    llm_provider: str
    tts_provider: str
    stt_model: str
    llm_model: str
    tts_model: str
    tts_voice: str
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
    """Load settings. Phase 1 only needs LiveKit; Supabase required from Phase 2+."""

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
        agent_display_name=_opt("AGENT_DISPLAY_NAME", "Alex"),
        stt_provider=_opt("STT_PROVIDER", "deepgram").lower(),
        llm_provider=_opt("LLM_PROVIDER", "openai").lower(),
        tts_provider=_opt("TTS_PROVIDER", "cartesia").lower(),
        stt_model=_opt("STT_MODEL", "nova-3"),
        llm_model=_opt("LLM_MODEL", "gpt-4o-mini"),
        tts_model=_opt("TTS_MODEL", ""),
        tts_voice=_opt("TTS_VOICE", ""),
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
