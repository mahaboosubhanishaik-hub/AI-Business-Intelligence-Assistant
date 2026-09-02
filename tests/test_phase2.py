import os
import unittest
import io
import pandas as pd

from app import create_app, db
from app.models.user import User
from app.models.dataset import Dataset
from app.services.data_profiler import profile_dataset, detect_column_type


class Phase2TestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Clean up leftover test users and datasets safely
        self.cleanup_test_data()

        # Create test users
        self.user_a = User(name="User A", email="user_a@example.com")
        self.user_a.set_password("Password123!")

        self.user_b = User(name="User B", email="user_b@example.com")
        self.user_b.set_password("Password123!")

        db.session.add_all([self.user_a, self.user_b])
        db.session.commit()

    def tearDown(self):
        self.cleanup_test_data()
        self.app_context.pop()

    def cleanup_test_data(self):
        db.session.rollback()
        users = User.query.filter(User.email.in_(["user_a@example.com", "user_b@example.com"])).all()
        for u in users:
            Dataset.query.filter_by(user_id=u.id).delete(synchronize_session=False)
            db.session.delete(u)
        db.session.commit()

    def login_user(self, email="user_a@example.com", password="Password123!"):
        return self.client.post("/auth/login", data={
            "email": email,
            "password": password
        }, follow_redirects=True)

    def test_01_type_detection_and_profiler(self):
        # Create a sample DataFrame
        df = pd.DataFrame({
            "Revenue": [100.5, 200.0, None, 400.25],
            "Units": [10, 20, 30, 40],
            "Region": ["North", "South", "North", "East"],
            "Date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
        })

        self.assertEqual(detect_column_type(df["Revenue"]), "float")
        self.assertEqual(detect_column_type(df["Units"]), "integer")
        self.assertEqual(detect_column_type(df["Region"]), "string")
        self.assertEqual(detect_column_type(df["Date"]), "datetime")

        profile = profile_dataset(df)
        self.assertEqual(profile["rows"], 4)
        self.assertEqual(profile["columns"], 4)
        self.assertEqual(profile["missing_values"], 1)
        self.assertEqual(profile["duplicate_rows"], 0)

        # Check numeric stats for Revenue
        rev_info = next(c for c in profile["column_information"] if c["name"] == "Revenue")
        self.assertEqual(rev_info["min"], 100.5)
        self.assertEqual(rev_info["max"], 400.25)
        self.assertEqual(rev_info["missing_count"], 1)

        # Check categorical stats for Region
        reg_info = next(c for c in profile["column_information"] if c["name"] == "Region")
        self.assertEqual(reg_info["top_value"], "North")
        self.assertEqual(reg_info["top_frequency"], 2)

    def test_02_dataset_upload_csv(self):
        self.login_user("user_a@example.com")

        csv_data = "Product,Sales,Region\nWidget A,150,North\nWidget B,250,South\nWidget A,150,North\n"
        data = {
            "file": (io.BytesIO(csv_data.encode("utf-8")), "sample_sales.csv")
        }

        response = self.client.post("/data/upload", data=data, content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Dataset uploaded and profiled successfully!", response.data)
        self.assertIn(b"sample_sales", response.data)

        # Verify dataset saved in DB
        ds = Dataset.query.filter_by(user_id=self.user_a.id, name="sample_sales").first()
        self.assertIsNotNone(ds)
        self.assertEqual(ds.rows, 3)
        self.assertEqual(ds.columns, 3)
        self.assertIsNotNone(ds.file_size_bytes)

        # Clean up physical file
        upload_path = os.path.join(os.getcwd(), "uploads", ds.filename)
        if os.path.exists(upload_path):
            os.remove(upload_path)

    def test_03_invalid_file_upload_rejected(self):
        self.login_user("user_a@example.com")

        # Invalid extension
        data = {
            "file": (io.BytesIO(b"executable code"), "malicious.exe")
        }
        response = self.client.post("/data/upload", data=data, content_type="multipart/form-data", follow_redirects=True)
        self.assertIn(b"Only CSV (.csv) and Excel (.xlsx, .xls) files are allowed", response.data)

        # Empty file
        data = {
            "file": (io.BytesIO(b""), "empty.csv")
        }
        response = self.client.post("/data/upload", data=data, content_type="multipart/form-data", follow_redirects=True)
        self.assertIn(b"Uploaded file is empty", response.data)

    def test_04_dataset_ownership_security(self):
        # Create dataset for User A
        ds_a = Dataset(
            user_id=self.user_a.id,
            name="user_a_private_data",
            filename="non_existent_a.csv",
            source_type="csv",
            rows=10,
            columns=2,
            file_size_bytes=100
        )
        db.session.add(ds_a)
        db.session.commit()

        # Login as User B
        self.login_user("user_b@example.com")

        # Attempt to access User A's dataset view, preview, and delete
        res_view = self.client.get(f"/data/view/{ds_a.id}")
        self.assertEqual(res_view.status_code, 404)

        res_prev = self.client.get(f"/data/preview/{ds_a.id}")
        self.assertEqual(res_prev.status_code, 404)

        res_del = self.client.post(f"/data/delete/{ds_a.id}")
        self.assertEqual(res_del.status_code, 404)


if __name__ == "__main__":
    unittest.main()
