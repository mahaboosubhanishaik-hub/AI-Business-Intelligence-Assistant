import pandas as pd
import numpy as np


def format_bytes(size_in_bytes):
    """Format bytes into human readable string."""
    if not size_in_bytes:
        return "0 B"
    size = float(size_in_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def detect_column_type(series):
    """
    Intelligently detect the high-level data type of a Pandas series:
    Returns one of: 'integer', 'float', 'boolean', 'datetime', 'string'.
    """
    dtype = series.dtype

    if pd.api.types.is_bool_dtype(dtype):
        return "boolean"

    if pd.api.types.is_integer_dtype(dtype):
        return "integer"

    if pd.api.types.is_float_dtype(dtype):
        return "float"

    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "datetime"

    # For object/string columns, test for datetime or numeric conversion
    non_null_series = series.dropna()
    if non_null_series.empty:
        return "string"

    # Sample up to 100 non-null values for fast conversion test
    sample = non_null_series.head(100).astype(str).str.strip()

    # Test numeric conversion
    try:
        numeric_converted = pd.to_numeric(sample, errors="raise")
        if (numeric_converted % 1 == 0).all():
            return "integer"
        return "float"
    except (ValueError, TypeError):
        pass

    # Test datetime conversion
    try:
        dt_converted = pd.to_datetime(sample, errors="coerce", format="mixed")
        valid_ratio = dt_converted.notnull().mean()
        if valid_ratio >= 0.8:
            return "datetime"
    except (ValueError, TypeError, Exception):
        pass

    return "string"


def profile_dataset(df):
    """
    Generate comprehensive dataset-level and column-level profiling metrics.
    """
    total_rows = int(df.shape[0])
    total_columns = int(df.shape[1])
    total_cells = total_rows * total_columns

    # Dataset-level memory usage
    memory_bytes = int(df.memory_usage(deep=True).sum())
    memory_human = format_bytes(memory_bytes)

    # Missing & Duplicate calculations
    missing_values = int(df.isnull().sum().sum())
    missing_percentage = round((missing_values / total_cells * 100), 2) if total_cells > 0 else 0.0

    duplicate_rows = int(df.duplicated().sum())
    duplicate_percentage = round((duplicate_rows / total_rows * 100), 2) if total_rows > 0 else 0.0

    column_information = []
    numeric_count = 0
    categorical_count = 0
    datetime_count = 0

    for col_name in df.columns:
        series = df[col_name]
        col_type = detect_column_type(series)

        non_null_cnt = int(series.count())
        missing_cnt = int(series.isnull().sum())
        missing_pct = round((missing_cnt / total_rows * 100), 2) if total_rows > 0 else 0.0

        unique_cnt = int(series.nunique(dropna=True))
        unique_pct = round((unique_cnt / total_rows * 100), 2) if total_rows > 0 else 0.0

        col_meta = {
            "name": str(col_name),
            "detected_type": col_type,
            "non_null_count": non_null_cnt,
            "missing_count": missing_cnt,
            "missing_percentage": missing_pct,
            "unique_count": unique_cnt,
            "unique_percentage": unique_pct,
            # Placeholders for type-specific stats
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "std_dev": None,
            "top_value": None,
            "top_frequency": None,
            "min_date": None,
            "max_date": None
        }

        if col_type in {"integer", "float"}:
            numeric_count += 1
            num_series = pd.to_numeric(series, errors="coerce").dropna()
            if not num_series.empty:
                col_meta["min"] = round(float(num_series.min()), 2)
                col_meta["max"] = round(float(num_series.max()), 2)
                col_meta["mean"] = round(float(num_series.mean()), 2)
                col_meta["median"] = round(float(num_series.median()), 2)
                col_meta["std_dev"] = round(float(num_series.std()), 2) if len(num_series) > 1 else 0.0

        elif col_type == "datetime":
            datetime_count += 1
            dt_series = pd.to_datetime(series, errors="coerce", format="mixed").dropna()
            if not dt_series.empty:
                col_meta["min_date"] = dt_series.min().strftime("%Y-%m-%d")
                col_meta["max_date"] = dt_series.max().strftime("%Y-%m-%d")

        else:
            categorical_count += 1
            str_series = series.dropna().astype(str).str.strip()
            if not str_series.empty:
                val_counts = str_series.value_counts()
                col_meta["top_value"] = str(val_counts.index[0])
                col_meta["top_frequency"] = int(val_counts.iloc[0])

        column_information.append(col_meta)

    return {
        "rows": total_rows,
        "columns": total_columns,
        "memory_bytes": memory_bytes,
        "memory_human": memory_human,
        "missing_values": missing_values,
        "missing_percentage": missing_percentage,
        "duplicate_rows": duplicate_rows,
        "duplicate_percentage": duplicate_percentage,
        "numeric_columns_count": numeric_count,
        "categorical_columns_count": categorical_count,
        "datetime_columns_count": datetime_count,
        "column_information": column_information
    }