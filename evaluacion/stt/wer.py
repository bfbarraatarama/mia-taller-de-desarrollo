"""
Compute WER for the STT outputs in evaluacion/stt/generado against the Humyn ground truth.

Texts are normalized (lowercase, no accents, no punctuation/symbols) before comparing.
For Humyn only ASR segments starting before the last ground-truth timestamp are used, since
the ground truth is shorter than the audio. CORdeBA has no timestamps: the full ASR is used.
Writes evaluacion/stt/resultados/wer.json and copies each evaluated asr.json to
evaluacion/stt/resultados/asr/<ID>.json (both versioned, unlike generado/).

    python -m evaluacion.stt.wer                    # every ID in generado/
    python -m evaluacion.stt.wer --ids PER-1 PER-2  # only these IDs
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import sys
import unicodedata
from pathlib import Path

import jiwer
import pandas as pd

from src.rutas import ARCHIVO_ASR

from evaluacion.stt.ejemplos import (
    CORDEBA_CACHE,
    HUMYN_CACHE,
    HUMYN_RECORDINGS,
    OUTPUT_BASE,
    RECORDINGS,
)

logger = logging.getLogger(__name__)

ARCHIVO_WER = "wer.json"
RESULTADOS = Path(__file__).with_name("resultados")
RESULTADOS_ASR = RESULTADOS / "asr"


def normalize(text: str) -> str:
    """Lowercase, strip accents, punctuation and symbols (e.g. CORdeBA's '='), collapse whitespace."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(
        c for c in text
        if unicodedata.category(c) != "Mn" and unicodedata.category(c)[0] not in "PS"
    )
    return re.sub(r"\s+", " ", text).strip()


def parse_timestamp(value: str) -> float:
    """Convert 'HH:MM:SS.mmm' to seconds."""
    h, m, s = value.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def load_hypothesis(test_id: str, until: float, base: Path = OUTPUT_BASE) -> str:
    """Normalized ASR text from the segments that start before `until` seconds."""
    with open(base / test_id / ARCHIVO_ASR, encoding="utf-8") as f:
        asr = json.load(f)
    return normalize(" ".join(seg["text"] for seg in asr["segments"] if seg["start"] < until))


def load_references(test_ids: list[str]) -> dict[str, tuple[str, float]]:
    """Return {test_id: (normalized ground truth, last timestamp in s)}."""
    import pyarrow.parquet as pq

    refs: dict[str, tuple[str, float]] = {}

    humyn = {RECORDINGS[i]: i for i in test_ids if i in HUMYN_RECORDINGS}
    if humyn:
        for parquet in sorted(HUMYN_CACHE.glob("*.parquet")):
            df = pq.read_table(parquet, columns=["file_name", "transcript_json"]).to_pandas()
            for _, row in df[df["file_name"].isin(humyn)].iterrows():
                segments = json.loads(row["transcript_json"])
                refs[humyn[row["file_name"]]] = (
                    normalize(" ".join(s["text"] for s in segments)),
                    parse_timestamp(segments[-1]["end"]),
                )

    cordeba = {f"data/{RECORDINGS[i]}": i for i in test_ids if i not in HUMYN_RECORDINGS}
    if cordeba:
        df = pd.read_csv(CORDEBA_CACHE / "metadata.csv")
        for _, row in df[df["file_name"].isin(cordeba)].iterrows():
            turns = json.loads(row["text"])
            refs[cordeba[row["file_name"]]] = (
                normalize(" ".join(t["text"] for t in turns)),
                float("inf"),
            )
    return refs


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute WER of generado/*/asr.json")
    parser.add_argument("--ids", nargs="+", help="Specific IDs (default: all in generado/)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.ids:
        ids = args.ids
    else:
        ids = sorted(p.parent.name for p in OUTPUT_BASE.glob(f"*/{ARCHIVO_ASR}"))

    valid = []
    for test_id in ids:
        if test_id not in RECORDINGS:
            logger.warning(f"SKIP {test_id}: no ground truth mapping")
        elif not (OUTPUT_BASE / test_id / ARCHIVO_ASR).exists():
            logger.warning(f"SKIP {test_id}: missing {ARCHIVO_ASR}")
        else:
            valid.append(test_id)
    if not valid:
        logger.error("Nothing to evaluate")
        return 1

    refs = load_references(valid)

    results: dict[str, float] = {}
    for test_id in valid:
        entry = refs.get(test_id)
        if not entry or not entry[0]:
            logger.warning(f"SKIP {test_id}: ground truth not found")
            continue
        ref, until = entry
        results[test_id] = jiwer.wer(ref, load_hypothesis(test_id, until))
        RESULTADOS_ASR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(OUTPUT_BASE / test_id / ARCHIVO_ASR, RESULTADOS_ASR / f"{test_id}.json")
        logger.info(f"{test_id}: WER = {results[test_id]:.2%}")

    if not results:
        return 1

    average = sum(results.values()) / len(results)
    logger.info(f"Average WER ({len(results)} files): {average:.2%}")

    RESULTADOS.mkdir(exist_ok=True)
    output = RESULTADOS / ARCHIVO_WER
    output.write_text(
        json.dumps({"wer": dict(sorted(results.items())), "average_wer": average}, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info(f"Saved: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
