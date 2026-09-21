"""Incrementally cache public ESPN NBA athlete profiles for every known player."""

from __future__ import annotations

import argparse
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import pandas as pd
import requests

from dataUpdateSafety import DataValidationError, atomic_write_csv, player_metadata_by_id


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_OUTPUT = DEFAULT_DATA_DIR / "playerMetadata.csv"
PLAYER_DATASETS = ("playerDailyData.csv", "playerMatchupData.csv", "activityData.csv")
ATHLETE_URL = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/athletes/{player_id}"
REFRESH_AFTER = timedelta(days=7)

METADATA_COLUMNS = [
    "ESPN Player ID", "Full Name", "First Name", "Last Name", "Headshot URL",
    "Height Inches", "Weight Pounds", "Birth Date", "Birth City", "Birth State Region",
    "Birth Country", "NBA Position Name", "NBA Position Abbreviation", "Jersey Number",
    "ESPN NBA Team ID", "NBA Team Name", "Team Relationship", "Draft Year", "Draft Round",
    "Draft Pick", "Debut Year", "NBA Experience Years", "Active", "Status",
    "Profile Source", "Profile Fetched At",
]


@dataclass
class UpdateReport:
    discovered: int
    fetched: int
    refreshed: int
    unresolved: list[int]
    records: int


def discover_player_ids(data_dir: str | Path = DEFAULT_DATA_DIR) -> set[int]:
    """Return the historical union from all canonical player-bearing datasets."""
    directory = Path(data_dir)
    player_ids: set[int] = set()
    found = []
    for filename in PLAYER_DATASETS:
        path = directory / filename
        if not path.exists():
            continue
        frame = pd.read_csv(path, usecols=["Player ID"])
        found.append(filename)
        raw = frame["Player ID"]
        numeric = pd.to_numeric(raw, errors="coerce")
        invalid = raw.notna() & (numeric.isna() | (numeric % 1 != 0) | (numeric <= 0))
        if invalid.any():
            sample = raw.loc[invalid].head(3).tolist()
            raise DataValidationError(f"{filename} contains invalid Player ID values: {sample}")
        player_ids.update(int(value) for value in numeric.dropna())
    if not found:
        raise DataValidationError(f"no player datasets found in {directory}")
    if not player_ids:
        raise DataValidationError("historical player universe is empty")
    return player_ids


def _team_id(ref: str | None) -> int | None:
    if not ref:
        return None
    match = re.search(r"/teams/(\d+)(?:\?|$)", ref)
    return int(match.group(1)) if match else None


def _date_only(value: object) -> str | None:
    return str(value)[:10] if value else None


def _nonempty(value: object) -> bool:
    return value is not None and not (isinstance(value, float) and pd.isna(value)) and value != ""


class EspnAthleteClient:
    """Small public-API client with conservative transient retries."""

    def __init__(self, session: requests.Session | None = None, attempts: int = 3):
        self.session = session or requests.Session()
        self.attempts = attempts
        self.team_names: dict[str, str | None] = {}
        self.headers = {"User-Agent": "BasketballBrawlMetadata/1.0"}

    def _json(self, url: str) -> dict:
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                response = self.session.get(url.replace("http://", "https://"), headers=self.headers, timeout=20)
                if response.status_code == 404:
                    raise LookupError("ESPN athlete profile not found")
                response.raise_for_status()
                return response.json()
            except LookupError:
                raise
            except (requests.RequestException, ValueError) as error:
                last_error = error
                if attempt + 1 < self.attempts:
                    time.sleep(0.5 * (2 ** attempt))
        raise RuntimeError(f"ESPN request failed after {self.attempts} attempts: {last_error}")

    def fetch_player(self, player_id: int, fetched_at: datetime | None = None) -> dict:
        athlete = self._json(ATHLETE_URL.format(player_id=player_id))
        if int(athlete.get("id", -1)) != player_id:
            raise DataValidationError(f"ESPN returned athlete {athlete.get('id')} for requested ID {player_id}")
        team_ref = (athlete.get("team") or {}).get("$ref")
        team_name = None
        if team_ref:
            if team_ref not in self.team_names:
                team = self._json(team_ref)
                self.team_names[team_ref] = team.get("displayName") or team.get("name")
            team_name = self.team_names[team_ref]
        active = athlete.get("active")
        birth = athlete.get("birthPlace") or {}
        position = athlete.get("position") or {}
        draft = athlete.get("draft") or {}
        experience = athlete.get("experience") or {}
        headshot = athlete.get("headshot") or {}
        status = athlete.get("status") or {}
        moment = fetched_at or datetime.now(timezone.utc)
        return {
            "ESPN Player ID": player_id,
            "Full Name": athlete.get("fullName"),
            "First Name": athlete.get("firstName"),
            "Last Name": athlete.get("lastName"),
            "Headshot URL": headshot.get("href"),
            "Height Inches": athlete.get("height"),
            "Weight Pounds": athlete.get("weight"),
            "Birth Date": _date_only(athlete.get("dateOfBirth")),
            "Birth City": birth.get("city"),
            "Birth State Region": birth.get("state") or birth.get("region"),
            "Birth Country": birth.get("country"),
            "NBA Position Name": position.get("displayName") or position.get("name"),
            "NBA Position Abbreviation": position.get("abbreviation"),
            "Jersey Number": athlete.get("jersey"),
            "ESPN NBA Team ID": _team_id(team_ref),
            "NBA Team Name": team_name,
            "Team Relationship": "current" if active is True else "last-known" if team_ref else None,
            "Draft Year": draft.get("year"),
            "Draft Round": draft.get("round"),
            "Draft Pick": draft.get("selection"),
            "Debut Year": athlete.get("debutYear"),
            "NBA Experience Years": experience.get("years"),
            "Active": active,
            "Status": status.get("type") or status.get("name"),
            "Profile Source": "espn-core-athlete",
            "Profile Fetched At": moment.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }


def load_metadata(path: str | Path = DEFAULT_OUTPUT) -> pd.DataFrame:
    source = Path(path)
    if not source.exists():
        return pd.DataFrame(columns=METADATA_COLUMNS)
    frame = pd.read_csv(source, dtype={"Jersey Number": "string"})
    validate_metadata(frame)
    return frame


def validate_metadata(frame: pd.DataFrame, discovered_ids: set[int] | None = None, unresolved: set[int] | None = None) -> None:
    missing = set(METADATA_COLUMNS).difference(frame.columns)
    if missing:
        raise DataValidationError(f"player metadata is missing columns: {sorted(missing)}")
    by_id = player_metadata_by_id(frame)
    for player_id, record in by_id.items():
        if not _nonempty(record.get("Full Name")) or record.get("Profile Source") != "espn-core-athlete":
            raise DataValidationError(f"player metadata record {player_id} is incomplete")
    if discovered_ids is not None:
        unexplained = discovered_ids.difference(by_id).difference(unresolved or set())
        if unexplained:
            raise DataValidationError(f"player metadata silently omits IDs: {sorted(unexplained)}")


def _is_due(record: dict, now: datetime) -> bool:
    active = record.get("Active")
    if isinstance(active, str):
        active = active.casefold() == "true"
    if active is not True:
        return False
    value = record.get("Profile Fetched At")
    if not _nonempty(value):
        return True
    try:
        fetched = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return True
    return now - fetched >= REFRESH_AFTER


def merge_profile(previous: dict | None, fetched: dict) -> dict:
    """Apply a refresh without replacing established values with nulls."""
    if previous is None:
        return {column: fetched.get(column) for column in METADATA_COLUMNS}
    merged = dict(previous)
    for column in METADATA_COLUMNS:
        value = fetched.get(column)
        if _nonempty(value):
            merged[column] = value
    return merged


def update_player_metadata(
    data_dir: str | Path = DEFAULT_DATA_DIR,
    output_path: str | Path = DEFAULT_OUTPUT,
    fetch_player: Callable[[int, datetime], dict] | None = None,
    now: datetime | None = None,
) -> UpdateReport:
    moment = now or datetime.now(timezone.utc)
    discovered = discover_player_ids(data_dir)
    existing = load_metadata(output_path)
    records = player_metadata_by_id(existing) if not existing.empty else {}
    new_ids = discovered.difference(records)
    due_ids = {player_id for player_id, record in records.items() if player_id in discovered and _is_due(record, moment)}
    client = EspnAthleteClient()
    fetch = fetch_player or client.fetch_player
    unresolved: list[int] = []
    changed = False
    for player_id in sorted(new_ids | due_ids):
        try:
            profile = fetch(player_id, moment)
            records[player_id] = merge_profile(records.get(player_id), profile)
            changed = True
        except Exception as error:  # isolate one ESPN profile from the full cache
            unresolved.append(player_id)
            print(f"WARNING: unresolved ESPN Player ID {player_id}: {type(error).__name__}: {error}")

    candidate = pd.DataFrame([records[player_id] for player_id in sorted(records)], columns=METADATA_COLUMNS)
    validate_metadata(candidate, discovered, set(unresolved))
    if changed:
        atomic_write_csv(candidate, output_path)
    report = UpdateReport(len(discovered), len(new_ids - set(unresolved)), len(due_ids - set(unresolved)), unresolved, len(candidate))
    print(
        f"Player metadata: discovered={report.discovered}, records={report.records}, "
        f"new={report.fetched}, refreshed={report.refreshed}, unresolved={report.unresolved}"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    update_player_metadata(arguments.data_dir, arguments.output)
