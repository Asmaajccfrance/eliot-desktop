"""Synthèse vocale : voix réaliste OpenAI, avec Microsoft Hortense (SAPI) en secours."""
import asyncio
import re
import sys
import uuid
from pathlib import Path

from .listen import openai_key


def clean_for_speech(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text or "", flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_#`>|•]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:3800]


def synthesize(text: str, voice: str, model: str, out_dir) -> str:
    from emergentintegrations.llm.openai import OpenAITextToSpeech
    tts = OpenAITextToSpeech(api_key=openai_key())
    audio = asyncio.run(tts.generate_speech(text=text, model=model, voice=voice, response_format="mp3"))
    out = Path(out_dir) / f"eliot_{uuid.uuid4().hex[:8]}.mp3"
    out.write_bytes(audio)
    return str(out)


class HortenseVoice:
    """Voix Windows hors ligne. À utiliser depuis le thread graphique (appels asynchrones SAPI)."""

    def __init__(self):
        self._voice = None

    @property
    def available(self) -> bool:
        return sys.platform == "win32"

    def _ensure(self):
        if self._voice is None:
            import win32com.client
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            tokens = voice.GetVoices()
            chosen = None
            for i in range(tokens.Count):
                desc = tokens.Item(i).GetDescription()
                if "hortense" in desc.lower():
                    chosen = tokens.Item(i)
                    break
                if chosen is None and ("french" in desc.lower() or "fran" in desc.lower()):
                    chosen = tokens.Item(i)
            if chosen is not None:
                voice.Voice = chosen
            self._voice = voice
        return self._voice

    def speak(self, text: str) -> None:
        if self.available and text:
            self._ensure().Speak(text, 1 | 2)

    def stop(self) -> None:
        if self._voice is not None:
            try:
                self._voice.Speak("", 2)
            except Exception:
                pass
