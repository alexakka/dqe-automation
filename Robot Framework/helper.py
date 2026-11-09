import re
from pathlib import Path
import pandas as pd


def _normalize_columns(df):
    """'Facility Type' and 'facility_type' both become 'facility_type'."""
    df.columns = [re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_") for c in df.columns]
    return df


def read_html_table(table_element):
    """Read the (Plotly) table that was located by SeleniumLibrary into a DataFrame.

    The table scrolls and only some rows exist in the page, so the full data
    is taken from the Plotly chart that contains the located table element.
    """
    driver = table_element.parent
    data = driver.execute_script(
        "var plot = arguments[0].closest('.js-plotly-plot');"
        "var t = plot.data.find(function(d) { return d.type === 'table'; });"
        "return {headers: t.header.values, columns: t.cells.values};",
        table_element,
    )
    df = pd.DataFrame(list(zip(*data["columns"])), columns=data["headers"])
    return _normalize_columns(df)


def _read_parquet_files(folder):
    """Read every .parquet file separately (files may have different columns)
    and add hive partition values from the folder names (key=value)."""
    frames = []
    for path in sorted(Path(folder).rglob("*.parquet")):
        part = pd.read_parquet(path)
        for folder_name in path.relative_to(folder).parts[:-1]:
            if "=" in folder_name:
                key, value = folder_name.split("=", 1)
                if key not in part.columns:
                    part[key] = value
        frames.append(part)
    return pd.concat(frames, ignore_index=True)


def read_parquet_data(folder, filter_date=None, date_column="visit_date"):
    """Read the partitioned Parquet dataset (facility type average time per visit date)
    and shape it like the report table.
    If filter_date (YYYY-MM-DD) is given, keep only rows with date_column >= filter_date."""
    df = _normalize_columns(_read_parquet_files(folder))
    df[date_column] = pd.to_datetime(df[date_column]).dt.strftime("%Y-%m-%d")
    if filter_date:
        df = df[df[date_column] >= str(filter_date)]

    # facility type can be a normal column or a partition folder name
    type_columns = [c for c in df.columns if c.startswith("facility_type")]
    facility_type = df[type_columns[0]].astype(object)
    for column in type_columns[1:]:
        facility_type = facility_type.fillna(df[column].astype(object))
    df["facility_type"] = facility_type.astype(str).str.replace("_", " ")

    # the average column (for example avg_time_spent) is renamed to match the report
    avg_columns = [c for c in df.columns if "avg" in c or "average" in c]
    if not avg_columns:
        raise AssertionError(f"No average time column found in Parquet. Columns: {list(df.columns)}")
    df["average_time_spent"] = df[avg_columns[0]].astype(float).round(2)

    return df[["facility_type", "visit_date", "average_time_spent"]]


def compare_dataframes(df_html, df_parquet):
    """Compare two DataFrames for an exact match (row order is ignored).

    Returns a DataFrame with the differing rows (empty if they match).
    The 'source' column says where the row exists: html_only / parquet_only.
    """
    columns = list(df_html.columns)
    missing = set(columns) ^ set(df_parquet.columns)
    if missing:
        raise AssertionError(f"Column mismatch: {sorted(missing)}. "
                             f"HTML={columns}, Parquet={list(df_parquet.columns)}")

    left = df_html[columns].astype(str).drop_duplicates()
    right = df_parquet[columns].astype(str).drop_duplicates()
    merged = left.merge(right, on=columns, how="outer", indicator="source")
    diff = merged[merged["source"] != "both"].copy()
    diff["source"] = diff["source"].map({"left_only": "html_only", "right_only": "parquet_only"})
    return diff.sort_values(columns).reset_index(drop=True)