"""Contract tests for Stage 3 (no Whisper model required)."""

import pytest

pytest.importorskip("whisper")

from STT.asr_core import build_asr, validate_asr_contract  # noqa: E402

WHISPER_RESULT = {
    "segments": [
        {
            "id": 0,
            "start": 0.5,
            "end": 4.2,
            "text": " Vamos a revisar.",
            "words": [
                {"word": " Vamos", "start": 0.5, "end": 0.8, "probability": 0.9},
                {"word": " a", "start": 0.8, "end": 0.9},
                {"word": " ", "start": 0.9, "end": 1.0},
                {"word": " revisar.", "start": 1.0, "end": 1.0},
            ],
        },
        {"id": 1, "start": 5.0, "end": 6.0, "text": "  ", "words": []},
    ]
}


def test_build_asr_follows_contract():
    asr = build_asr(WHISPER_RESULT)
    assert asr == {
        "language": "es",
        "segments": [
            {
                "start": 0.5,
                "end": 4.2,
                "text": "Vamos a revisar.",
                "words": [
                    {"word": "Vamos", "start": 0.5, "end": 0.8},
                    {"word": "a", "start": 0.8, "end": 0.9},
                ],
            }
        ],
    }
    validate_asr_contract(asr, audio_duration=5.0)


def test_no_speaker_information():
    asr = build_asr(WHISPER_RESULT)
    assert all("speaker" not in seg for seg in asr["segments"])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda a: a.pop("language"),
        lambda a: a["segments"][0].update(text=""),
        lambda a: a["segments"][0].update(start=5.0),
        lambda a: a["segments"][0].pop("words"),
        lambda a: a["segments"][0]["words"][0].update(word=""),
        lambda a: a["segments"][0]["words"][0].update(end=0.1),
        lambda a: a["segments"][0].update(end=100.0),
    ],
)
def test_invalid_asr_rejected(mutate):
    asr = build_asr(WHISPER_RESULT)
    mutate(asr)
    with pytest.raises(ValueError):
        validate_asr_contract(asr, audio_duration=5.0)


class _FakeModel:
    def __init__(self, fail):
        self.fail = fail

    def transcribe(self, *args, **kwargs):
        if self.fail:
            raise RuntimeError("boom")
        return WHISPER_RESULT


@pytest.mark.parametrize("fail", [False, True])
def test_process_asr_releases_model(tmp_path, monkeypatch, fail):
    import gc
    import weakref

    import numpy as np
    import whisper

    from STT import asr_core

    refs = []

    def fake_load_model(size, device):
        model = _FakeModel(fail)
        refs.append(weakref.ref(model))
        return model

    monkeypatch.setattr(whisper, "load_model", fake_load_model)
    monkeypatch.setattr(whisper, "load_audio", lambda path: np.zeros(16000 * 6))
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"")

    if fail:
        with pytest.raises(RuntimeError):
            asr_core.process_asr(audio, tmp_path / "asr.json", device="cpu")
    else:
        asr_core.process_asr(audio, tmp_path / "asr.json", device="cpu")

    gc.collect()
    assert refs and refs[0]() is None
