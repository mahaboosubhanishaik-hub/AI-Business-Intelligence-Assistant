import unittest
import pandas as pd

from app import create_app, db
from app.models.user import User
from app.models.dataset import Dataset
from app.models.quality_audit import QualityAudit
from app.services.data_quality import evaluate_data_quality
from app.services.monitoring import (
    audit_and_monitor_quality,
    QUALITY_DEGRADATION_THRESHOLD
)


class Phase6TestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        self.cleanup_test_data()

        self.user = User(name="Phase6 User", email="p6_user@example.com")
        self.user.set_password("Password123!")

        db.session.add(self.user)
        db.session.commit()

        self.dataset = Dataset(
            user_id=self.user.id,
            name="p6_test_dataset",
            filename="p6_test.csv",
            source_type="csv",
            rows=10,
            columns=3,
            file_size_bytes=500
        )
        db.session.add(self.dataset)
        db.session.commit()

    def tearDown(self):
        self.cleanup_test_data()
        self.app_context.pop()

    def cleanup_test_data(self):
        db.session.rollback()
        user = User.query.filter_by(email="p6_user@example.com").first()
        if user:
            QualityAudit.query.filter_by(user_id=user.id).delete(synchronize_session=False)
            Dataset.query.filter_by(user_id=user.id).delete(synchronize_session=False)
            db.session.delete(user)
        db.session.commit()

    def test_01_quality_audit_model_persistence(self):
        audit = QualityAudit(
            dataset_id=self.dataset.id,
            user_id=self.user.id,
            quality_score=95.0,
            status="Excellent",
            missing_count=0,
            duplicate_count=0,
            outlier_count=0,
            suspicious_count=0
        )
        db.session.add(audit)
        db.session.commit()

        retrieved = QualityAudit.query.filter_by(dataset_id=self.dataset.id).first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.quality_score, 95.0)
        self.assertEqual(retrieved.status, "Excellent")

    def test_02_quality_degradation_detection(self):
        # Step 1: Initial high quality audit
        initial_audit = QualityAudit(
            dataset_id=self.dataset.id,
            user_id=self.user.id,
            quality_score=95.0,
            status="Excellent",
            missing_count=0,
            duplicate_count=0,
            outlier_count=0,
            suspicious_count=0
        )
        db.session.add(initial_audit)
        db.session.commit()

        # Step 2: New evaluation with degraded dataset quality (missing values & duplicates)
        degraded_df = pd.DataFrame({
            "Product": ["A", "A", None, None],
            "Region": ["North", "North", None, None],
            "Revenue": [100.0, 100.0, None, None]
        })
        degraded_dqm = evaluate_data_quality(degraded_df)

        # Step 3: Run monitoring service
        monitoring_res = audit_and_monitor_quality(self.dataset.id, self.user.id, degraded_dqm)

        self.assertTrue(monitoring_res["degradation_detected"])
        self.assertTrue(monitoring_res["score_delta"] <= -QUALITY_DEGRADATION_THRESHOLD)
        self.assertTrue(any(a["type"] == "DEGRADATION_ALERT" for a in monitoring_res["alerts"]))

    def test_03_security_http_headers(self):
        res = self.client.get("/")
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(res.headers.get("X-XSS-Protection"), "1; mode=block")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

    def test_04_ownership_security_check(self):
        # Login as a different user attempting to access Phase 6 dataset quality analysis
        other_user = User(name="Unauthorized User", email="unauth@example.com")
        other_user.set_password("Password123!")
        db.session.add(other_user)
        db.session.commit()

        self.client.post("/auth/login", data={"email": "unauth@example.com", "password": "Password123!"})

        res = self.client.get(f"/data/quality/{self.dataset.id}")
        self.assertEqual(res.status_code, 404)

        # Cleanup
        Dataset.query.filter_by(user_id=other_user.id).delete()
        db.session.delete(other_user)
        db.session.commit()


if __name__ == "__main__":
    unittest.main()
