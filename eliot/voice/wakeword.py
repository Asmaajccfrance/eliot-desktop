"""« Hey Eliot » : écoute locale hors ligne (Vosk) + confirmation d'un court extrait par Whisper.

Vosk tourne en continu sur le PC sans rien envoyer. Seuls les extraits de ~3 secondes où il croit entendre
« Eliot » sont transcrits par Whisper pour confirmer (et récupérer la commande dite dans la foulée)."""
import collections
import json
import logging
import re
import tempfile
import threading
import time
import urllib.request
import wave
import zipfile
from pathlib import Path

from ..commands.router import clean
from ..text import norm, simplify
from .listen import amplify_pcm

log = logging.getLogger("eliot")
MODEL_NAME = "vosk-model-small-fr-0.22"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
GRAMMAR = ["hey eliot", "eliot", "elliot", "[unk]"]
CANDIDATE = {"eliot", "elliot", "hey"}
WAKE_WORD = re.compile(r"\b(?:h?e+l+[iy]+o+t*e?s?|el+iet+|alliot)\b")


def is_wake(text: str) -> bool:
    return bool(WAKE_WORD.search(simplify(text)))


def command_after_wake(text: str) -> str:
    low = norm(text)
    m = None
    for m in re.finditer(r"\b(?:h?e+l+[iy]+o+t*e?s?|el+iet+|alliot)\b", low):
        break
    if m is None:
        return ""
    rest = text[m.end():]
    return clean(rest)[0] if rest.strip(" ,.!?") else ""


def ensure_model(models_dir: Path, progress=None) -> Path:
    target = Path(models_dir) / MODEL_NAME
    if (target / "am").exists():
        return target
    Path(models_dir).mkdir(parents=True, exist_ok=True)
    archive = Path(models_dir) / f"{MODEL_NAME}.zip"
    if progress:
        progress("Téléchargement du modèle « Hey Eliot » (45 Mo)…")
    urllib.request.urlretrieve(MODEL_URL, archive)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(models_dir)
    archive.unlink(missing_ok=True)
    return target


def _rms(chunk: bytes) -> float:
    import numpy as np
    samples = np.frombuffer(chunk, dtype="<i2").astype("float32")
    return float(np.sqrt(np.mean(samples ** 2))) if samples.size else 0.0


def write_wav(path, chunks, samplerate=16000) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(samplerate)
        wav.writeframes(b"".join(chunks))


class WakeWordListener:
    def __init__(self, models_dir, on_detect, on_status=None, confirm=None, samplerate=16000):
        self.models_dir = Path(models_dir)
        self.on_detect = on_detect
        self.on_status = on_status or (lambda msg: None)
        self.confirm = confirm
        self.samplerate = samplerate
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._idle = threading.Event()
        self._idle.set()
        self._thread = None
        self._last_check = 0.0
        self._gain = {"gain": 8.0}

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="eliot-wake", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def pause(self) -> None:
        self._paused.set()

    def wait_until_released(self, timeout=2.0) -> bool:
        """Ferme le micro avant un autre enregistrement. Deux flux en même temps n'entendent presque rien."""
        self.pause()
        return self._idle.wait(timeout)

    def resume(self) -> None:
        self._paused.clear()

    def _check(self, chunks) -> None:
        if self.confirm is None:
            self._paused.set()
            self.on_detect("")
            return
        path = Path(tempfile.gettempdir()) / "eliot_wake.wav"
        write_wav(path, chunks, self.samplerate)
        try:
            text = self.confirm(path)
        except Exception as exc:
            log.warning("Confirmation « Hey Eliot » impossible : %s", exc)
            return
        if is_wake(text):
            self._paused.set()
            self.on_detect(command_after_wake(text))

    def _listen_until_paused(self, sd, rec, block):
        ring = collections.deque(maxlen=8)
        with sd.RawInputStream(samplerate=self.samplerate, blocksize=block, dtype="int16", channels=1) as stream:
            while not self._stop.is_set() and not self._paused.is_set():
                data, _ = stream.read(block)
                raw = bytes(data)
                chunk = amplify_pcm(raw, self._gain)
                ring.append(chunk)
                final = rec.AcceptWaveform(chunk)
                text = json.loads(rec.Result())["text"] if final else json.loads(rec.PartialResult())["partial"]
                if not (CANDIDATE & set(text.split())) or time.monotonic() - self._last_check <= 2.5:
                    continue
                self._last_check = time.monotonic()
                clip, quiet = list(ring), 0
                for _ in range(36):
                    if self._stop.is_set() or self._paused.is_set():
                        break
                    more, _ = stream.read(block)
                    raw = bytes(more)
                    clip.append(amplify_pcm(raw, self._gain))
                    quiet = quiet + 1 if _rms(raw) < 140 else 0
                    if quiet >= 5:
                        break
                rec.Reset()
                return clip
        return None

    def _run(self) -> None:
        try:
            import sounddevice as sd
            from vosk import KaldiRecognizer, Model, SetLogLevel
            SetLogLevel(-1)
            model = Model(str(ensure_model(self.models_dir, self.on_status)))
            rec = KaldiRecognizer(model, self.samplerate, json.dumps(GRAMMAR, ensure_ascii=False))
            self.on_status("« Hey Eliot » est à l'écoute.")
            block = self.samplerate // 4
            while not self._stop.is_set():
                if self._paused.is_set():
                    self._idle.set()
                    rec.Reset()
                    if self._stop.wait(0.05):
                        break
                    continue
                self._idle.clear()
                try:
                    clip = self._listen_until_paused(sd, rec, block)
                finally:
                    self._idle.set()
                if clip:
                    self._check(clip)
        except Exception as exc:
            log.exception("Écoute « Hey Eliot » arrêtée")
            self.on_status(f"« Hey Eliot » indisponible : {str(exc)[:160]}")
        finally:
            self._idle.set()
