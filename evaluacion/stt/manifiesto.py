"""
Write or verify evaluacion/stt/manifiesto.json: the STT evaluation selection with the
SHA-256 of every audio file and of every normalized ground truth.

    python -m evaluacion.stt.manifiesto             # write the manifest
    python -m evaluacion.stt.manifiesto --verificar  # compare against the committed one
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from evaluacion.stt.ejemplos import (
    CORDEBA_EXCLUDED,
    CORDEBA_K,
    CORDEBA_SEED,
    HUMYN_RECORDINGS,
    OUTPUT_BASE,
    RECORDINGS,
    ensure_audio,
)
from evaluacion.stt.wer import load_references

MANIFIESTO = Path(__file__).with_name("manifiesto.json")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build() -> dict:
    refs = load_references(list(RECORDINGS))
    recordings = {}
    for test_id, archivo in RECORDINGS.items():
        audio = ensure_audio(test_id, archivo)
        texto, hasta = refs[test_id]
        recordings[test_id] = {
            "fuente": "humyn" if test_id in HUMYN_RECORDINGS else "cordeba",
            "archivo": archivo,
            "audio_sha256": sha256_file(audio),
            "referencia_palabras": len(texto.split()),
            "referencia_sha256": sha256_bytes(texto.encode("utf-8")),
            "referencia_hasta_s": None if hasta == float("inf") else hasta,
        }
    return {
        "cordeba": {
            "k": CORDEBA_K,
            "semilla": CORDEBA_SEED,
            "excluidas": {f"CordeBA_{n:04d}": motivo for n, motivo in sorted(CORDEBA_EXCLUDED.items())},
        },
        "grabaciones": recordings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Write or verify the STT manifest")
    parser.add_argument("--verificar", action="store_true", help="Compare with the committed manifest")
    args = parser.parse_args()

    actual = build()
    if args.verificar:
        esperado = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
        if actual == esperado:
            print(f"OK: {len(actual['grabaciones'])} recordings match {MANIFIESTO.name}")
            return 0
        for test_id in sorted(set(actual["grabaciones"]) | set(esperado["grabaciones"])):
            if actual["grabaciones"].get(test_id) != esperado["grabaciones"].get(test_id):
                print(f"DIFF: {test_id}")
        if actual["cordeba"] != esperado["cordeba"]:
            print("DIFF: cordeba selection parameters")
        return 1

    MANIFIESTO.write_text(json.dumps(actual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved: {MANIFIESTO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
