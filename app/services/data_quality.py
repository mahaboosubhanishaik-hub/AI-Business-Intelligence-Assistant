import pandas as pd
import numpy as np


# Recognized business columns that should typically be non-negative
BUSINESS_MEASURE_COLUMNS = {
    "revenue", "sales", "total_sales", "sales_amount", "amount",
    "income", "profit", "units", "units_sold", "quantity", "qty", "price"
}


def get_quality_status(score):
    """
    Centralized status mapping based on quality score (0 - 100%).
    """
    if score >= 90.0:
        return {"status": "Excellent", "badge_class": "bg-success", "alert_class": "alert-success"}
    elif score >= 75.0:
        return {"status": "Good", "badge_class": "bg-primary", "alert_class": "alert-primary"}
    elif score >= 50.0:
        return {"status": "Needs Attention", "badge_class": "bg-warning text-dark", "alert_class": "alert-warning"}
    else:
        return {"status": "Poor", "badge_class": "bg-danger", "alert_class": "alert-danger"}


def evaluate_data_quality(df):
    """
    Evaluate dataset quality across 4 core dimensions:
    1. Completeness (weight 30%)
    2. Uniqueness (weight 25%)
    3. Validity (weight 25%)
    4. Consistency / Outliers (weight 20%)

    Returns structured report dictionary.
    """
    if df is None or df.empty:
        return {
            "score": 0.0,
            "status": "Poor",
            "status_info": get_quality_status(0.0),
            "dimensions": {
                "completeness": 0.0,
                "uniqueness": 0.0,
                "validity": 0.0,
                "consistency": 0.0
            },
            "summary": {
                "total_rows": 0,
                "total_columns": 0,
                "missing_values": 0,
                "duplicate_rows": 0,
                "suspicious_values": 0,
                "outliers_count": 0
            },
            "issues": [],
            "column_quality": []
        }

    total_rows = int(df.shape[0])
    total_columns = int(df.shape[1])
    total_cells = total_rows * total_columns

    issues = []
    column_quality = []

    # ==========================================
    # 1. COMPLETENESS (Weight 30%)
    # ==========================================
    missing_values = int(df.isnull().sum().sum())
    non_missing_cells = total_cells - missing_values
    completeness_score = round((non_missing_cells / total_cells * 100.0), 1) if total_cells > 0 else 0.0

    if missing_values > 0:
        missing_pct = round((missing_values / total_cells * 100.0), 1)
        severity = "CRITICAL" if missing_pct > 30.0 else "WARNING"
        issues.append({
            "column": "Dataset Overview",
            "issue_type": "Missing Values",
            "severity": severity,
            "count": missing_values,
            "percentage": missing_pct,
            "message": f"Dataset contains {missing_values:,} missing values ({missing_pct}% of total cells)."
        })

    # ==========================================
    # 2. UNIQUENESS (Weight 25%)
    # ==========================================
    duplicate_rows = int(df.duplicated().sum())
    unique_rows = total_rows - duplicate_rows
    uniqueness_score = round((unique_rows / total_rows * 100.0), 1) if total_rows > 0 else 0.0

    if duplicate_rows > 0:
        dup_pct = round((duplicate_rows / total_rows * 100.0), 1)
        severity = "CRITICAL" if dup_pct > 20.0 else "WARNING"
        issues.append({
            "column": "Dataset Overview",
            "issue_type": "Duplicate Rows",
            "severity": severity,
            "count": duplicate_rows,
            "percentage": dup_pct,
            "message": f"Dataset contains {duplicate_rows:,} completely duplicated rows ({dup_pct}% of rows)."
        })

    # ==========================================
    # 3. VALIDITY & 4. CONSISTENCY (Per Column Analysis)
    # ==========================================
    total_invalid_cells = 0
    total_outliers_count = 0

    for col in df.columns:
        series = df[col]
        col_missing = int(series.isnull().sum())
        col_missing_pct = round((col_missing / total_rows * 100.0), 1) if total_rows > 0 else 0.0

        col_invalid_count = 0
        col_outlier_count = 0

        # Check empty or whitespace-only strings for non-numeric, non-datetime columns
        if not pd.api.types.is_numeric_dtype(series.dtype) and not pd.api.types.is_datetime64_any_dtype(series.dtype) and not pd.api.types.is_bool_dtype(series.dtype):
            str_series = series.dropna().astype(str)
            empty_str_count = int((str_series.str.strip() == "").sum())
            if empty_str_count > 0:
                col_invalid_count += empty_str_count
                issues.append({
                    "column": str(col),
                    "issue_type": "Empty Strings",
                    "severity": "WARNING",
                    "count": empty_str_count,
                    "percentage": round((empty_str_count / total_rows * 100.0), 1),
                    "message": f"Column '{col}' contains {empty_str_count:,} empty or whitespace-only values."
                })

        # Check negative values in business measure columns
        col_clean_name = str(col).strip().lower().replace(" ", "_")
        if col_clean_name in BUSINESS_MEASURE_COLUMNS or any(bm in col_clean_name for bm in ["revenue", "sales", "amount", "qty"]):
            num_series = pd.to_numeric(series, errors="coerce")
            negative_count = int((num_series < 0).sum())
            if negative_count > 0:
                col_invalid_count += negative_count
                issues.append({
                    "column": str(col),
                    "issue_type": "Suspicious Negative Values",
                    "severity": "WARNING",
                    "count": negative_count,
                    "percentage": round((negative_count / total_rows * 100.0), 1),
                    "message": f"Column '{col}' contains {negative_count:,} potential suspicious negative values."
                })

        # Check numerical outliers using IQR method
        if pd.api.types.is_numeric_dtype(series.dtype):
            clean_num = series.dropna()
            if len(clean_num) >= 4:
                q1 = float(clean_num.quantile(0.25))
                q3 = float(clean_num.quantile(0.75))
                iqr = q3 - q1
                if iqr > 0:
                    lower_bound = q1 - 1.5 * iqr
                    upper_bound = q3 + 1.5 * iqr
                    outliers_mask = (clean_num < lower_bound) | (clean_num > upper_bound)
                    col_outlier_count = int(outliers_mask.sum())

                    if col_outlier_count > 0:
                        outlier_pct = round((col_outlier_count / total_rows * 100.0), 1)
                        issues.append({
                            "column": str(col),
                            "issue_type": "Outliers (IQR)",
                            "severity": "INFO",
                            "count": col_outlier_count,
                            "percentage": outlier_pct,
                            "message": f"Column '{col}' contains {col_outlier_count:,} potential statistical outliers (bounds: [{lower_bound:.2f}, {upper_bound:.2f}])."
                        })

        total_invalid_cells += col_invalid_count
        total_outliers_count += col_outlier_count

        # Column Quality Status
        col_status = "Good"
        col_status_class = "bg-success"

        if col_missing_pct > 30.0 or col_invalid_count > (total_rows * 0.15):
            col_status = "Critical"
            col_status_class = "bg-danger"
        elif col_missing_pct > 0.0 or col_invalid_count > 0 or col_outlier_count > (total_rows * 0.05):
            col_status = "Warning"
            col_status_class = "bg-warning text-dark"

        column_quality.append({
            "column": str(col),
            "completeness_pct": round(100.0 - col_missing_pct, 1),
            "missing_count": col_missing,
            "missing_percentage": col_missing_pct,
            "suspicious_count": col_invalid_count,
            "outlier_count": col_outlier_count,
            "status": col_status,
            "status_class": col_status_class
        })

    # Calculate Validity Score (25% weight)
    valid_cells = max(0, total_cells - total_invalid_cells)
    validity_score = round((valid_cells / total_cells * 100.0), 1) if total_cells > 0 else 0.0

    # Calculate Consistency Score (20% weight)
    consistent_cells = max(0, total_cells - total_outliers_count)
    consistency_score = round((consistent_cells / total_cells * 100.0), 1) if total_cells > 0 else 0.0

    # ==========================================
    # OVERALL QUALITY SCORE & STATUS
    # ==========================================
    overall_score = round(
        (completeness_score * 0.30) +
        (uniqueness_score * 0.25) +
        (validity_score * 0.25) +
        (consistency_score * 0.20),
        1
    )
    overall_score = max(0.0, min(100.0, overall_score))

    status_info = get_quality_status(overall_score)

    return {
        "score": overall_score,
        "status": status_info["status"],
        "status_info": status_info,
        "dimensions": {
            "completeness": completeness_score,
            "uniqueness": uniqueness_score,
            "validity": validity_score,
            "consistency": consistency_score
        },
        "summary": {
            "total_rows": total_rows,
            "total_columns": total_columns,
            "missing_values": missing_values,
            "duplicate_rows": duplicate_rows,
            "suspicious_values": total_invalid_cells,
            "outliers_count": total_outliers_count
        },
        "issues": issues,
        "column_quality": column_quality
    }
