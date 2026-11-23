"""Micro : enregistrement jusqu'au silence, puis transcription française (OpenAI Whisper)."""
import asyncio
import logging
import wave

from ..config import EMERGENT_LLM_KEY
from ..secrets_store import OPENAI, get_secret

log = logging.getLogger("eliot")


class VoiceError(Exception):
    pass


class SpeechTracker:
    """Repère une voix même faible. Le seuil s'adapte au bruit de fond, au lieu d'un niveau fixe
    qui ignorait le micro du casque (parole vers 0,01, ancien seuil 0,015)."""

    def __init__(self, silence_seconds=1.4, min_speech=0.25):
        self.noise = 0.0008
        self.silence_seconds = silence_seconds
        self.min_speech = min_speech
        self.speech = 0.0
        self.silent = 0.0
        self.heard = False

    def threshold(self) -> float:
        return max(0.0032, self.noise * 4.5)

    def push(self, level: float, dt: float = 0.1) -> bool:
        level = max(0.0, float(level))
        if level >= self.threshold():
            self.heard = True
            self.speech += dt
            self.silent = 0.0
            return False
        self.noise = 0.92 * self.noise + 0.08 * level
        if self.heard:
            self.silent += dt
            return self.silent >= self.silence_seconds and self.speech >= self.min_speech
        return False

    @property
    def ok(self) -> bool:
        return self.speech >= self.min_speech


def normalize_audio(samples, target=0.8, max_gain=40.0):
    import numpy as np
    audio = np.asarray(samples, dtype="float32")
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak < 1e-4:
        return audio
    gain = min(max_gain, target / peak)
    if gain <= 1.0:
        return audio
    return np.clip(audio * gain, -1.0, 1.0)


def amplify_pcm(chunk: bytes, state: dict, target=10000.0, max_gain=30.0) -> bytes:
    """Remonte un micro trop faible avant Vosk, sans pousser le gain sur du silence."""
    import numpy as np
    samples = np.frombuffer(chunk, dtype="<i2").astype("float32")
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    gain = state.get("gain", 8.0)
    if peak > 40:
        gain = gain * 0.7 + min(max_gain, target / peak) * 0.3
        state["gain"] = gain
    return np.clip(samples * gain, -32767, 32767).astype("<i2").tobytes()


def openai_key() -> str:
    return get_secret(OPENAI) or EMERGENT_LLM_KEY


def record(path, stop_event, max_seconds=30.0, silence_seconds=1.4, samplerate=16000) -> bool:
    try:
        import numpy as np
        import sounddevice as sd
    except Exception as exc:
        raise VoiceError("Le module micro (sounddevice) est indisponible.") from exc
    block = samplerate // 10
    frames, elapsed = [], 0.0
    tracker = SpeechTracker(silence_seconds=silence_seconds)
    try:
        with sd.InputStream(samplerate=samplerate, channels=1, dtype="float32", blocksize=block) as stream:
            while elapsed < max_seconds and not stop_event.is_set():
                data, _ = stream.read(block)
                frames.append(data.copy())
                elapsed += 0.1
                level = float(np.sqrt(np.mean(np.square(data))))
                if tracker.push(level):
                    break
                if not tracker.heard and elapsed > 10:
                    break
    except Exception as exc:
        raise VoiceError(f"Micro inaccessible : {exc}") from exc
    if not frames or not tracker.ok:
        log.info("Micro : rien d'assez net (parole %.1fs)", tracker.speech)
        return False
    audio = normalize_audio(np.concatenate(frames)[:, 0])
    peak = float(np.max(np.abs(audio)))
    log.info("Micro : parole %.1fs, crête %.2f", tracker.speech, peak)
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(samplerate)
        wav.writeframes(pcm.tobytes())
    return True


def transcribe(path) -> str:
    from emergentintegrations.llm.openai import OpenAISpeechToText
    stt = OpenAISpeechToText(api_key=openai_key())

    async def run():
        with open(path, "rb") as audio:
            response = await stt.transcribe(
                file=audio, model="whisper-1", response_format="json", language="fr", temperature=0,
                prompt="Français. Bloc-notes, Firefox, Cursor, Téléchargements.")
        return getattr(response, "text", "") or ""

    try:
        return asyncio.run(run()).strip()
    except Exception as exc:
        raise VoiceError(f"Transcription impossible : {str(exc)[:200]}") from exc
