from app import db
from app.models.quality_audit import QualityAudit


# ==========================================
# CENTRALIZED MONITORING THRESHOLDS
# ==========================================
QUALITY_DEGRADATION_THRESHOLD = 10.0  # Quality score drop >= 10 points triggers degradation alert
CRITICAL_MISSING_THRESHOLD = 30.0    # Missing cell ratio >= 30%
CRITICAL_DUPLICATE_THRESHOLD = 20.0  # Duplicate row ratio >= 20%
CRITICAL_OUTLIER_THRESHOLD = 15.0    # Outlier ratio >= 15%


def audit_and_monitor_quality(dataset_id, user_id, quality_report):
    """
    Perform quality tracking, detect quality degradation against previous audits,
    generate automated alert notifications, and persist new quality audit snapshot.
    """
    if not quality_report:
        return {
            "previous_audit": None,
            "current_audit": None,
            "score_delta": 0.0,
            "degradation_detected": False,
            "alerts": []
        }

    current_score = float(quality_report.get("score", 0.0))
    current_status = quality_report.get("status", "Unknown")
    summary = quality_report.get("summary", {})

    missing_cnt = summary.get("missing_values", 0)
    duplicate_cnt = summary.get("duplicate_rows", 0)
    outlier_cnt = summary.get("outliers_count", 0)
    suspicious_cnt = summary.get("suspicious_values", 0)

    # Fetch most recent previous audit for dataset
    previous_audit_obj = (
        QualityAudit.query
        .filter_by(dataset_id=dataset_id, user_id=user_id)
        .order_by(QualityAudit.audited_at.desc())
        .first()
    )

    previous_audit_dict = None
    score_delta = 0.0
    degradation_detected = False
    alerts = []

    if previous_audit_obj:
        prev_score = float(previous_audit_obj.quality_score)
        score_delta = round(current_score - prev_score, 1)

        previous_audit_dict = {
            "id": previous_audit_obj.id,
            "quality_score": prev_score,
            "status": previous_audit_obj.status,
            "missing_count": previous_audit_obj.missing_count,
            "duplicate_count": previous_audit_obj.duplicate_count,
            "outlier_count": previous_audit_obj.outlier_count,
            "suspicious_count": previous_audit_obj.suspicious_count,
            "audited_at": previous_audit_obj.audited_at.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Check for significant quality degradation
        if score_delta <= -QUALITY_DEGRADATION_THRESHOLD:
            degradation_detected = True
            alerts.append({
                "type": "DEGRADATION_ALERT",
                "severity": "CRITICAL",
                "message": f"DATA QUALITY DEGRADATION DETECTED: Quality score decreased by {abs(score_delta)} points (from {prev_score}% to {current_score}%)."
            })

    # Threshold Alerts
    tot_rows = summary.get("total_rows", 1) or 1
    tot_cols = summary.get("total_columns", 1) or 1
    tot_cells = tot_rows * tot_cols

    missing_pct = round((missing_cnt / tot_cells) * 100.0, 1)
    if missing_pct >= CRITICAL_MISSING_THRESHOLD:
        alerts.append({
            "type": "MISSING_VALUE_ALERT",
            "severity": "CRITICAL",
            "message": f"Critical missing values detected: {missing_pct}% of dataset cells are empty."
        })

    dup_pct = round((duplicate_cnt / tot_rows) * 100.0, 1)
    if dup_pct >= CRITICAL_DUPLICATE_THRESHOLD:
        alerts.append({
            "type": "DUPLICATE_ALERT",
            "severity": "CRITICAL",
            "message": f"Critical duplicate rows detected: {dup_pct}% of dataset rows are completely duplicated."
        })

    outlier_pct = round((outlier_cnt / tot_cells) * 100.0, 1)
    if outlier_pct >= CRITICAL_OUTLIER_THRESHOLD:
        alerts.append({
            "type": "OUTLIER_ALERT",
            "severity": "WARNING",
            "message": f"Significant statistical outliers detected: {outlier_pct}% of cell entries outside IQR normal bounds."
        })

    # Save new QualityAudit snapshot to PostgreSQL database
    new_audit = QualityAudit(
        dataset_id=dataset_id,
        user_id=user_id,
        quality_score=current_score,
        status=current_status,
        missing_count=missing_cnt,
        duplicate_count=duplicate_cnt,
        outlier_count=outlier_cnt,
        suspicious_count=suspicious_cnt
    )
    db.session.add(new_audit)
    db.session.commit()

    current_audit_dict = {
        "id": new_audit.id,
        "quality_score": current_score,
        "status": current_status,
        "missing_count": missing_cnt,
        "duplicate_count": duplicate_cnt,
        "outlier_count": outlier_cnt,
        "suspicious_count": suspicious_cnt,
        "audited_at": new_audit.audited_at.strftime("%Y-%m-%d %H:%M:%S")
    }

    return {
        "previous_audit": previous_audit_dict,
        "current_audit": current_audit_dict,
        "score_delta": score_delta,
        "degradation_detected": degradation_detected,
        "alerts": alerts
    }
