"""Tests réels (Internet + crédit IA). Lancer avec : set ELIOT_LIVE=1 && python -m pytest tests/test_live.py"""
import os


import pytest

pytestmark = pytest.mark.skipif(os.environ.get("ELIOT_LIVE") != "1", reason="test live désactivé (ELIOT_LIVE=1)")


def test_claude_emergent_chat(tmp_path):
    from eliot.config import Settings
    from eliot.llm.engine import LLMEngine
    s = Settings.load(tmp_path / "s.json")
    chunks = []
    text = LLMEngine(s).chat([{"role": "user", "content": "Réponds uniquement : prêt"}], on_delta=chunks.append)
    assert "prêt" in text.lower() and chunks


def test_claude_plans_real_task(services):
    from eliot.llm.engine import LLMEngine
    services.settings.ai_provider = "emergent"
    services.planner.llm = LLMEngine(services.settings)
    task = services.planner.plan("Eliot, ouvre Firefox et recherche la météo à Lyon")
    assert task.steps and task.steps[0].tool in {"search_in_app", "open_app", "web_search"}


def test_voice_roundtrip(tmp_path):
    from eliot.voice.listen import transcribe
    from eliot.voice.speak import synthesize
    mp3 = synthesize("Bonjour, je suis Eliot.", "nova", "tts-1", tmp_path)
    assert os.path.getsize(mp3) > 1000
    assert "bonjour" in transcribe(mp3).lower()


def test_claude_prepares_mail_replies(services, monkeypatch):
    from eliot.llm.engine import LLMEngine
    from eliot.mail.accounts import Mail
    from eliot.mail.service import MailService
    services.settings.ai_provider = "emergent"
    services.llm = LLMEngine(services.settings)
    mails = [Mail("outlook", "1", "Paul", "paul@x.fr", "Réunion", "2026-11-21", "Es-tu disponible lundi à 10h ?"),
             Mail("outlook", "2", "Boutique", "promo@shop.fr", "Soldes -50%", "2026-11-21", "Profitez des soldes !")]
    monkeypatch.setattr(MailService, "check", lambda self, which="", limit=10: setattr(self, "last", mails) or mails)
    drafts = services.mail.prepare(services.llm)
    assert 1 in drafts and 2 not in drafts


def test_wake_pipeline_on_synthetic_voice(tmp_path):
    import json
    import numpy as np
    from vosk import KaldiRecognizer, Model, SetLogLevel
    from emergentintegrations.llm.openai import OpenAITextToSpeech
    import asyncio
    from eliot.voice.listen import transcribe
    from eliot.voice.wakeword import GRAMMAR, command_after_wake, is_wake, write_wav
    model_dir = os.environ.get("ELIOT_VOSK_MODEL")
    if not model_dir:
        pytest.skip("ELIOT_VOSK_MODEL non défini")
    SetLogLevel(-1)
    model = Model(model_dir)
    from eliot.voice.listen import openai_key
    pcm = asyncio.run(OpenAITextToSpeech(api_key=openai_key()).generate_speech(
        text="Eliot, ouvre le bloc-notes.", model="tts-1", voice="onyx", response_format="pcm"))
    a = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
    a16 = np.interp(np.arange(0, len(a), 1.5), np.arange(len(a)), a).astype("<i2").tobytes()
    rec = KaldiRecognizer(model, 16000, json.dumps(GRAMMAR, ensure_ascii=False))
    rec.AcceptWaveform(a16)
    assert {"eliot", "elliot", "hey"} & set(json.loads(rec.FinalResult())["text"].split())
    wav = tmp_path / "w.wav"
    write_wav(wav, [a16])
    text = transcribe(wav)
    assert is_wake(text) and "bloc" in command_after_wake(text).lower()
