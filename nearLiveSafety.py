"""Explicit bounded reconciliation; no network or file writes."""
from __future__ import annotations

import pandas as pd

from dataUpdateSafety import DataValidationError, require_csv_schema

RECONCILE_PERIODS = 7


def refresh_start(stored, available, first=1, window=RECONCILE_PERIODS):
    """Include missing periods after an outage, plus the recent correction window."""
    return max(first, min(stored + 1, available - window + 1))


def replace_partitions(existing, fetched, partitions, period_column, key, validator):
    """Replace only enumerated (season, period) partitions, including deletions."""
    require_csv_schema(existing, fetched, f'{period_column} partition refresh')
    authorized = set(partitions)
    identities = list(zip(fetched['Year'].astype(int), fetched[period_column].astype(int)))
    if not set(identities).issubset(authorized):
        raise DataValidationError('refresh contains records outside authorized partitions')
    mask = pd.Series([(int(y), int(p)) in authorized for y, p in
                      zip(existing['Year'], existing[period_column])], index=existing.index)
    # Preserve saved eligibility for existing historical logical records. ESPN
    # returns current eligibility even when reading an old box score.
    fetched = fetched.copy()
    positions = [c for c in ('Position', 'Position2', 'Position3', 'Team Name', 'Team Abbreviation',
        'Team Owner', 'Opponent Team Name', 'Opponent Owner') if c in fetched]
    old = existing.set_index(key)
    for index, row in fetched.iterrows():
        identity = tuple(row[c] for c in key)
        if identity in old.index:
            for column in positions:
                fetched.at[index, column] = old.loc[identity, column]
            if 'Type' in fetched and old.loc[identity, 'Type'] != 'Regular':
                # The legacy append path re-ranks its prefix while calculating
                # a new week. That is not an ESPN correction to playoff places.
                if all(fetched.at[index, c] == old.loc[identity, c] for c in ('Win', 'Loss')):
                    fetched.at[index, 'Rank'] = old.loc[identity, 'Rank']
    for column, dtype in existing.dtypes.items():
        if pd.api.types.is_integer_dtype(dtype):
            values = pd.to_numeric(fetched[column], errors='raise')
            if values.isna().any() or (values % 1 != 0).any():
                raise DataValidationError(f'non-integer refresh value for {column}')
            fetched[column] = values.astype(dtype)
    candidate = pd.concat([existing.loc[~mask], fetched], ignore_index=True)
    validator(candidate)
    pd.testing.assert_frame_equal(candidate.iloc[:sum(~mask)].reset_index(drop=True),
                                  existing.loc[~mask].reset_index(drop=True), check_dtype=False)
    if not any(changes(existing, candidate, key).values()):
        return existing.copy(deep=True)
    return candidate


def changes(existing, candidate, key):
    """Report logical insertions, removals, and changed records without secrets."""
    before, after = existing.set_index(key), candidate.set_index(key)
    shared = before.index.intersection(after.index)
    # Numeric CSV serialization may differ (1 vs 1.0); compare dataframes first.
    equal = before.loc[shared].eq(after.loc[shared]) | (before.loc[shared].isna() & after.loc[shared].isna())
    return {'inserted': len(after.index.difference(before.index)),
            'removed': len(before.index.difference(after.index)),
            'corrected': int((~equal.all(axis=1)).sum())}


def change_details(existing, candidate, key):
    """Identify corrected/deleted keys and fields, without exposing request data."""
    before, after = existing.set_index(key), candidate.set_index(key)
    shared = before.index.intersection(after.index)
    equal = before.loc[shared].eq(after.loc[shared]) | (before.loc[shared].isna() & after.loc[shared].isna())
    return {'removedKeys': [list(k) for k in before.index.difference(after.index).tolist()],
            'corrected': [{'key': list(k), 'fields': equal.columns[~equal.loc[k]].tolist()}
                          for k in equal.index[~equal.all(axis=1)]]}
