import pandas as pd
import numpy as np


# ==========================================
# GENERATE ANALYTICS
# ==========================================

def generate_analytics(df):
    """
    Generate structured BI analytics, KPIs, multi-dimensional breakdowns,
    time-series trend data, generic numeric statistics, and business highlights.
    """
    result = {
        "total_rows": int(len(df)),
        "total_columns": int(len(df.columns)),
        "numeric_columns": [],
        "categorical_columns": [],
        "kpis": {},
        "charts": {
            "revenue_by_product": {},
            "revenue_by_region": {},
            "profit_by_product": {},
            "profit_by_region": {},
            "revenue_by_category": {},
            "revenue_trend": {}
        },
        "highlights": {},
        "insights": [],
        "column_stats": {}
    }

    if df is None or df.empty:
        return result

    # ======================================
    # IDENTIFY COLUMN TYPES
    # ======================================
    numeric_columns = df.select_dtypes(include="number").columns.tolist()
    categorical_columns = df.select_dtypes(include=["object", "category", "string"]).columns.tolist()

    result["numeric_columns"] = numeric_columns
    result["categorical_columns"] = categorical_columns

    # ======================================
    # GENERIC NUMERIC STATISTICS
    # ======================================
    for column in numeric_columns:
        series = pd.to_numeric(df[column], errors="coerce").dropna()
        if series.empty:
            continue

        result["column_stats"][column] = {
            "sum": round(float(series.sum()), 2),
            "average": round(float(series.mean()), 2),
            "minimum": round(float(series.min()), 2),
            "maximum": round(float(series.max()), 2),
            "median": round(float(series.median()), 2),
            "std_dev": round(float(series.std()), 2) if len(series) > 1 else 0.0
        }

    # ======================================
    # FIND BUSINESS COLUMNS
    # ======================================
    revenue_col = find_column(df, ["revenue", "sales", "total_sales", "sales_amount", "amount", "income"])
    profit_col = find_column(df, ["profit", "net_profit", "gross_profit"])
    quantity_col = find_column(df, ["quantity", "units", "units_sold", "qty"])
    product_col = find_column(df, ["product", "product_name", "item", "item_name"])
    region_col = find_column(df, ["region", "area", "location", "territory"])
    category_col = find_column(df, ["category", "product_category", "type", "segment"])
    date_col = find_column(df, ["date", "order_date", "sale_date", "transaction_date", "created_at"])

    # ======================================
    # REVENUE KPIs
    # ======================================
    if revenue_col:
        revenue = pd.to_numeric(df[revenue_col], errors="coerce").fillna(0)
        tot_rev = float(revenue.sum())
        avg_rev = float(revenue.mean())
        result["kpis"]["total_revenue"] = round(tot_rev, 2)
        result["kpis"]["average_revenue"] = round(avg_rev, 2)

    # ======================================
    # PROFIT KPIs
    # ======================================
    if profit_col:
        profit = pd.to_numeric(df[profit_col], errors="coerce").fillna(0)
        tot_prof = float(profit.sum())
        avg_prof = float(profit.mean())
        result["kpis"]["total_profit"] = round(tot_prof, 2)
        result["kpis"]["average_profit"] = round(avg_prof, 2)

    # ======================================
    # QUANTITY KPIs
    # ======================================
    if quantity_col:
        quantity = pd.to_numeric(df[quantity_col], errors="coerce").fillna(0)
        tot_qty = float(quantity.sum())
        result["kpis"]["total_quantity"] = round(tot_qty, 2)

    # ======================================
    # PROFIT MARGIN KPI
    # ======================================
    if revenue_col and profit_col:
        tot_rev = result["kpis"].get("total_revenue", 0)
        tot_prof = result["kpis"].get("total_profit", 0)
        if tot_rev > 0:
            margin = round((tot_prof / tot_rev) * 100, 2)
            result["kpis"]["profit_margin"] = margin
            result["highlights"]["profit_margin"] = f"{margin}%"

            if margin >= 30:
                result["insights"].append(f"The business maintains a strong profit margin of {margin}%.")
            elif margin >= 15:
                result["insights"].append(f"The business has a moderate profit margin of {margin}%.")
            else:
                result["insights"].append(f"The profit margin is low at {margin}% and requires cost optimization.")

    # ======================================
    # REVENUE & PROFIT BY PRODUCT
    # ======================================
    if product_col and revenue_col:
        temp = df[[product_col, revenue_col]].copy()
        temp[revenue_col] = pd.to_numeric(temp[revenue_col], errors="coerce").fillna(0)
        temp[product_col] = temp[product_col].fillna("Unknown").astype(str).str.strip()
        temp = temp[temp[product_col] != ""]

        product_rev = temp.groupby(product_col)[revenue_col].sum().sort_values(ascending=False).head(10)
        result["charts"]["revenue_by_product"] = {str(k): round(float(v), 2) for k, v in product_rev.items()}

        if not product_rev.empty:
            top_prod = str(product_rev.index[0])
            top_prod_rev = float(product_rev.iloc[0])
            result["kpis"]["top_product"] = top_prod
            result["highlights"]["top_product"] = top_prod
            result["insights"].append(f"'{top_prod}' is the top-performing product generating {top_prod_rev:,.2f} in revenue.")

    if product_col and profit_col:
        temp = df[[product_col, profit_col]].copy()
        temp[profit_col] = pd.to_numeric(temp[profit_col], errors="coerce").fillna(0)
        temp[product_col] = temp[product_col].fillna("Unknown").astype(str).str.strip()
        temp = temp[temp[product_col] != ""]

        product_prof = temp.groupby(product_col)[profit_col].sum().sort_values(ascending=False).head(10)
        result["charts"]["profit_by_product"] = {str(k): round(float(v), 2) for k, v in product_prof.items()}

        if not product_prof.empty:
            top_prof_prod = str(product_prof.index[0])
            result["highlights"]["highest_profit_product"] = top_prof_prod

    # ======================================
    # REVENUE & PROFIT BY REGION
    # ======================================
    if region_col and revenue_col:
        temp = df[[region_col, revenue_col]].copy()
        temp[revenue_col] = pd.to_numeric(temp[revenue_col], errors="coerce").fillna(0)
        temp[region_col] = temp[region_col].fillna("Unknown").astype(str).str.strip()
        temp = temp[temp[region_col] != ""]

        region_rev = temp.groupby(region_col)[revenue_col].sum().sort_values(ascending=False)
        result["charts"]["revenue_by_region"] = {str(k): round(float(v), 2) for k, v in region_rev.items()}

        if not region_rev.empty:
            best_reg = str(region_rev.index[0])
            best_reg_rev = float(region_rev.iloc[0])
            result["kpis"]["best_region"] = best_reg
            result["highlights"]["best_region"] = best_reg
            result["insights"].append(f"'{best_reg}' is the highest-revenue region contributing {best_reg_rev:,.2f}.")

    if region_col and profit_col:
        temp = df[[region_col, profit_col]].copy()
        temp[profit_col] = pd.to_numeric(temp[profit_col], errors="coerce").fillna(0)
        temp[region_col] = temp[region_col].fillna("Unknown").astype(str).str.strip()
        temp = temp[temp[region_col] != ""]

        region_prof = temp.groupby(region_col)[profit_col].sum().sort_values(ascending=False)
        result["charts"]["profit_by_region"] = {str(k): round(float(v), 2) for k, v in region_prof.items()}

    # ======================================
    # REVENUE BY CATEGORY
    # ======================================
    if category_col and revenue_col:
        temp = df[[category_col, revenue_col]].copy()
        temp[revenue_col] = pd.to_numeric(temp[revenue_col], errors="coerce").fillna(0)
        temp[category_col] = temp[category_col].fillna("Unknown").astype(str).str.strip()
        temp = temp[temp[category_col] != ""]

        cat_rev = temp.groupby(category_col)[revenue_col].sum().sort_values(ascending=False).head(10)
        result["charts"]["revenue_by_category"] = {str(k): round(float(v), 2) for k, v in cat_rev.items()}

        if not cat_rev.empty:
            top_cat = str(cat_rev.index[0])
            result["kpis"]["top_category"] = top_cat
            result["highlights"]["top_category"] = top_cat

    # ======================================
    # REVENUE OVER TIME (TIME-SERIES)
    # ======================================
    if date_col and revenue_col:
        try:
            temp = df[[date_col, revenue_col]].copy()
            temp[revenue_col] = pd.to_numeric(temp[revenue_col], errors="coerce").fillna(0)
            temp["parsed_date"] = pd.to_datetime(temp[date_col], errors="coerce", format="mixed")
            temp = temp.dropna(subset=["parsed_date"])

            if not temp.empty:
                temp = temp.sort_values("parsed_date")
                min_d = temp["parsed_date"].min()
                max_d = temp["parsed_date"].max()
                day_diff = (max_d - min_d).days

                if day_diff > 365:
                    temp["period"] = temp["parsed_date"].dt.to_period("M").astype(str)
                elif day_diff > 30:
                    temp["period"] = temp["parsed_date"].dt.to_period("W").astype(str)
                else:
                    temp["period"] = temp["parsed_date"].dt.strftime("%Y-%m-%d")

                trend_data = temp.groupby("period")[revenue_col].sum()
                result["charts"]["revenue_trend"] = {str(k): round(float(v), 2) for k, v in trend_data.items()}
                result["insights"].append(f"Revenue trend computed across date range {min_d.strftime('%Y-%m-%d')} to {max_d.strftime('%Y-%m-%d')}.")
        except Exception:
            pass

    # Dataset Size Summary Insight
    if len(df) > 0:
        result["insights"].append(f"Analyzed {len(df):,} records across {len(df.columns)} columns.")

    return result


def find_column(df, possible_names):
    """
    Search for matching column names using normalized case-insensitive & whitespace-tolerant logic.
    """
    normalized_columns = {
        str(column).strip().lower().replace(" ", "_"): column
        for column in df.columns
    }

    for name in possible_names:
        normalized_name = name.strip().lower().replace(" ", "_")
        if normalized_name in normalized_columns:
            return normalized_columns[normalized_name]

    return None