import os
import unittest
import uuid
from datetime import datetime

from app import create_app, db
from app.models.activity_log import ActivityLog
from app.models.dataset import Dataset
from app.models.monthly_budget import MonthlyBudget
from app.models.quality_audit import QualityAudit
from app.models.user import User
from app.services.business_metrics import UPLOAD_FOLDER


class BusinessReportsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="business-reports-test-secret",
            ADMIN_USERNAME="@admin",
            ADMIN_EMAIL="admin@localhost",
            ADMIN_PASSWORD="A12345678",
            WTF_CSRF_ENABLED=False,
            RATELIMIT_ENABLED=False
        )
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.client = self.app.test_client()
        self.user = User(
            name="Report Test User",
            username=f"report_{uuid.uuid4().hex[:12]}",
            email=f"report_{uuid.uuid4().hex[:12]}@example.com"
        )
        self.user.set_password("ReportPassword123!")
        db.session.add(self.user)
        db.session.flush()

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        self.filename = f"business_report_test_{uuid.uuid4().hex}.csv"
        self.filepath = os.path.join(UPLOAD_FOLDER, self.filename)
        with open(self.filepath, "w", encoding="utf-8", newline="") as dataset_file:
            dataset_file.write(
                "Date,Branch,Team,Revenue,Units\n"
                "2026-10-05,North,Sales,100,2\n"
                "2026-10-12,South,Sales,150,3\n"
                "2026-11-02,North,Support,200,4\n"
                "2026-11-10,South,Sales,50,1\n"
            )
        self.dataset = Dataset(
            user_id=self.user.id,
            name="Quarterly Business Results",
            filename=self.filename,
            source_type="csv",
            rows=4,
            columns=5
        )
        db.session.add(self.dataset)
        db.session.commit()
        self.client.get("/auth/login")
        self.client.post(
            "/auth/login",
            data={
                "identifier": self.user.username,
                "password": "ReportPassword123!"
            }
        )

    def tearDown(self):
        MonthlyBudget.query.filter_by(user_id=self.user.id).delete()
        QualityAudit.query.filter_by(user_id=self.user.id).delete()
        ActivityLog.query.filter_by(user_id=self.user.id).delete()
        db.session.delete(self.dataset)
        db.session.delete(self.user)
        db.session.commit()
        db.session.remove()
        self.app_context.pop()
        if os.path.exists(self.filepath):
            os.remove(self.filepath)

    def test_budget_actual_uses_owned_dataset_and_selected_group(self):
        response = self.client.post(
            "/reports/budgets",
            data={
                "dataset_id": self.dataset.id,
                "month": "2026-11",
                "date_column": "Date",
                "value_column": "Revenue",
                "group_column": "Branch",
                "group_value": "North",
                "budget_amount": "250.00"
            },
            follow_redirects=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"North", response.data)
        self.assertIn(b"200.00", response.data)
        self.assertIn(b"-50.00", response.data)
        budget = MonthlyBudget.query.filter_by(user_id=self.user.id).one()
        self.assertEqual(budget.period_start.isoformat(), "2026-11-01")
        self.assertEqual(str(budget.budget_amount), "250.00")

    def test_comparison_supports_group_and_month_dimensions(self):
        response = self.client.get(
            "/reports/compare",
            query_string={
                "dataset_id": self.dataset.id,
                "value_column": "Revenue",
                "group_column": "Branch",
                "date_column": "Date"
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"2026-10", response.data)
        self.assertIn(b"2026-11", response.data)
        self.assertIn(b"North", response.data)
        self.assertIn(b"200.00", response.data)

    def test_monthly_report_is_printable_and_uses_account_data(self):
        db.session.add(MonthlyBudget(
            user_id=self.user.id,
            dataset_id=self.dataset.id,
            period_start=datetime(2026, 11, 1).date(),
            date_column="Date",
            value_column="Revenue",
            group_column="",
            group_value="",
            budget_amount=300
        ))
        db.session.add(ActivityLog(
            user_id=self.user.id,
            dataset_id=self.dataset.id,
            event_type="analytics_view",
            description="Reviewed monthly results",
            created_at=datetime(2026, 11, 12, 9, 0)
        ))
        db.session.add(QualityAudit(
            dataset_id=self.dataset.id,
            user_id=self.user.id,
            quality_score=92.5,
            status="Good",
            missing_count=0,
            duplicate_count=0,
            outlier_count=1,
            suspicious_count=0,
            audited_at=datetime(2026, 11, 12, 9, 0)
        ))
        db.session.commit()

        response = self.client.get("/reports/monthly?month=2026-11")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"November 2026", response.data)
        self.assertIn(b"Print / Save PDF", response.data)
        self.assertIn(b"250.00", response.data)
        self.assertIn(b"92.5%", response.data)

    def test_budget_route_cannot_access_another_users_dataset(self):
        other_user = User(
            name="Other Account",
            username=f"other_{uuid.uuid4().hex[:12]}",
            email=f"other_{uuid.uuid4().hex[:12]}@example.com"
        )
        other_user.set_password("OtherPassword123!")
        db.session.add(other_user)
        db.session.flush()
        other_dataset = Dataset(
            user_id=other_user.id,
            name="Private dataset",
            filename="not-on-disk.csv",
            source_type="csv"
        )
        db.session.add(other_dataset)
        db.session.commit()

        response = self.client.post(
            "/reports/budgets",
            data={
                "dataset_id": other_dataset.id,
                "month": "2026-11",
                "date_column": "Date",
                "value_column": "Revenue",
                "budget_amount": "250"
            }
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(MonthlyBudget.query.count(), 0)
        db.session.delete(other_dataset)
        db.session.delete(other_user)
        db.session.commit()


if __name__ == "__main__":
    unittest.main()
