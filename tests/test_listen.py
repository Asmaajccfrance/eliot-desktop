import numpy as np

from eliot.voice.listen import SpeechTracker, normalize_audio


def test_quiet_headset_speech_is_kept():
    """Le casque USB parlait vers 0,01 : l'ancien seuil 0,015 jetait la phrase."""
    meter = SpeechTracker()
    levels = [0.0] * 8 + [0.003, 0.013, 0.010, 0.014, 0.010, 0.009, 0.014, 0.007] + [0.0] * 20
    stopped = False
    for level in levels:
        stopped = meter.push(level)
    assert meter.ok
    assert stopped
    assert meter.speech >= 0.5


def test_room_noise_alone_is_ignored():
    meter = SpeechTracker()
    for _ in range(30):
        meter.push(0.0004)
    assert not meter.ok


def test_normalize_raises_quiet_speech():
    samples = np.zeros(1600, dtype="float32")
    samples[200:600] = 0.014
    out = normalize_audio(samples)
    assert float(np.max(np.abs(out))) > 0.5
