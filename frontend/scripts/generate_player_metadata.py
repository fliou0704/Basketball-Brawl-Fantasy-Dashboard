"""Export canonical player metadata as an ESPN-ID-keyed frontend payload."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pandas as pd


def _value(value):
    if pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def build(source: Path, output: Path) -> dict:
    frame = pd.read_csv(source / "playerMetadata.csv", dtype={"Jersey Number": "string"})
    ids = pd.to_numeric(frame["ESPN Player ID"], errors="raise").astype(int)
    if ids.duplicated().any():
        raise ValueError("player metadata contains duplicate ESPN Player IDs")
    players = {}
    for (_, row), player_id in zip(frame.iterrows(), ids):
        record = {column: _value(value) for column, value in row.items() if column != "ESPN Player ID"}
        players[str(player_id)] = record
    payload = {"schemaVersion": 1, "players": players}
    destination = output / "player-metadata.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", prefix=".player-metadata-", dir=destination.parent, delete=False) as temporary:
        json.dump(payload, temporary, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        temporary_path = Path(temporary.name)
    try:
        os.replace(temporary_path, destination)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return payload
