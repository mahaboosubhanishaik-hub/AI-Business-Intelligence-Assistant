import unittest
import pandas as pd

from app import create_app, db
from app.models.user import User
from app.models.dataset import Dataset
from app.services.analytics import generate_analytics
from app.services.data_quality import evaluate_data_quality


class Phase4TestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        self.cleanup_test_data()

        self.user_a = User(name="Phase4 User A", email="p4_user_a@example.com")
        self.user_a.set_password("Password123!")

        self.user_b = User(name="Phase4 User B", email="p4_user_b@example.com")
        self.user_b.set_password("Password123!")

        db.session.add_all([self.user_a, self.user_b])
        db.session.commit()

    def tearDown(self):
        self.cleanup_test_data()
        self.app_context.pop()

    def cleanup_test_data(self):
        db.session.rollback()
        users = User.query.filter(User.email.in_(["p4_user_a@example.com", "p4_user_b@example.com"])).all()
        for u in users:
            Dataset.query.filter_by(user_id=u.id).delete(synchronize_session=False)
            db.session.delete(u)
        db.session.commit()

    def login_user(self, email="p4_user_a@example.com", password="Password123!"):
        return self.client.post("/auth/login", data={
            "email": email,
            "password": password
        }, follow_redirects=True)

    def test_01_full_business_dataset_analytics(self):
        df = pd.DataFrame({
            "Product": ["Laptop", "Mouse", "Keyboard", "Laptop"],
            "Region": ["North", "South", "North", "East"],
            "Revenue": [1000.0, 200.0, 300.0, 1500.0],
            "Profit": [300.0, 50.0, 75.0, 450.0],
            "Units_Sold": [10, 20, 15, 12],
            "Date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
        })

        res = generate_analytics(df)

        self.assertEqual(res["kpis"]["total_revenue"], 3000.0)
        self.assertEqual(res["kpis"]["total_profit"], 875.0)
        self.assertEqual(res["kpis"]["total_quantity"], 57.0)
        self.assertEqual(res["kpis"]["profit_margin"], 29.17)
        self.assertEqual(res["kpis"]["top_product"], "Laptop")
        self.assertEqual(res["kpis"]["best_region"], "East")

        self.assertIn("Laptop", res["charts"]["revenue_by_product"])
        self.assertIn("East", res["charts"]["revenue_by_region"])
        self.assertTrue(len(res["charts"]["revenue_trend"]) > 0)

        self.assertIn("Revenue", res["column_stats"])
        self.assertEqual(res["column_stats"]["Revenue"]["sum"], 3000.0)
        self.assertEqual(res["column_stats"]["Revenue"]["median"], 650.0)

    def test_02_time_series_trend_analytics(self):
        df = pd.DataFrame({
            "Order_Date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "Sales": [500.0, 700.0, 1200.0]
        })
        res = generate_analytics(df)

        self.assertEqual(res["kpis"]["total_revenue"], 2400.0)
        self.assertTrue(len(res["charts"]["revenue_trend"]) > 0)

    def test_03_non_business_dataset(self):
        df = pd.DataFrame({
            "Employee": ["Alice", "Bob", "Charlie"],
            "Age": [25, 30, 35],
            "Salary": [50000.0, 60000.0, 70000.0]
        })
        res = generate_analytics(df)

        self.assertNotIn("total_revenue", res["kpis"])
        self.assertIn("Age", res["column_stats"])
        self.assertIn("Salary", res["column_stats"])
        self.assertEqual(res["column_stats"]["Salary"]["average"], 60000.0)

    def test_04_dqm_bi_integration_and_warning(self):
        # Create dataset with low quality score (< 75%)
        df = pd.DataFrame({
            "Product": ["Widget", None, "Widget", None],
            "Revenue": [100.0, None, 100.0, None]
        })
        report = evaluate_data_quality(df)
        self.assertLess(report["score"], 75.0)

    def test_05_analytics_ownership_security(self):
        ds_a = Dataset(
            user_id=self.user_a.id,
            name="user_a_private_analytics",
            filename="non_existent.csv",
            source_type="csv",
            rows=10,
            columns=2,
            file_size_bytes=100
        )
        db.session.add(ds_a)
        db.session.commit()

        # Login as User B
        self.login_user("p4_user_b@example.com")

        # Attempt to access User A's analytics
        response = self.client.get(f"/analytics/{ds_a.id}")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
