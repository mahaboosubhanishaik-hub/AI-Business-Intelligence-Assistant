import os
from datetime import date

import pandas as pd

from app.services.data_loader import load_dataset


UPLOAD_FOLDER = os.path.abspath(os.path.join(os.getcwd(), "uploads"))


def load_business_dataset(dataset):
    filename = os.path.basename(dataset.filename)
    filepath = os.path.abspath(os.path.join(UPLOAD_FOLDER, filename))
    if os.path.commonpath((UPLOAD_FOLDER, filepath)) != UPLOAD_FOLDER:
        raise ValueError("The dataset file path is invalid.")
    if not os.path.isfile(filepath):
        raise FileNotFoundError("The dataset file is unavailable.")
    frame = load_dataset(filepath)
    frame.columns = frame.columns.map(str)
    return frame


def numeric_columns(frame):
    return [
        str(column)
        for column in frame.columns
        if pd.to_numeric(frame[column], errors="coerce").notna().any()
    ]


def categorical_values(frame, column, limit=500):
    if column not in frame.columns:
        return []
    values = (
        frame[column]
        .dropna()
        .astype(str)
        .str.strip()
    )
    return sorted(value for value in values.unique() if value)[:limit]


def aggregate_month(
    frame,
    period_start: date,
    date_column: str,
    value_column: str,
    group_column: str = "",
    group_value: str = ""
):
    _validate_columns(frame, date_column, value_column, group_column)
    parsed_dates = pd.to_datetime(
        frame[date_column],
        errors="coerce",
        format="mixed"
    )
    if not parsed_dates.notna().any():
        raise ValueError("The selected date column contains no valid dates.")
    values = pd.to_numeric(frame[value_column], errors="coerce")
    start = pd.Timestamp(period_start)
    end = start + pd.offsets.MonthBegin(1)
    mask = parsed_dates.ge(start) & parsed_dates.lt(end)

    if group_column:
        groups = frame[group_column].astype("string").str.strip()
        mask &= groups.eq(group_value)

    matched_rows = int(mask.sum())
    if matched_rows == 0:
        return None, 0

    matched_values = values[mask].dropna()
    if matched_values.empty:
        raise ValueError("The selected period has no valid numeric actual values.")
    return float(matched_values.sum()), int(matched_values.count())


def compare_values(
    frame,
    value_column: str,
    group_column: str = "",
    date_column: str = ""
):
    if value_column not in frame.columns:
        raise ValueError("Choose a valid numeric value column.")
    if group_column and group_column not in frame.columns:
        raise ValueError("Choose a valid comparison column.")
    if date_column and date_column not in frame.columns:
        raise ValueError("Choose a valid date column.")
    if not group_column and not date_column:
        raise ValueError("Choose a group column, a date column, or both.")
    if value_column in (group_column, date_column):
        raise ValueError("The value column must be different from comparison columns.")
    if group_column and group_column == date_column:
        raise ValueError("Choose different columns for grouping and dates.")

    values = pd.to_numeric(frame[value_column], errors="coerce")
    valid = values.notna()
    comparison = pd.DataFrame({"value": values[valid]})
    dimensions = []

    if group_column:
        groups = frame.loc[valid, group_column].fillna("Unknown").astype(str).str.strip()
        comparison["group"] = groups.where(groups != "", "Unknown")
        dimensions.append("group")
    if date_column:
        parsed_dates = pd.to_datetime(
            frame.loc[valid, date_column],
            errors="coerce",
            format="mixed"
        )
        comparison["period"] = parsed_dates.dt.to_period("M").astype(str)
        comparison = comparison[comparison["period"] != "NaT"]
        dimensions.append("period")

    if comparison.empty:
        raise ValueError("No rows have valid values for the selected columns.")

    grouped = (
        comparison.groupby(dimensions, dropna=False)
        .agg(actual=("value", "sum"), records=("value", "count"))
        .reset_index()
        .sort_values(dimensions)
    )
    return grouped.to_dict(orient="records"), dimensions


def _validate_columns(frame, date_column, value_column, group_column):
    if date_column not in frame.columns:
        raise ValueError("Choose a valid date column.")
    if value_column not in frame.columns:
        raise ValueError("Choose a valid numeric value column.")
    if date_column == value_column:
        raise ValueError("The date and value columns must be different.")
    if group_column:
        if group_column not in frame.columns:
            raise ValueError("Choose a valid group column.")
        if group_column in (date_column, value_column):
            raise ValueError("The group column must be different from date and value columns.")
