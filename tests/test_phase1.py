import unittest
import io
from app import create_app, db
from app.models.user import User
from app.models.dataset import Dataset


class Phase1TestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_01_app_initialization(self):
        self.assertIsNotNone(self.app)

    def test_02_home_route(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"AI Business Intelligence Assistant", response.data)

    def test_03_login_route_get(self):
        response = self.client.get("/auth/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login", response.data)

    def test_04_register_route_get(self):
        response = self.client.get("/auth/register")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Create a Business Account", response.data)

    def test_05_protected_routes_redirect_unauthenticated(self):
        for path in ["/dashboard", "/data/datasets", "/data/upload"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/auth/login", response.location)

    def test_06_custom_404_page(self):
        response = self.client.get("/non-existent-route-path")
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"Page Not Found", response.data)

    def test_07_user_password_hashing(self):
        u = User(name="Test User", email="test@example.com")
        u.set_password("Secret123!")
        self.assertNotEqual(u.password_hash, "Secret123!")
        self.assertTrue(u.check_password("Secret123!"))
        self.assertFalse(u.check_password("WrongPassword"))


if __name__ == "__main__":
    unittest.main()
