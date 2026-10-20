import pandas as pd
import pytest
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "src" / "data" / "data.csv"
# print(DATA_FILE)

@pytest.fixture(scope="session")
def path_to_file():
    return DATA_FILE


# Fixture to read the CSV file
@pytest.fixture(scope="session")
def csv_data(path_to_file):
    return pd.read_csv(path_to_file)


@pytest.fixture(scope="session")
def actual_schema(csv_data):
    return list(csv_data.columns)


@pytest.fixture(scope="session")
def expected_schema():
    return ["id", "name", "age", "email", "is_active"]


# Fixture to validate the schema of the file
@pytest.fixture(scope="session")
def validate_schema(actual_schema, expected_schema):
    differences = []
    missing = [c for c in expected_schema if c not in actual_schema]
    unexpected = [c for c in actual_schema if c not in expected_schema]
    if missing:
        differences.append(f"missing columns: {missing}")
    if unexpected:
        differences.append(f"unexpected columns: {unexpected}")
    
    return differences


# Pytest hook to mark unmarked tests with a custom mark
def pytest_collection_modifyitems(items):
    for item in items:
        if not list(item.iter_markers()):
            item.add_marker(pytest.mark.unmarked)