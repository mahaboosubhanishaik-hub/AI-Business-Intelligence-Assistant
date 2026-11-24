import unittest

from app import create_app, db


class PasswordRecoveryEmailTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="password-recovery-test-secret",
            ADMIN_USERNAME="@admin",
            ADMIN_EMAIL="admin@localhost",
            ADMIN_PASSWORD="A12345678",
            WTF_CSRF_ENABLED=False
        )
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        self.app_context.pop()

    def test_login_page_has_prefilled_admin_email_draft(self):
        response = self.client.get("/auth/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Forgot Password?", response.data)
        self.assertIn(b"adminaibia@gmail.com", response.data)
        self.assertIn(
            b"AI%20BIA%20%E2%80%93%20Business%20Account%20Password%20Recovery%20Request",
            response.data
        )
        self.assertIn(b"Registered Business Name", response.data)
        self.assertIn(b"Registered Email", response.data)
        self.assertIn(b"Business Handle", response.data)

    def test_legacy_password_recovery_routes_are_removed(self):
        for path in (
            "/auth/forgot",
            "/auth/forgot-password",
            "/auth/reset/example-token",
            "/auth/reset-password/example-token"
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
