"""Parquet reader used by the DQ framework."""

import os
from urllib.parse import unquote

import pandas as pd


class ParquetReader:
    """Reads a parquet file or a (partitioned) parquet dataset folder into one DataFrame."""

    @staticmethod
    def _is_data_file(name: str) -> bool:
        # skip hidden / bookkeeping files such as .crc, _SUCCESS, _metadata
        return name.endswith(".parquet") and not name.startswith((".", "_"))

    def _list_files(self, path: str, include_subfolders: bool):
        if include_subfolders:
            found = []
            for root, dirs, files in os.walk(path):
                dirs[:] = sorted(d for d in dirs if not d.startswith((".", "_")))
                found.extend(os.path.join(root, f) for f in sorted(files) if self._is_data_file(f))
            return found
        return [os.path.join(path, f) for f in sorted(os.listdir(path)) if self._is_data_file(f)
                and os.path.isfile(os.path.join(path, f))]

    @staticmethod
    def _partition_values(file_path: str, root: str) -> dict:
        """Hive-style ``key=value`` folders between ``root`` and the file."""
        relative = os.path.relpath(os.path.dirname(file_path), root)
        values = {}
        if relative != ".":
            for part in relative.split(os.sep):
                if "=" in part:
                    key, value = part.split("=", 1)
                    values[key] = unquote(value)
        return values

    def process(self, path: str, include_subfolders: bool = False,
                include_partition_columns: bool = False) -> pd.DataFrame:
        """
        Load parquet data from ``path``.

        :param path: parquet file or dataset folder (for example ``/parquet_data/<dataset>``)
        :param include_subfolders: also read partition sub-folders (``key=value/...``)
        :param include_partition_columns: also add ``key=value`` folder names as columns. Off by default:
                 partition folders are a storage layout detail (often helper keys such as a year-month),
                 not mapped dataset columns, so they must not show up as extra columns in comparisons.
        :return: DataFrame with all rows, with the columns stored in the files. A column stored
                 inside a file is never overwritten by a folder value.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Parquet path does not exist: {path}")

        if os.path.isfile(path):
            return pd.read_parquet(path)

        files = self._list_files(path, include_subfolders)
        if not files:
            raise FileNotFoundError(
                f"No parquet files found in {path} (include_subfolders={include_subfolders})")

        frames = []
        for file_path in files:
            frame = pd.read_parquet(file_path)
            if include_partition_columns:
                for key, value in self._partition_values(file_path, path).items():
                    if key not in frame.columns:
                        frame[key] = value
            frames.append(frame)
        return pd.concat(frames, ignore_index=True)
