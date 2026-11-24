import re
import unittest
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from unittest.mock import patch

from app import create_app, db
from app.models.activity_log import ActivityLog
from app.models.user import User
from app.services.email import send_email


class RoleAuthenticationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="role-auth-test-secret",
            ADMIN_USERNAME="@admin",
            ADMIN_EMAIL="admin@localhost",
            ADMIN_PASSWORD="A12345678",
            WTF_CSRF_ENABLED=False
        )
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.client.get("/auth/login")
        self.admin = User.query.filter_by(username="@admin").one()
        self.admin.failed_login_attempts = 0
        self.admin.login_locked_until = None
        db.session.commit()
        self._remove_test_users()

        self.user = User(
            name="Role Test User",
            username="role_test_user",
            email="role_test_user@example.com"
        )
        self.user.set_password("Password123!")
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        self._remove_test_users()
        db.session.remove()
        self.app_context.pop()

    def _remove_test_users(self):
        emails = [
            "role_test_user@example.com",
            "role_other_user@example.com",
            "imposter@example.com",
            "new_user@example.com",
            "existing@example.com"
        ]
        users = User.query.filter(User.email.in_(emails)).all()
        user_ids = [user.id for user in users]
        ActivityLog.query.filter(
            ActivityLog.event_type == "user_status_changed",
            ActivityLog.description.like("%role_test_user%")
        ).delete(synchronize_session=False)
        ActivityLog.query.filter(
            ActivityLog.event_type == "temporary_password_issued",
            ActivityLog.description.like("%role_test_user%")
        ).delete(synchronize_session=False)
        if user_ids:
            ActivityLog.query.filter(ActivityLog.user_id.in_(user_ids)).delete(
                synchronize_session=False
            )
            for user in users:
                db.session.delete(user)
            db.session.commit()

    def _login_user(self, client=None):
        client = client or self.client
        return client.post(
            "/auth/login",
            data={
                "email": self.user.email,
                "password": "Password123!"
            }
        )

    def _temporary_password_from_response(self, response):
        match = re.search(
            rb'<code id="temporary-password"[^>]*>([A-Za-z0-9_-]+)</code>',
            response.data
        )
        self.assertIsNotNone(match, response.data)
        return match.group(1).decode()

    def _sign_in_admin(self, client=None, endpoint="/admin/login"):
        client = client or self.app.test_client()
        response = client.post(
            endpoint,
            data={"identifier": "@admin", "password": "A12345678"}
        )
        self.assertEqual(response.status_code, 302, response.data)
        self.assertTrue(response.location.endswith("/admin/dashboard"))
        return client.get("/admin/dashboard")

    def test_default_admin_is_created_once_with_a_hash(self):
        self.assertEqual(self.admin.role, "admin")
        self.assertTrue(self.admin.check_password("A12345678"))
        self.assertNotEqual(self.admin.password_hash, "A12345678")

        original_hash = self.admin.password_hash
        original_username = self.admin.username
        original_email = self.admin.email
        self.admin.set_password("RotatedAdmin123!")
        self.admin.username = "renamed_admin"
        self.admin.email = "renamed-admin@example.com"
        db.session.commit()

        try:
            restarted_app = create_app()
            restarted_app.config.update(
                TESTING=True,
                SECRET_KEY="role-auth-test-secret",
                ADMIN_USERNAME="@admin",
                ADMIN_EMAIL="admin@localhost",
                ADMIN_PASSWORD="A12345678",
                WTF_CSRF_ENABLED=False
            )
            with restarted_app.app_context():
                restarted_app.test_client().get("/auth/login")
                persisted_admin = User.query.filter_by(
                    username="renamed_admin"
                ).one()
                self.assertEqual(
                    User.query.filter_by(role="admin").count(),
                    1
                )
                self.assertEqual(persisted_admin.email, "renamed-admin@example.com")
                self.assertTrue(persisted_admin.check_password("RotatedAdmin123!"))
                self.assertFalse(persisted_admin.check_password("A12345678"))
        finally:
            self.admin.password_hash = original_hash
            self.admin.username = original_username
            self.admin.email = original_email
            db.session.commit()

    def test_registration_cannot_claim_admin_username_or_role(self):
        response = self.client.post(
            "/auth/register",
            data={
                "name": "Imposter",
                "username": "@admin",
                "email": "imposter@example.com",
                "password": "Password123!"
            },
            follow_redirects=True
        )
        self.assertIn(b"reserved", response.data.lower())
        self.assertIsNone(User.query.filter_by(email="imposter@example.com").first())

        response = self.client.post(
            "/auth/register",
            data={
                "name": "New User",
                "username": "new_user",
                "email": "new_user@example.com",
                "password": "Password123!",
                "role": "admin"
            }
        )
        registered = User.query.filter_by(username="new_user").one()
        self.assertEqual(registered.role, "user")
        self.assertEqual(response.status_code, 302)

    def test_users_are_redirected_away_from_admin_routes(self):
        response = self._login_user()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/dashboard"))

        response = self.client.get("/admin/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/dashboard"))

        response = self.client.post(
            f"/admin/users/{self.admin.id}/toggle"
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.admin.active)

    def test_anonymous_admin_route_uses_admin_login(self):
        response = self.app.test_client().get("/admin/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/admin/login"))

    def test_user_dashboard_uses_sidebar_and_personal_greeting(self):
        response = self._login_user()
        self.assertEqual(response.status_code, 302)

        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'class="app-sidebar', response.data)
        self.assertIn(
            b'<h1 class="welcome-title" id="dashboard-welcome-title">Welcome</h1>',
            response.data
        )
        self.assertIn(b"Hello, Role Test User!", response.data)

    def test_admin_can_sign_in_from_standard_login(self):
        for endpoint in ("/auth/login", "/admin/login"):
            admin_client = self.app.test_client()
            response = admin_client.post(
                endpoint,
                data={"identifier": "@admin", "password": "A12345678"}
            )
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.location.endswith("/admin/dashboard"))
            self.assertEqual(
                admin_client.get("/admin/dashboard").status_code,
                200
            )
            self.assertEqual(
                admin_client.get("/admin/mfa/setup").status_code,
                404
            )
            self.assertEqual(
                admin_client.get("/admin/mfa/verify").status_code,
                404
            )

    def test_user_login_locks_after_repeated_failures(self):
        for _ in range(5):
            self.client.post(
                "/auth/login",
                data={"identifier": self.user.username, "password": "WrongPassword"},
                environ_overrides={"REMOTE_ADDR": "198.51.100.10"}
            )

        db.session.refresh(self.user)
        self.assertIsNotNone(self.user.login_locked_until)
        response = self.client.post(
            "/auth/login",
            data={"identifier": self.user.username, "password": "Password123!"},
            environ_overrides={"REMOTE_ADDR": "198.51.100.11"},
            follow_redirects=True
        )
        self.assertIn(b"temporarily locked", response.data)

        self.user.login_locked_until = (
            datetime.now(timezone.utc).replace(tzinfo=None)
            - timedelta(seconds=1)
        )
        db.session.commit()
        response = self.client.post(
            "/auth/login",
            data={"identifier": self.user.username, "password": "Password123!"},
            environ_overrides={"REMOTE_ADDR": "198.51.100.12"}
        )
        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.user)
        self.assertIsNone(self.user.login_locked_until)
        self.assertEqual(self.user.failed_login_attempts, 0)

    def test_admin_can_view_dashboard_and_deactivate_only_users(self):
        admin_client = self.app.test_client()
        response = self._sign_in_admin(admin_client)
        self.assertEqual(response.status_code, 200)

        response = admin_client.get("/admin/dashboard")
        self.assertEqual(response.status_code, 200, response.location)
        self.assertIn(b"Hello, Administrator!", response.data)
        self.assertIn(b"Registered accounts", response.data)
        self.assertIn(b"Recent application activity", response.data)
        self.assertIn(b"Generate temporary password", response.data)

        response = admin_client.post(f"/admin/users/{self.user.id}/toggle")
        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.user)
        self.assertFalse(self.user.active)

        user_client = self.app.test_client()
        with self.app.app_context():
            response = user_client.post(
                "/auth/login",
                data={"email": self.user.email, "password": "Password123!"}
            )
            self.assertEqual(response.status_code, 200, response.location)
            self.assertIn(b"Sign-in failed", response.data)

        response = admin_client.post(f"/admin/users/{self.admin.id}/toggle")
        self.assertEqual(response.status_code, 403)
        db.session.refresh(self.admin)
        self.assertTrue(self.admin.active)

    def test_admin_issued_password_requires_change_and_is_invalidated(self):
        admin_client = self.app.test_client()
        self._sign_in_admin(admin_client)

        self.app.config["MAIL_SERVER"] = None
        with patch("app.services.email.send_email") as send_email:
            response = admin_client.post(
                "/admin/issue-temporary-password",
                data={"email": self.user.email}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn(self.user.email.encode(), response.data)
        send_email.assert_not_called()
        temporary_password = self._temporary_password_from_response(response)
        self.assertNotEqual(self.user.password_hash, temporary_password)
        self.assertTrue(self.user.check_password(temporary_password))
        self.assertTrue(self.user.must_change_password)
        self.assertIsNone(self.user.temporary_password_used_at)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        self.assertGreater(self.user.temporary_password_expires_at, now)
        self.assertLessEqual(
            self.user.temporary_password_expires_at,
            now + timedelta(hours=24, seconds=1)
        )

        client_app = create_app()
        client_app.config.update(
            TESTING=True,
            SECRET_KEY="role-auth-test-secret",
            ADMIN_USERNAME="@admin",
            ADMIN_EMAIL="admin@localhost",
            ADMIN_PASSWORD="A12345678",
            WTF_CSRF_ENABLED=False
        )
        temporary_client = client_app.test_client()
        response = temporary_client.post(
            "/auth/login",
            data={
                "identifier": self.user.username,
                "password": temporary_password
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response.location.endswith("/auth/change-password"),
            response.location
        )
        db.session.refresh(self.user)
        self.assertIsNotNone(self.user.temporary_password_used_at)

        response = temporary_client.get("/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/auth/change-password"))

        reused_client = client_app.test_client(use_cookies=False)
        response = reused_client.post(
            "/auth/login",
            data={
                "identifier": self.user.username,
                "password": temporary_password
            },
            follow_redirects=True
        )
        self.assertIn(b"already been used", response.data)

        response = temporary_client.post(
            "/auth/change-password",
            data={
                "new_password": temporary_password,
                "confirm_password": temporary_password
            },
            follow_redirects=True
        )
        self.assertIn(b"different from your temporary password", response.data)

        response = temporary_client.post(
            "/auth/change-password",
            data={
                "new_password": "NewClientPassword123!",
                "confirm_password": "NewClientPassword123!"
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/dashboard"))
        db.session.refresh(self.user)
        self.assertFalse(self.user.must_change_password)
        self.assertIsNone(self.user.temporary_password_expires_at)
        self.assertIsNone(self.user.temporary_password_used_at)
        self.assertFalse(self.user.check_password(temporary_password))
        self.assertTrue(self.user.check_password("NewClientPassword123!"))

        old_client = client_app.test_client(use_cookies=False)
        response = old_client.post(
            "/auth/login",
            data={
                "identifier": self.user.username,
                "password": temporary_password
            }
        )
        self.assertEqual(response.status_code, 200)

        new_client = client_app.test_client(use_cookies=False)
        response = new_client.post(
            "/auth/login",
            data={
                "identifier": self.user.email,
                "password": "NewClientPassword123!"
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/dashboard"))

    def test_expired_temporary_password_is_rejected(self):
        admin_client = self.app.test_client()
        self._sign_in_admin(admin_client)

        response = admin_client.post(
            "/admin/issue-temporary-password",
            data={"email": self.user.email}
        )
        temporary_password = self._temporary_password_from_response(response)
        self.user.temporary_password_expires_at = (
            datetime.now(timezone.utc).replace(tzinfo=None)
            - timedelta(seconds=1)
        )
        db.session.commit()

        client_app = create_app()
        client_app.config.update(
            TESTING=True,
            SECRET_KEY="role-auth-test-secret",
            ADMIN_USERNAME="@admin",
            ADMIN_EMAIL="admin@localhost",
            ADMIN_PASSWORD="A12345678",
            WTF_CSRF_ENABLED=False
        )
        response = client_app.test_client().post(
            "/auth/login",
            data={
                "identifier": self.user.username,
                "password": temporary_password
            },
            follow_redirects=True
        )

        self.assertIn(b"temporary password has expired", response.data)
        db.session.refresh(self.user)
        self.assertTrue(self.user.must_change_password)
        self.assertIsNone(self.user.temporary_password_used_at)

    def test_temporary_password_issue_looks_up_existing_client_by_email(self):
        admin_client = self.app.test_client()
        self._sign_in_admin(admin_client)
        original_hash = self.user.password_hash
        self.admin.email = "admin@example.com"
        db.session.commit()

        response = admin_client.post(
            "/admin/issue-temporary-password",
            data={"email": "wrong@example.com"},
            follow_redirects=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No business account was found", response.data)
        response = admin_client.post(
            "/admin/issue-temporary-password",
            data={"email": self.admin.email},
            follow_redirects=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No business account was found", response.data)
        self.assertEqual(self.user.password_hash, original_hash)
        self.assertFalse(self.user.must_change_password)

    def test_normal_user_cannot_issue_temporary_passwords(self):
        original_hash = self.user.password_hash
        self._login_user()

        response = self.client.post(
            "/admin/issue-temporary-password",
            data={"email": self.user.email}
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/dashboard"))
        self.assertEqual(self.user.password_hash, original_hash)
        self.assertFalse(self.user.must_change_password)

    def test_email_sender_refuses_unencrypted_smtp(self):
        self.app.config.update(
            MAIL_SERVER="smtp.example.com",
            MAIL_USE_TLS=False,
            MAIL_USE_SSL=False
        )
        message = EmailMessage()
        message["Subject"] = "Test"
        message["From"] = "sender@example.com"
        message["To"] = "client@example.com"
        message.set_content("Test message")

        with patch("app.services.email.smtplib.SMTP") as smtp:
            self.assertFalse(send_email(message, "test"))

        smtp.assert_not_called()

    def test_analysis_history_is_scoped_to_the_current_user(self):
        other = User(
            name="Other User",
            username="role_other_user",
            email="role_other_user@example.com"
        )
        other.set_password("Password123!")
        db.session.add(other)
        db.session.flush()
        db.session.add_all([
            ActivityLog(
                user_id=self.user.id,
                event_type="analytics_view",
                description="My private analysis"
            ),
            ActivityLog(
                user_id=other.id,
                event_type="analytics_view",
                description="Other private analysis"
            )
        ])
        db.session.commit()

        self._login_user()
        response = self.client.get("/analysis-history")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"My private analysis", response.data)
        self.assertNotIn(b"Other private analysis", response.data)

    def test_analysis_history_filters_dates_and_exports_safe_csv(self):
        other = User(
            name="Other User",
            username="role_other_user",
            email="role_other_user@example.com"
        )
        other.set_password("Password123!")
        db.session.add(other)
        db.session.flush()
        db.session.add_all([
            ActivityLog(
                user_id=self.user.id,
                event_type="ai_assistant",
                description="=SUM(1,2)",
                created_at=datetime(2026, 3, 10, 12, 0)
            ),
            ActivityLog(
                user_id=other.id,
                event_type="ai_assistant",
                description="Private other account report",
                created_at=datetime(2026, 3, 10, 12, 0)
            ),
            ActivityLog(
                user_id=self.user.id,
                event_type="analytics_view",
                description="Outside date range",
                created_at=datetime(2026, 4, 10, 12, 0)
            )
        ])
        db.session.commit()
        self._login_user()

        params = {
            "q": "SUM",
            "start_date": "2026-03-10",
            "end_date": "2026-03-10"
        }
        response = self.client.get("/analysis-history", query_string=params)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"=SUM(1,2)", response.data)
        self.assertNotIn(b"Outside date range", response.data)
        self.assertNotIn(b"Private other account report", response.data)

        response = self.client.get(
            "/analysis-history",
            query_string={**params, "export": "csv"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)
        self.assertIn(b"'=SUM(1,2)", response.data)
        self.assertNotIn(b"Private other account report", response.data)
    def test_profile_update_changes_name_and_business_handle(self):
        self._login_user()
        response = self.client.get("/auth/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Edit Profile", response.data)
        self.assertIn(b"Business Handle", response.data)
        self.assertIn(b'id="edit-profile-form"', response.data)
        self.assertNotIn(b'id="profile-email"', response.data)

        response = self.client.post(
            "/auth/profile",
            data={
                "name": "Updated User",
                "username": "updated_business"
            }
        )
        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.user)
        self.assertEqual(self.user.name, "Updated User")
        self.assertEqual(self.user.username, "updated_business")
        self.assertTrue(self.user.check_password("Password123!"))
        self.assertIsNone(
            User.query.filter_by(username="role_test_user").first()
        )

        self.client.post("/auth/logout")
        response = self.client.post(
            "/auth/login",
            data={
                "identifier": "updated_business",
                "password": "Password123!"
            }
        )
        self.assertEqual(response.status_code, 302)

        self.client.post("/auth/logout")
        response = self.client.post(
            "/auth/login",
            data={
                "identifier": "role_test_user",
                "password": "Password123!"
            }
        )
        self.assertEqual(response.status_code, 200, response.location)

    def test_profile_update_rejects_reserved_and_existing_business_handles(self):
        other = User(
            name="Other User",
            username="existing_business",
            email="role_other_user@example.com"
        )
        other.set_password("Password123!")
        db.session.add(other)
        db.session.commit()
        self._login_user()

        for handle in ("@admin", "existing_business", "invalid handle"):
            with self.subTest(handle=handle):
                response = self.client.post(
                    "/auth/profile",
                    data={"name": self.user.name, "username": handle},
                    follow_redirects=True
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Business Handle", response.data)
                db.session.refresh(self.user)
                self.assertEqual(self.user.username, "role_test_user")

    def test_admin_can_change_business_handle_and_email_from_profile(self):
        admin_client = self.app.test_client()
        self._sign_in_admin(admin_client)
        profile_response = admin_client.get("/auth/profile")
        self.assertIn(b'id="profile-email"', profile_response.data)
        original_username = self.admin.username
        original_email = self.admin.email

        try:
            response = admin_client.post(
                "/auth/profile",
                data={
                    "name": self.admin.name,
                    "username": "changed_admin",
                    "email": original_email
                },
                follow_redirects=True
            )

            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Your profile was updated.", response.data)
            db.session.refresh(self.admin)
            self.assertEqual(self.admin.username, "changed_admin")

            response = admin_client.post(
                "/auth/profile",
                data={
                    "name": self.admin.name,
                    "username": "changed_admin",
                    "email": "changed-admin@example.com"
                },
                follow_redirects=True
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Your profile was updated.", response.data)
            db.session.refresh(self.admin)
            self.assertEqual(self.admin.email, "changed-admin@example.com")
        finally:
            db.session.refresh(self.admin)
            self.admin.username = original_username
            self.admin.email = original_email
            db.session.commit()

    def test_admin_profile_rejects_invalid_or_duplicate_email(self):
        other = User(
            name="Other User",
            username="existing_business",
            email="existing@example.com"
        )
        other.set_password("Password123!")
        db.session.add(other)
        db.session.commit()
        admin_client = self.app.test_client()
        self._sign_in_admin(admin_client)

        for email, message in (
            ("invalid-email", b"Enter a valid email address."),
            ("existing@example.com", b"That email address is already in use.")
        ):
            with self.subTest(email=email):
                response = admin_client.post(
                    "/auth/profile",
                    data={
                        "name": self.admin.name,
                        "username": "changed_admin",
                        "email": email
                    },
                    follow_redirects=True
                )
                self.assertIn(message, response.data)
                db.session.refresh(self.admin)
                self.assertEqual(self.admin.username, "@admin")
                self.assertEqual(self.admin.email, "admin@localhost")

    def test_change_password_updates_hash_and_authentication(self):
        self._login_user()
        response = self.client.post(
            "/auth/change-password",
            data={
                "current_password": "Password123!",
                "new_password": "ChangedPassword123!",
                "confirm_password": "ChangedPassword123!"
            },
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your password has been updated successfully.", response.data)
        db.session.refresh(self.user)
        self.assertTrue(self.user.check_password("ChangedPassword123!"))
        self.assertFalse(self.user.check_password("Password123!"))

        old_login = self.app.test_client(use_cookies=False)
        with self.app.app_context():
            response = old_login.post(
                "/auth/login",
                data={"email": self.user.email, "password": "Password123!"}
            )
        self.assertEqual(response.status_code, 200)

        new_login = self.app.test_client(use_cookies=False)
        with self.app.app_context():
            response = new_login.post(
                "/auth/login",
                data={"email": self.user.email, "password": "ChangedPassword123!"}
            )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/dashboard"))

    def test_change_password_rejects_incorrect_current_password(self):
        self._login_user()
        response = self.client.post(
            "/auth/change-password",
            data={
                "current_password": "WrongPassword123!",
                "new_password": "ChangedPassword123!",
                "confirm_password": "ChangedPassword123!"
            },
            follow_redirects=True
        )
        self.assertIn(b"Current password is incorrect.", response.data)
        self.assertTrue(self.user.check_password("Password123!"))
        self.assertFalse(self.user.check_password("ChangedPassword123!"))

    def test_change_password_rejects_mismatch_and_short_password(self):
        self._login_user()
        mismatch_response = self.client.post(
            "/auth/change-password",
            data={
                "current_password": "Password123!",
                "new_password": "ChangedPassword123!",
                "confirm_password": "DifferentPassword123!"
            },
            follow_redirects=True
        )
        self.assertIn(b"New password and confirmation do not match.", mismatch_response.data)

        short_response = self.client.post(
            "/auth/change-password",
            data={
                "current_password": "Password123!",
                "new_password": "Short123!",
                "confirm_password": "Short123!"
            },
            follow_redirects=True
        )
        self.assertIn(b"between 12 and 128 characters", short_response.data)
        self.assertTrue(self.user.check_password("Password123!"))

    def test_client_password_route_cannot_target_another_account(self):
        self._login_user()
        admin_hash = self.admin.password_hash
        response = self.client.post(
            "/auth/change-password",
            data={
                "user_id": self.admin.id,
                "current_password": "Password123!",
                "new_password": "ChangedPassword123!",
                "confirm_password": "ChangedPassword123!"
            }
        )
        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.admin)
        self.assertEqual(self.admin.password_hash, admin_hash)
        self.assertTrue(self.user.check_password("ChangedPassword123!"))

    def test_login_page_has_admin_email_request_instead_of_forgot_link(self):
        response = self.client.get("/auth/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Forgot Password?", response.data)
        self.assertIn(b"adminaibia@gmail.com", response.data)
        self.assertIn(
            b"subject=AI%20BIA%20%E2%80%93%20Business%20Account%20Password%20Recovery%20Request",
            response.data
        )
        self.assertIn(b"%5BRegistered%20Business%20Name%5D", response.data)
        self.assertIn(b"%5BRegistered%20Email%5D", response.data)
        self.assertIn(b"%5BBusiness%20Handle%5D", response.data)
        self.assertIn(b"Business Name", response.data)
        self.assertNotIn(b"Request Password from Admin", response.data)

    def test_deactivated_user_session_loses_access(self):
        user_client = self.app.test_client()
        user_id = self.user.id

        with self.app.app_context():
            response = user_client.post(
                "/auth/login",
                data={"email": self.user.email, "password": "Password123!"}
            )
            self.assertEqual(response.status_code, 302)

        admin_client = self.app.test_client()
        with self.app.app_context():
            response = self._sign_in_admin(admin_client)
            self.assertEqual(response.status_code, 200)
            admin_client.post(f"/admin/users/{user_id}/toggle")

        with self.app.app_context():
            response = user_client.get("/dashboard")
            self.assertEqual(response.status_code, 302)
            self.assertIn("/auth/login", response.location)

    def test_csrf_rejects_mutating_requests_without_a_token(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        response = self.client.post(
            "/auth/login",
            data={"email": self.user.email, "password": "Password123!"}
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
