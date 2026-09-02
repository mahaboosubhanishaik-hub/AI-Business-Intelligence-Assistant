import unittest
import pandas as pd

from app import create_app, db
from app.models.user import User
from app.models.dataset import Dataset
from app.services.data_quality import evaluate_data_quality
from app.services.analytics import generate_analytics
from app.services.ai_service import (
    build_ai_context,
    generate_ai_summary,
    ask_ai_assistant
)


class Phase5TestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        self.cleanup_test_data()

        self.user_a = User(name="Phase5 User A", email="p5_user_a@example.com")
        self.user_a.set_password("Password123!")

        self.user_b = User(name="Phase5 User B", email="p5_user_b@example.com")
        self.user_b.set_password("Password123!")

        db.session.add_all([self.user_a, self.user_b])
        db.session.commit()

    def tearDown(self):
        self.cleanup_test_data()
        self.app_context.pop()

    def cleanup_test_data(self):
        db.session.rollback()
        users = User.query.filter(User.email.in_(["p5_user_a@example.com", "p5_user_b@example.com"])).all()
        for u in users:
            Dataset.query.filter_by(user_id=u.id).delete(synchronize_session=False)
            db.session.delete(u)
        db.session.commit()

    def login_user(self, email="p5_user_a@example.com", password="Password123!"):
        return self.client.post("/auth/login", data={
            "email": email,
            "password": password
        }, follow_redirects=True)

    def test_01_context_builder(self):
        df = pd.DataFrame({
            "Product": ["Laptop", "Mouse"],
            "Region": ["North", "South"],
            "Revenue": [1000.0, 200.0]
        })
        dqm = evaluate_data_quality(df)
        analytics = generate_analytics(df)

        context = build_ai_context(df, "Sample_Sales", dqm, analytics)

        self.assertEqual(context["dataset_metadata"]["name"], "Sample_Sales")
        self.assertEqual(context["dataset_metadata"]["total_rows"], 2)
        self.assertEqual(context["data_quality_monitoring"]["score"], 100.0)
        self.assertEqual(context["business_intelligence_kpis"]["total_revenue"], 1200.0)

    def test_02_summary_generator_and_fallback(self):
        df = pd.DataFrame({
            "Product": ["Laptop", "Mouse"],
            "Region": ["North", "South"],
            "Revenue": [1000.0, 200.0]
        })
        dqm = evaluate_data_quality(df)
        analytics = generate_analytics(df)

        summary = generate_ai_summary(df, "Sample_Sales", dqm, analytics)

        self.assertIn("summary", summary)
        self.assertIn("recommendations", summary)
        self.assertTrue(len(summary["recommendations"]) > 0)

    def test_03_missing_api_key_graceful_fallback(self):
        df = pd.DataFrame({
            "Product": ["Laptop"],
            "Revenue": [1000.0]
        })
        dqm = evaluate_data_quality(df)
        analytics = generate_analytics(df)

        # Query assistant when API key is missing/unconfigured
        res = ask_ai_assistant(df, "Sample_Sales", dqm, analytics, "What is my total revenue?")

        self.assertIn("status", res)
        self.assertIn("answer", res)
        # Should gracefully return message without crashing application
        self.assertTrue("unavailable" in res["answer"].lower() or "revenue" in res["answer"].lower() or res["status"] in ["disabled", "success"])

    def test_04_ai_route_ownership_security(self):
        ds_a = Dataset(
            user_id=self.user_a.id,
            name="user_a_private_ai_dataset",
            filename="non_existent.csv",
            source_type="csv",
            rows=10,
            columns=2,
            file_size_bytes=100
        )
        db.session.add(ds_a)
        db.session.commit()

        # Login as User B
        self.login_user("p5_user_b@example.com")

        # Attempt GET request to User A's AI assistant endpoint
        res_get = self.client.get(f"/ai/assistant/{ds_a.id}")
        self.assertEqual(res_get.status_code, 404)

        # Attempt POST request to User A's AI assistant endpoint
        res_post = self.client.post(
            f"/ai/assistant/{ds_a.id}",
            json={"question": "What is the total revenue?"}
        )
        self.assertEqual(res_post.status_code, 404)


if __name__ == "__main__":
    unittest.main()
