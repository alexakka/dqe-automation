---
name: generate-parquet-dq-tests
description: >-
  Creates one parquet_files PyTest DQ module per dataset (smoke, completeness, count, uniqueness,
  not-null) from docs/parquet-aggregated-data-mapping.md. Invoke by name for one dataset at a time;
  refuses to edit framework/Jenkins/conftest or to take SQL from data_dev.
disable-model-invocation: true
---

# Generate Parquet DQ tests

Read first: `PyTest DQ Framework/docs/test-automation-strategy.md`,
`docs/parquet-aggregated-data-mapping.md` (the dataset definition), `docs/project-environment.md` (3NF tables and keys).
This skill is dataset-agnostic: it holds no expected SQL for any named dataset.

## When to use

The user names this skill and a dataset. The framework already exists (`src/`, `tests/conftest.py` with
`db_connection`, `parquet_reader`, `data_quality_library`; markers in `tests/pytest.ini`).

Only output: `PyTest DQ Framework/tests/dq checks/parquet_files/test_<dataset_name>.py`.

Refuse (one sentence why) if asked to edit `src/`, `conftest.py`, `pytest.ini`, `requirements.txt` or
`Jenkinsfile`; put several datasets in one file; or make a failing run green by changing expected SQL.

## Inputs

- Dataset name (snake_case, same as the mapping heading) and its mapping section: target columns,
  transformation, source column, comments (`grouping`, `not null`, rounding, format), filters.
- Requirement id and author for the header; if not given, use `git config user.name` and a marked placeholder id, and say so.
- If the mapping section is missing or incomplete, **stop and ask**. Never guess.
- **Never use** `data_dev/` (queries, parquet loader), existing parquet files, earlier test output or other tests as a source for SQL.

## Rules

1. **Source = Postgres** (`db_connection`) is the expected result; **target = Parquet** (`parquet_reader`) is the actual one. Never swap them or compare the target with itself.
2. **Mapping-only SQL.** Only tables, joins, dimensions, measures, rounding and filters stated in the mapping. No extra `WHERE`, `UNION`, `CASE`, `DISTINCT`, `COALESCE` or sign changes.
3. Output column aliases equal the mapping's target column names; the mapping wins over any other summary.
4. `target_path = '/parquet_data/<dataset_name>'`, read with `include_subfolders=True`.
5. Tests only call `DataQualityLibrary` methods: no pandas logic, no bare `assert`.
6. All five tests, with these names: `test_check_dataset_is_not_empty`, `test_check_data_completeness`, `test_check_count`, `test_check_uniqueness`, `test_check_not_null_values`.
7. Markers on every test: `parquet_data` and `<dataset_name>`; `smoke` only on the not-empty test.
8. Uniqueness is checked on the **grain** (columns the mapping marks `grouping`); not-null on **all mapped output columns**.
9. Fixtures `source_data` and `target_data` have `scope='module'`.

## Workflow

1. Read the mapping section; note grain, measures (aggregate, rounding), source tables, join keys, filters (usually none).
2. Write the expected SQL (see below), then fill the template.
3. Check the file against the rules; report the file, grain, measures and any ambiguity you resolved
   (for example a table spelled differently in the ER diagram and the mapping).

## Template

```python
"""
Description: Data Quality checks for <dataset_name> dataset.
Requirement(s): <TICKET-ID>
Author(s): <name>
"""

import pytest


@pytest.fixture(scope='module')
def source_data(db_connection):
    source_query = """
    -- expected query derived from mapping (grain + measures + joins)
    """
    return db_connection.get_data_sql(source_query)


@pytest.fixture(scope='module')
def target_data(parquet_reader):
    target_path = '/parquet_data/<dataset_name>'
    return parquet_reader.process(target_path, include_subfolders=True)


@pytest.mark.parquet_data
@pytest.mark.smoke
@pytest.mark.<dataset_name>
def test_check_dataset_is_not_empty(target_data, data_quality_library):
    data_quality_library.check_dataset_is_not_empty(target_data)


@pytest.mark.parquet_data
@pytest.mark.<dataset_name>
def test_check_data_completeness(source_data, target_data, data_quality_library):
    data_quality_library.check_data_completeness(source_data, target_data)


@pytest.mark.parquet_data
@pytest.mark.<dataset_name>
def test_check_count(source_data, target_data, data_quality_library):
    data_quality_library.check_count(source_data, target_data)


@pytest.mark.parquet_data
@pytest.mark.<dataset_name>
def test_check_uniqueness(target_data, data_quality_library):
    data_quality_library.check_duplicates(target_data, ['<grouping_col_1>', '<grouping_col_2>'])


@pytest.mark.parquet_data
@pytest.mark.<dataset_name>
def test_check_not_null_values(target_data, data_quality_library):
    data_quality_library.check_not_null_values(target_data, ['<col_1>', '<col_2>', '<col_3>'])
```

Do not copy fixture names or direction from `tests/test_examples.py`; follow this template.

## SQL derivation (generic)

1. **Joins:** join `visits` to each dimension table on `visits.<dimension>_id = <dimension>.id` (inner join) for the tables the mapping's `Source` column names.
2. **Dimensions:** every `grouping` column is selected and listed in `GROUP BY`. A date derived from a timestamp is its date part (cast to `date`); partitioning notes describe storage, not the value.
3. **Computed values:** build them exactly as the mapping's format comment says and repeat the expression in `GROUP BY`.
4. **Measures:** apply the mapping's aggregate; apply the stated rounding (cast to `numeric` first if needed).
5. **Filters:** none unless the mapping states one.
6. **Stop.** Do not adjust the query to match parquet, a failed run or the ETL. Rules like "not null" or "can't be negative" are verified by tests, not added to the SQL.

## After generation

Run pytest only if asked. If a test fails, report it as a mapping-versus-parquet finding (dataset, test, expected, actual, suspected transformation cause). Never edit expected SQL, markers or the library to make a run green.
