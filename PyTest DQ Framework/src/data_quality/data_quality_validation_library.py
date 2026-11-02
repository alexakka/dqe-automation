"""Reusable data quality checks on pandas DataFrames."""

import datetime
import decimal

import pandas as pd

_NULL = "<NULL>"
_SAMPLE_ROWS = 10


def _fail(message: str):
    raise AssertionError(message)


def _sample(df: pd.DataFrame) -> str:
    return df.head(_SAMPLE_ROWS).to_string(index=False)


def _canonical_column(series: pd.Series) -> pd.Series:
    """
    Turn a column into comparable strings so that the same business value read from
    Postgres (Decimal, date) and from Parquet (float, timestamp, category, string)
    compares equal, while real differences (value, rounding beyond 6 dp, extra time part) do not.
    """
    if isinstance(series.dtype, pd.CategoricalDtype):
        series = series.astype(object)

    if pd.api.types.is_bool_dtype(series):
        return series.map(lambda v: _NULL if pd.isna(v) else str(bool(v)))

    if pd.api.types.is_datetime64_any_dtype(series):
        return _canonical_datetimes(pd.to_datetime(series))

    if pd.api.types.is_numeric_dtype(series):
        return series.astype("float64").map(_format_number)

    non_null = series.dropna()
    if len(non_null) and all(isinstance(v, (datetime.date, datetime.datetime, pd.Timestamp)) for v in non_null):
        return _canonical_datetimes(pd.to_datetime(series))
    if len(non_null) and all(isinstance(v, (decimal.Decimal, int, float)) and not isinstance(v, bool)
                             for v in non_null):
        return series.map(lambda v: _NULL if pd.isna(v) else _format_number(float(v)))

    return series.map(lambda v: _NULL if pd.isna(v) else str(v))


def _format_number(value) -> str:
    if pd.isna(value):
        return _NULL
    return f"{round(float(value), 6) + 0.0:.6f}"  # "+ 0.0" turns -0.0 into 0.0


def _canonical_datetimes(series: pd.Series) -> pd.Series:
    if getattr(series.dt, "tz", None) is not None:
        series = series.dt.tz_convert("UTC").dt.tz_localize(None)
    valid = series.dropna()
    date_only = len(valid) > 0 and bool((valid == valid.dt.normalize()).all())
    fmt = "%Y-%m-%d" if date_only else "%Y-%m-%d %H:%M:%S.%f"
    return series.map(lambda v: _NULL if pd.isna(v) else v.strftime(fmt))


def _canonical_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({col: _canonical_column(df[col]) for col in df.columns})
    return out[sorted(out.columns)]


class DataQualityLibrary:
    """
    Reusable data quality checks.

    Every method raises ``AssertionError`` with a message that is meant to be read in the HTML
    report: counts, column names and sample rows. Tests call these methods and must not
    re-implement the comparison logic.
    """

    @staticmethod
    def check_dataset_is_not_empty(df):
        """Target dataset exists and has at least one row."""
        if df is None:
            _fail("Dataset is None: nothing was loaded.")
        if len(df) == 0:
            _fail(f"Dataset is empty (0 rows). Columns: {list(df.columns)}")

    @staticmethod
    def check_count(df_expected, df_actual):
        """Both datasets have the same number of rows."""
        expected_count, actual_count = len(df_expected), len(df_actual)
        if expected_count != actual_count:
            _fail(f"Row count mismatch: expected (source) = {expected_count}, "
                  f"actual (target) = {actual_count}, difference = {actual_count - expected_count:+d}")

    @staticmethod
    def check_data_completeness(df_expected, df_actual):
        """
        Both datasets contain the same rows (row order ignored, duplicates counted).
        Reports column differences first, then rows missing from / unexpected in the actual data.
        """
        expected_cols, actual_cols = set(df_expected.columns), set(df_actual.columns)
        if expected_cols != actual_cols:
            _fail("Column mismatch between expected (source) and actual (target) data: "
                  f"missing in actual = {sorted(expected_cols - actual_cols)}, "
                  f"unexpected in actual = {sorted(actual_cols - expected_cols)}")

        expected = _canonical_frame(df_expected)
        actual = _canonical_frame(df_actual)
        columns = list(expected.columns)
        occurrence = "__occurrence__"
        expected[occurrence] = expected.groupby(columns).cumcount()
        actual[occurrence] = actual.groupby(columns).cumcount()

        merged = expected.merge(actual, on=columns + [occurrence], how="outer", indicator=True)
        missing = merged[merged["_merge"] == "left_only"][columns]
        unexpected = merged[merged["_merge"] == "right_only"][columns]

        if len(missing) or len(unexpected):
            parts = [f"Data mismatch: {len(missing)} expected row(s) missing in actual, "
                     f"{len(unexpected)} unexpected row(s) in actual "
                     f"(expected rows = {len(expected)}, actual rows = {len(actual)})."]
            if len(missing):
                parts.append(f"Rows missing in actual (first {_SAMPLE_ROWS}):\n{_sample(missing)}")
            if len(unexpected):
                parts.append(f"Unexpected rows in actual (first {_SAMPLE_ROWS}):\n{_sample(unexpected)}")
            _fail("\n".join(parts))

    @staticmethod
    def check_duplicates(df, column_names=None):
        """No duplicate rows; with ``column_names`` no duplicates of that column combination (the grain)."""
        if column_names is not None:
            column_names = list(column_names)
            absent = [c for c in column_names if c not in df.columns]
            if absent:
                _fail(f"Cannot check duplicates, columns not found: {absent}. Available: {list(df.columns)}")
        canonical = _canonical_frame(df)
        subset = column_names or None
        duplicated = canonical.duplicated(subset=subset, keep=False)
        if duplicated.any():
            rows = canonical[duplicated].sort_values(by=subset or list(canonical.columns))
            _fail(f"Found {int(duplicated.sum())} duplicated row(s) "
                  f"(key = {column_names or 'all columns'}); first {_SAMPLE_ROWS}:\n{_sample(rows)}")

    @staticmethod
    def check_not_null_values(df, column_names):
        """The named columns contain no nulls."""
        if not column_names:
            _fail("check_not_null_values needs a non-empty list of column names.")
        column_names = list(column_names)
        absent = [c for c in column_names if c not in df.columns]
        if absent:
            _fail(f"Columns not found in dataset: {absent}. Available: {list(df.columns)}")
        null_counts = {c: int(df[c].isna().sum()) for c in column_names}
        offenders = {c: n for c, n in null_counts.items() if n}
        if offenders:
            sample = df[df[list(offenders)].isna().any(axis=1)]
            _fail(f"Null values found (column: null count out of {len(df)} rows): {offenders}. "
                  f"First {_SAMPLE_ROWS} affected rows:\n{_sample(sample)}")
