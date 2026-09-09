"""Safely rebuild the current Activity season from ESPN and manual trades."""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from espn_api.basketball import League
from espn_api.requests.espn_requests import ESPNInvalidLeague

from dataUpdateSafety import DataValidationError, atomic_write_csv, require_espn_credentials

LEAGUE_ID = 609694684
ACTIVITY_PATH = Path("data/activityData.csv")
BACKUP_PATH = Path("data/activityDataBackup.csv")
TRADE_PATH = Path("data/activityTradeSupplement.csv")
TIMEZONE = ZoneInfo("America/New_York")
SCHEMA = ["Unnamed: 0", "Year", "Date", "Time", "Team Name", "Asset", "Action", "Team ID", "Player ID"]
AUTOMATED_ACTIONS = {"WAIVER ADDED", "FA ADDED", "DROPPED"}
ALL_ACTIONS = AUTOMATED_ACTIONS | {"DRAFTED", "KEEPER", "NOT KEPT", "TRADED", "RECEIVED"}
OWNED_AFTER_ACTION = {"DRAFTED", "KEEPER", "WAIVER ADDED", "FA ADDED", "RECEIVED"}
ACTIVITY_KEY = ["Year", "Date", "Time", "Team ID", "Player ID", "Action"]
TRADE_COLUMNS = ["Year", "Date", "Time", "Player ID", "From Team ID", "To Team ID", "ESPN Trade ID"]


def _upper(value):
    return str(value or "").upper()


def transaction_occurred(transaction):
    return _upper(transaction.get("status")) == "EXECUTED" and not bool(transaction.get("isPending", False))


def acquisition_occurred(transaction):
    """Apply the finalized type-specific execution rules observed in live data."""
    if not transaction_occurred(transaction):
        return False
    expected_execution = {
        "WAIVER": "PROCESS",
        "FREEAGENT": "EXECUTE",
        "ROSTER": "EXECUTE",
    }
    kind = _upper(transaction.get("type"))
    return kind in expected_execution and _upper(transaction.get("executionType")) == expected_execution[kind]


def _instant(transaction, trade=False):
    fields = ("acceptedDate", "processDate", "proposedDate") if trade else ("processDate", "acceptedDate", "proposedDate")
    for field in fields:
        value = transaction.get(field)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, TIMEZONE)
    raise DataValidationError(f"ESPN transaction {transaction.get('id')} has no usable timestamp")


def fetch_transactions(league, requester=requests.get):
    """Fetch every ESPN partition, including offseason and post-playoff activity."""
    transactions = {}
    trade_accepts = []
    for period in range(0, int(league.scoringPeriodId) + 1):
        response = requester(
            league.espn_request.LEAGUE_ENDPOINT,
            params={"view": "mTransactions2", "scoringPeriodId": period},
            cookies=league.espn_request.cookies,
            timeout=45,
        )
        response.raise_for_status()
        for transaction in response.json().get("transactions", []):
            transaction_id = transaction.get("id")
            if not transaction_id:
                raise DataValidationError("ESPN returned a transaction without an ID")
            if transaction_id in transactions and transactions[transaction_id] != transaction:
                raise DataValidationError(f"ESPN transaction {transaction_id} changed across partitions")
            transactions[transaction_id] = transaction
    for transaction in transactions.values():
        if _upper(transaction.get("type")) == "TRADE_ACCEPT" and transaction_occurred(transaction):
            trade_accepts.append(transaction)
    return list(transactions.values()), trade_accepts


def _team_maps(league):
    names = {int(team.team_id): team.team_name for team in league.teams}
    players = dict(league.player_map)
    return names, players


def _row(year, moment, team_id, player_id, action, team_names, player_names):
    if team_id in (None, 0) or player_id is None:
        raise DataValidationError(f"{action} is missing a team or player ID")
    team_id, player_id = int(team_id), int(player_id)
    if team_id not in team_names or player_id not in player_names:
        raise DataValidationError(f"{action} references unknown team/player {team_id}/{player_id}")
    return {"Year": int(year), "Date": moment.strftime("%Y-%m-%d"), "Time": moment.strftime("%H:%M"),
            "Team Name": team_names[team_id], "Asset": player_names[player_id], "Action": action,
            "Team ID": team_id, "Player ID": player_id}


def build_automated_rows(year, transactions, team_names, player_names):
    rows = []
    for transaction in transactions:
        kind = _upper(transaction.get("type"))
        if kind == "TRADE_ACCEPT" and transaction_occurred(transaction):
            moment = _instant(transaction, trade=True)
            for item in transaction.get("items", []):
                # Player movements remain manual. Only explicit roster-cleanup
                # drops attached to the finalized acceptance are automated.
                if _upper(item.get("type")) == "DROP":
                    rows.append(_row(year, moment, item.get("fromTeamId"), item.get("playerId"), "DROPPED", team_names, player_names))
            continue
        if not acquisition_occurred(transaction):
            continue
        moment = _instant(transaction)
        for item in transaction.get("items", []):
            operation = _upper(item.get("type"))
            if operation == "ADD":
                action = "WAIVER ADDED" if kind == "WAIVER" else "FA ADDED"
                rows.append(_row(year, moment, item.get("toTeamId"), item.get("playerId"), action, team_names, player_names))
            elif operation == "DROP":
                rows.append(_row(year, moment, item.get("fromTeamId"), item.get("playerId"), "DROPPED", team_names, player_names))
    return pd.DataFrame(rows)


def _draft_instant(transactions):
    times = [_instant(t) for t in transactions if _upper(t.get("type")) == "DRAFT" and transaction_occurred(t)]
    if not times:
        raise DataValidationError("ESPN returned draft picks but no completed draft timestamp")
    return min(times)


def build_draft_rows(year, league, transactions, team_names, player_names):
    picks = list(league.draft)
    if not picks:
        return pd.DataFrame()
    moment = _draft_instant(transactions)
    rows = []
    for pick in picks:
        player_id = getattr(pick, "playerId", None)
        if player_id is None:
            matches = [key for key, value in player_names.items() if value == pick.playerName]
            if len(matches) != 1:
                raise DataValidationError(f"Cannot uniquely identify drafted player {pick.playerName}")
            player_id = matches[0]
        rows.append(_row(year, moment, pick.team.team_id, player_id,
                         "KEEPER" if bool(pick.keeper_status) else "DRAFTED", team_names, player_names))
    return pd.DataFrame(rows)


def build_manual_trade_rows(year, manual, team_names, player_names):
    if list(manual.columns) != TRADE_COLUMNS:
        raise DataValidationError(f"trade supplement columns must be {TRADE_COLUMNS}")
    current = manual[pd.to_numeric(manual["Year"], errors="coerce") == year].copy()
    if current.duplicated(TRADE_COLUMNS).any():
        raise DataValidationError("trade supplement contains duplicate player movements")
    rows = []
    for record in current.to_dict("records"):
        time = str(record["Time"]).strip() if pd.notna(record["Time"]) else "00:00"
        moment = pd.to_datetime(f"{record['Date']} {time}", errors="raise").to_pydatetime().replace(tzinfo=TIMEZONE)
        rows.append(_row(year, moment, record["From Team ID"], record["Player ID"], "TRADED", team_names, player_names))
        rows.append(_row(year, moment, record["To Team ID"], record["Player ID"], "RECEIVED", team_names, player_names))
    return pd.DataFrame(rows)


def build_not_kept_rows(existing, year, draft_rows):
    if draft_rows.empty:
        return pd.DataFrame()
    previous = existing[pd.to_numeric(existing["Year"]) == year - 1].copy()
    if previous.empty:
        raise DataValidationError(f"cannot derive {year} NOT KEPT without {year - 1} activity")
    previous["_when"] = pd.to_datetime(previous["Date"].astype(str) + " " + previous["Time"].fillna("00:00").astype(str))
    previous = previous.sort_values(["_when", "Unnamed: 0"], kind="stable")
    latest = previous.groupby(["Team ID", "Player ID"], dropna=True).tail(1)
    keepers = set(draft_rows[draft_rows["Action"] == "KEEPER"][["Team ID", "Player ID"]].itertuples(index=False, name=None))
    draft_moment = pd.to_datetime(draft_rows.iloc[0]["Date"] + " " + draft_rows.iloc[0]["Time"]).to_pydatetime().replace(tzinfo=TIMEZONE)
    rows = []
    for record in latest.to_dict("records"):
        identity = (int(record["Team ID"]), int(record["Player ID"]))
        if record["Action"] in OWNED_AFTER_ACTION and identity not in keepers:
            rows.append({"Year": year, "Date": draft_moment.strftime("%Y-%m-%d"), "Time": draft_moment.strftime("%H:%M"),
                         "Team Name": record["Team Name"], "Asset": record["Asset"], "Action": "NOT KEPT",
                         "Team ID": identity[0], "Player ID": identity[1]})
    return pd.DataFrame(rows)


def validate_activity(frame):
    if list(frame.columns) != SCHEMA:
        raise DataValidationError(f"activity data columns must be {SCHEMA}")
    if frame.empty:
        raise DataValidationError("activity data is empty")
    if not set(frame["Action"]).issubset(ALL_ACTIONS):
        raise DataValidationError("activity data contains an unknown action")
    for column in ("Unnamed: 0", "Year", "Team ID"):
        if pd.to_numeric(frame[column], errors="coerce").isna().any():
            raise DataValidationError(f"activity data contains invalid {column}")
    if frame.duplicated(ACTIVITY_KEY).any():
        raise DataValidationError("activity data contains duplicate logical rows")
    pd.to_datetime(frame["Date"].astype(str) + " " + frame["Time"].astype(str), errors="raise")


def prepare_activity_update(existing, current_rows, year):
    original = existing.copy(deep=True)
    history = existing[pd.to_numeric(existing["Year"]) < year].copy()
    if len(history) != len(existing[pd.to_numeric(existing["Year"]) != year]):
        raise DataValidationError("activity data contains a future season")
    current = current_rows.copy()
    required = [column for column in SCHEMA if column != "Unnamed: 0"]
    if list(current.columns) != required or current[required].isna().any().any():
        raise DataValidationError("generated current-season activity has missing or incorrect columns")
    current = current.sort_values(["Date", "Time", "Team ID", "Player ID", "Action"], kind="stable").reset_index(drop=True)
    start = int(pd.to_numeric(history["Unnamed: 0"]).max()) + 1 if len(history) else 0
    current.insert(0, "Unnamed: 0", range(start, start + len(current)))
    current = current[SCHEMA]
    candidate = pd.concat([history, current], ignore_index=True)
    validate_activity(candidate)
    pd.testing.assert_frame_equal(history.reset_index(drop=True), original[pd.to_numeric(original["Year"]) < year].reset_index(drop=True))
    return candidate


def draft_is_complete(league):
    """Use ESPN's explicit completion flag, not a partial-pick count."""
    payload = league.espn_request.get_league_draft()
    detail = payload.get("draftDetail", {})
    return detail.get("drafted") is True, len(detail.get("picks", []))


def build_activity_candidate(existing, league, year, manual_source):
    complete, raw_pick_count = draft_is_complete(league)
    if not complete:
        raise DataValidationError(f"ESPN draft for {year} is not complete")
    transactions, trade_accepts = fetch_transactions(league)
    team_names, player_names = _team_maps(league)
    automated = build_automated_rows(year, transactions, team_names, player_names)
    draft = build_draft_rows(year, league, transactions, team_names, player_names)
    if raw_pick_count != len(draft):
        raise DataValidationError("ESPN draft endpoint changed between reads")
    manual = build_manual_trade_rows(year, manual_source, team_names, player_names)
    not_kept = build_not_kept_rows(existing, year, draft)
    current = pd.concat([automated, draft, manual, not_kept], ignore_index=True)
    candidate = prepare_activity_update(existing, current, year)
    executed_ids = {str(transaction["id"]) for transaction in trade_accepts}
    manual_ids = set(manual_source.loc[
        pd.to_numeric(manual_source["Year"], errors="coerce") == year, "ESPN Trade ID"
    ].dropna().astype(str)) - {""}
    report = {
        "counts": current["Action"].value_counts().to_dict(),
        "finalized_espn_trade_accepts": len(executed_ids),
        "manual_player_movements": len(manual) // 2,
        "unreconciled_espn_trade_accepts": sorted(executed_ids - manual_ids),
        "supplement_ids_not_finalized": sorted(manual_ids - executed_ids),
    }
    return candidate, current, report


def write_activity_update(existing, current_rows, year, destination=ACTIVITY_PATH, backup=BACKUP_PATH):
    candidate = prepare_activity_update(existing, current_rows, year)
    if candidate.equals(existing):
        return False
    shutil.copy2(destination, backup)
    atomic_write_csv(candidate, destination)
    return True


def update_activity_data(year=None, write=False):
    swid, espn_s2 = require_espn_credentials()
    existing = pd.read_csv(ACTIVITY_PATH)
    if year is not None:
        requested = int(year)
        league = League(league_id=LEAGUE_ID, year=requested, espn_s2=espn_s2, swid=swid)
    else:
        stored_year = int(pd.to_numeric(existing["Year"]).max())
        requested = stored_year + 1
        try:
            next_league = League(league_id=LEAGUE_ID, year=requested, espn_s2=espn_s2, swid=swid)
            # A future shell can exist before its Activity season has begun.
            # Rollover only when ESPN has a completed draft to anchor the season.
            complete, _ = draft_is_complete(next_league)
            if not complete:
                raise DataValidationError("next ESPN season has no completed draft")
            league = next_league
        except (ESPNInvalidLeague, DataValidationError):
            requested = stored_year
            league = League(league_id=LEAGUE_ID, year=requested, espn_s2=espn_s2, swid=swid)
    manual_source = pd.read_csv(TRADE_PATH)
    candidate, current, report = build_activity_candidate(existing, league, requested, manual_source)
    unreconciled = report["unreconciled_espn_trade_accepts"]
    unknown = report["supplement_ids_not_finalized"]
    if unreconciled or unknown:
        print(f"WARNING: trade reconciliation requires review: {len(unreconciled)} finalized ESPN trade IDs lack supplemental movements; {len(unknown)} supplemental trade IDs were not finalized by ESPN. No trade rows were inferred.")
    print(f"Activity {requested} candidate counts: {report['counts']}")
    print(f"finalized ESPN trades={report['finalized_espn_trade_accepts']}, manual player movements={report['manual_player_movements']}, unreconciled={len(unreconciled)}")
    print(f"historical rows preserved exactly: {candidate[candidate['Year'] < requested].reset_index(drop=True).equals(existing[existing['Year'] < requested].reset_index(drop=True))}")
    if not write:
        print("PREVIEW ONLY: production Activity was not written")
        return False
    changed = write_activity_update(existing, current, requested)
    print(f"Activity {requested}: {'updated' if changed else 'already current'}")
    return changed


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int)
    parser.add_argument("--write", action="store_true", help="replace production Activity after validation")
    arguments = parser.parse_args()
    update_activity_data(arguments.year, arguments.write)
