import re

import pandas as pd
import pytest

EMAIL_PATTERN = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def test_file_not_empty(csv_data):
    assert not csv_data.empty, "CSV file is empty: expected at least one data row"


@pytest.mark.validate_csv
def test_validate_schema(validate_schema, actual_schema, expected_schema):
    assert not validate_schema, (
        f"Schema mismatch ({'; '.join(validate_schema)}). "
        f"Expected {expected_schema}, got {actual_schema}"
    )


@pytest.mark.validate_csv
@pytest.mark.skip(reason="Age validation is temporarily disabled")
def test_age_column_valid(csv_data):
    ages = pd.to_numeric(csv_data["age"], errors="coerce")
    invalid = csv_data[~ages.between(0, 100)]
    assert invalid.empty, (
        f"Age must be a number between 0 and 100. Invalid rows:\n"
        f"{invalid[['id', 'age']].to_string(index=False)}"
    )


@pytest.mark.validate_csv
def test_email_column_valid(csv_data):
    valid = csv_data["email"].astype(str).str.match(EMAIL_PATTERN)
    invalid = csv_data[~valid]
    assert invalid.empty, (
        f"Invalid email format found for (id, email): "
        f"{list(zip(invalid['id'], invalid['email']))}"
    )


@pytest.mark.validate_csv
@pytest.mark.xfail(reason="Known issue: data.csv contains a duplicated row (id=4)")
def test_duplicates(csv_data):
    duplicates = csv_data[csv_data.duplicated(keep="first")]
    assert duplicates.empty, f"Duplicate rows found for ids: {list(duplicates['id'])}"


def _is_active(csv_data, player_id):
    rows = csv_data.loc[csv_data["id"] == player_id, "is_active"]
    assert not rows.empty, f"No row with id={player_id} found in CSV"
    return bool(rows.iloc[0])


@pytest.mark.parametrize("id, is_active", [(1, False), (2, True)])
def test_active_players(csv_data, id, is_active):
    actual = _is_active(csv_data, id)
    assert actual is is_active, (
        f"Expected is_active={is_active} for id={id}, got {actual}"
    )


def test_active_player(csv_data):
    actual = _is_active(csv_data, 2)
    assert actual is True, f"Expected is_active=True for id=2, got {actual}"