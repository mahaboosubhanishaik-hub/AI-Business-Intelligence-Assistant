import unittest
import pandas as pd

from app import create_app, db
from app.models.user import User
from app.models.dataset import Dataset
from app.services.data_quality import evaluate_data_quality


class Phase3TestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        self.cleanup_test_data()

        self.user_a = User(name="Phase3 User A", email="p3_user_a@example.com")
        self.user_a.set_password("Password123!")

        self.user_b = User(name="Phase3 User B", email="p3_user_b@example.com")
        self.user_b.set_password("Password123!")

        db.session.add_all([self.user_a, self.user_b])
        db.session.commit()

    def tearDown(self):
        self.cleanup_test_data()
        self.app_context.pop()

    def cleanup_test_data(self):
        db.session.rollback()
        users = User.query.filter(User.email.in_(["p3_user_a@example.com", "p3_user_b@example.com"])).all()
        for u in users:
            Dataset.query.filter_by(user_id=u.id).delete(synchronize_session=False)
            db.session.delete(u)
        db.session.commit()

    def login_user(self, email="p3_user_a@example.com", password="Password123!"):
        return self.client.post("/auth/login", data={
            "email": email,
            "password": password
        }, follow_redirects=True)

    def test_01_clean_dataset(self):
        df = pd.DataFrame({
            "Product": ["Widget A", "Widget B", "Widget C", "Widget D"],
            "Region": ["North", "South", "East", "West"],
            "Revenue": [1000.0, 2000.0, 3000.0, 4000.0]
        })
        report = evaluate_data_quality(df)
        self.assertEqual(report["score"], 100.0)
        self.assertEqual(report["status"], "Excellent")
        self.assertEqual(len(report["issues"]), 0)

    def test_02_dataset_with_missing_values(self):
        df = pd.DataFrame({
            "Product": ["Widget A", None, "Widget C", None],
            "Revenue": [1000.0, None, 3000.0, 4000.0]
        })
        report = evaluate_data_quality(df)
        self.assertLess(report["score"], 100.0)
        self.assertLess(report["dimensions"]["completeness"], 100.0)

        missing_issue = next(i for i in report["issues"] if i["issue_type"] == "Missing Values")
        self.assertIsNotNone(missing_issue)

    def test_03_dataset_with_duplicates(self):
        df = pd.DataFrame({
            "Product": ["Widget A", "Widget A", "Widget B"],
            "Revenue": [1000.0, 1000.0, 2000.0]
        })
        report = evaluate_data_quality(df)
        self.assertLess(report["dimensions"]["uniqueness"], 100.0)
        dup_issue = next(i for i in report["issues"] if i["issue_type"] == "Duplicate Rows")
        self.assertIsNotNone(dup_issue)

    def test_04_dataset_with_suspicious_values(self):
        df = pd.DataFrame({
            "Product": ["Widget A", "Widget B", "Widget C"],
            "Revenue": [1000.0, -500.0, 3000.0]  # Negative revenue
        })
        report = evaluate_data_quality(df)
        suspicious_issue = next(i for i in report["issues"] if i["issue_type"] == "Suspicious Negative Values")
        self.assertIsNotNone(suspicious_issue)

    def test_05_dataset_with_outliers(self):
        df = pd.DataFrame({
            "Revenue": [100, 102, 105, 101, 103, 104, 102, 10000]  # 10000 is an IQR outlier
        })
        report = evaluate_data_quality(df)
        outlier_issue = next(i for i in report["issues"] if i["issue_type"] == "Outliers (IQR)")
        self.assertIsNotNone(outlier_issue)

    def test_06_dataset_with_empty_strings(self):
        df = pd.DataFrame({
            "Product": ["Widget A", "   ", "", "Widget B"]
        })
        report = evaluate_data_quality(df)
        empty_issue = next(i for i in report["issues"] if i["issue_type"] == "Empty Strings")
        self.assertIsNotNone(empty_issue)

    def test_07_business_dataset_evaluation(self):
        df = pd.DataFrame({
            "Product": ["Laptop", "Mouse", "Keyboard", "Monitor", "Desk"],
            "Region": ["North", "South", "East", "West", "North"],
            "Revenue": [1200.0, 50.0, 80.0, 300.0, 500.0],
            "Profit": [300.0, 15.0, 25.0, 75.0, 125.0],
            "Units_Sold": [10, 50, 40, 15, 5]
        })
        report = evaluate_data_quality(df)
        self.assertGreaterEqual(report["score"], 80.0)
        self.assertIn(report["status"], ["Excellent", "Good"])

    def test_08_dqm_ownership_security(self):
        ds_a = Dataset(
            user_id=self.user_a.id,
            name="user_a_dqm_data",
            filename="non_existent.csv",
            source_type="csv",
            rows=10,
            columns=2,
            file_size_bytes=100
        )
        db.session.add(ds_a)
        db.session.commit()

        # Login as User B
        self.login_user("p3_user_b@example.com")

        # Attempt to access User A's quality report
        response = self.client.get(f"/data/quality/{ds_a.id}")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
