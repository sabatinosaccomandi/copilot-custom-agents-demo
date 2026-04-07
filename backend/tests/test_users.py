"""Tests for the ``/users`` Blueprint.

Endpoint matrix
---------------
POST   /users/           – TestUserRegistration
POST   /users/login      – TestUserLogin
GET    /users/           – TestListUsers
GET    /users/<id>       – TestGetUser
DELETE /users/<id>       – TestDeleteUser
GET    /users/search     – TestSearchUsers

Each class is self-contained: fixtures from conftest.py are injected by
pytest and the in-memory SQLite database is reset between every test
function, so tests are fully independent of execution order.
"""
from __future__ import annotations

import pytest


# ===========================================================================
# POST /users/  — registration
# ===========================================================================

class TestUserRegistration:
    """POST /users/ — create a new user account."""

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_happy_path_returns_201(self, client):
        resp = client.post(
            "/users/",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "securepass",
            },
        )
        assert resp.status_code == 201

    def test_happy_path_response_body_contains_id_and_username(self, client):
        resp = client.post(
            "/users/",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "securepass",
            },
        )
        data = resp.get_json()
        assert "id" in data
        assert data["username"] == "newuser"
        assert isinstance(data["id"], int)

    def test_response_never_exposes_password_hash(self, client):
        resp = client.post(
            "/users/",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "securepass",
            },
        )
        assert "password" not in resp.get_json()

    def test_newly_registered_user_can_log_in(self, client):
        client.post(
            "/users/",
            json={
                "username": "loginready",
                "email": "loginready@example.com",
                "password": "securepass",
            },
        )
        resp = client.post(
            "/users/login",
            json={"username": "loginready", "password": "securepass"},
        )
        assert resp.status_code == 200
        assert "token" in resp.get_json()

    def test_role_is_always_forced_to_user_even_when_admin_sent(self, client):
        """The service must ignore any ``role`` field in the request body.

        Verify by logging in and then attempting an admin-only action — the
        request should be rejected with 403, proving the role was not
        elevated to ``"admin"``.
        """
        client.post(
            "/users/",
            json={
                "username": "wannabeadmin",
                "email": "wannabe@example.com",
                "password": "password123",
                "role": "admin",  # must be ignored
            },
        )
        login = client.post(
            "/users/login",
            json={"username": "wannabeadmin", "password": "password123"},
        )
        token = login.get_json()["token"]
        # Attempt an admin-only write on /products/ — must be 403, not 201.
        resp = client.post(
            "/products/",
            json={"name": "Hack", "price": 1.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_email_is_normalised_to_lowercase_before_storage(self, client):
        """Registration with UPPER@CASE.COM and a follow-up registration with
        the same address in lower case must yield a 409 Conflict, proving the
        first registration normalised the email.
        """
        client.post(
            "/users/",
            json={
                "username": "caseuser1",
                "email": "UPPER@EXAMPLE.COM",
                "password": "securepass",
            },
        )
        resp = client.post(
            "/users/",
            json={
                "username": "caseuser2",
                "email": "upper@example.com",  # same after lower-casing
                "password": "securepass",
            },
        )
        assert resp.status_code == 409

    # ------------------------------------------------------------------
    # Missing / empty fields
    # ------------------------------------------------------------------

    def test_missing_username_returns_422_with_field_error(self, client):
        resp = client.post(
            "/users/",
            json={"email": "new@example.com", "password": "securepass"},
        )
        assert resp.status_code == 422
        errors = resp.get_json().get("errors", {})
        assert "username" in errors

    def test_missing_email_returns_422_with_field_error(self, client):
        resp = client.post(
            "/users/",
            json={"username": "newuser", "password": "securepass"},
        )
        assert resp.status_code == 422
        assert "email" in resp.get_json().get("errors", {})

    def test_missing_password_returns_422_with_field_error(self, client):
        resp = client.post(
            "/users/",
            json={"username": "newuser", "email": "new@example.com"},
        )
        assert resp.status_code == 422
        assert "password" in resp.get_json().get("errors", {})

    def test_all_three_fields_missing_returns_422_with_all_errors(self, client):
        # ``require_json_body`` rejects an empty dict because ``not {} == True``;
        # send a non-empty body that omits all three expected fields so that
        # execution reaches ``user_service.create_user`` and triggers the full
        # per-field ValidationError.
        resp = client.post("/users/", json={"unrelated": "value"})
        assert resp.status_code == 422
        errors = resp.get_json().get("errors", {})
        assert "username" in errors
        assert "email" in errors
        assert "password" in errors

    def test_empty_string_username_returns_422(self, client):
        resp = client.post(
            "/users/",
            json={"username": "", "email": "new@example.com", "password": "securepass"},
        )
        assert resp.status_code == 422
        assert "username" in resp.get_json().get("errors", {})

    def test_whitespace_only_username_returns_422(self, client):
        resp = client.post(
            "/users/",
            json={
                "username": "   ",
                "email": "new@example.com",
                "password": "securepass",
            },
        )
        assert resp.status_code == 422
        assert "username" in resp.get_json().get("errors", {})

    # ------------------------------------------------------------------
    # Username length boundaries
    # ------------------------------------------------------------------

    def test_username_one_char_returns_422(self, client):
        resp = client.post(
            "/users/",
            json={"username": "x", "email": "x@x.com", "password": "securepass"},
        )
        assert resp.status_code == 422
        assert "username" in resp.get_json().get("errors", {})

    def test_username_two_chars_returns_422(self, client):
        resp = client.post(
            "/users/",
            json={"username": "xy", "email": "xy@x.com", "password": "securepass"},
        )
        assert resp.status_code == 422
        assert "username" in resp.get_json().get("errors", {})

    def test_username_exactly_three_chars_is_accepted(self, client):
        resp = client.post(
            "/users/",
            json={"username": "abc", "email": "abc@x.com", "password": "securepass"},
        )
        assert resp.status_code == 201

    def test_username_81_chars_returns_422(self, client):
        resp = client.post(
            "/users/",
            json={
                "username": "x" * 81,
                "email": "long@x.com",
                "password": "securepass",
            },
        )
        assert resp.status_code == 422
        assert "username" in resp.get_json().get("errors", {})

    def test_username_exactly_80_chars_is_accepted(self, client):
        resp = client.post(
            "/users/",
            json={
                "username": "u" * 80,
                "email": "eighty@x.com",
                "password": "securepass",
            },
        )
        assert resp.status_code == 201

    # ------------------------------------------------------------------
    # Email validation
    # ------------------------------------------------------------------

    def test_email_without_at_sign_returns_422(self, client):
        resp = client.post(
            "/users/",
            json={
                "username": "newuser",
                "email": "notanemail",
                "password": "securepass",
            },
        )
        assert resp.status_code == 422
        assert "email" in resp.get_json().get("errors", {})

    def test_email_without_domain_tld_returns_422(self, client):
        resp = client.post(
            "/users/",
            json={
                "username": "newuser",
                "email": "user@nodot",
                "password": "securepass",
            },
        )
        assert resp.status_code == 422
        assert "email" in resp.get_json().get("errors", {})

    def test_email_with_spaces_returns_422(self, client):
        resp = client.post(
            "/users/",
            json={
                "username": "newuser",
                "email": "user @example.com",
                "password": "securepass",
            },
        )
        assert resp.status_code == 422
        assert "email" in resp.get_json().get("errors", {})

    # ------------------------------------------------------------------
    # Password length boundaries
    # ------------------------------------------------------------------

    def test_password_7_chars_returns_422(self, client):
        resp = client.post(
            "/users/",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "short7c",
            },
        )
        assert resp.status_code == 422
        assert "password" in resp.get_json().get("errors", {})

    def test_password_exactly_8_chars_is_accepted(self, client):
        resp = client.post(
            "/users/",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "exactly8",
            },
        )
        assert resp.status_code == 201

    def test_empty_password_returns_422(self, client):
        resp = client.post(
            "/users/",
            json={"username": "newuser", "email": "new@example.com", "password": ""},
        )
        assert resp.status_code == 422
        assert "password" in resp.get_json().get("errors", {})

    # ------------------------------------------------------------------
    # Conflict / uniqueness
    # ------------------------------------------------------------------

    def test_duplicate_username_returns_409(self, client, regular_user):
        user_dict, _ = regular_user
        resp = client.post(
            "/users/",
            json={
                "username": user_dict["username"],  # already exists
                "email": "other@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 409
        assert "error" in resp.get_json()

    def test_duplicate_email_returns_409(self, client, regular_user):
        user_dict, _ = regular_user
        resp = client.post(
            "/users/",
            json={
                "username": "brandnewuser",
                "email": user_dict["email"],  # already exists
                "password": "password123",
            },
        )
        assert resp.status_code == 409
        assert "error" in resp.get_json()

    # ------------------------------------------------------------------
    # Malformed requests
    # ------------------------------------------------------------------

    def test_non_json_content_type_returns_400(self, client):
        resp = client.post(
            "/users/",
            data="username=x&email=x@x.com&password=secret",
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_empty_body_returns_400(self, client):
        resp = client.post(
            "/users/",
            data="",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_malformed_json_returns_400(self, client):
        resp = client.post(
            "/users/",
            data="{not valid json",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_empty_json_object_returns_400(self, client):
        """``require_json_body`` checks ``if not data``; an empty dict ``{}``
        is falsy, so it is rejected with 400 before the service layer runs.
        This is distinct from missing individual fields (422): the entire
        body is considered absent.
        """
        resp = client.post("/users/", json={})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_username_surrounding_whitespace_is_stripped_on_registration(
        self, client
    ):
        """``user_service.create_user`` calls ``username.strip()`` before
        validation.  A username wrapped in spaces should be stored without
        them as long as the stripped form is at least 3 characters.
        """
        resp = client.post(
            "/users/",
            json={
                "username": "  trimmed  ",
                "email": "trimmed@example.com",
                "password": "securepass",
            },
        )
        assert resp.status_code == 201
        assert resp.get_json()["username"] == "trimmed"

    def test_extra_fields_in_registration_body_are_silently_ignored(self, client):
        """Keys beyond ``username``, ``email``, and ``password`` are simply
        not read by the route or service and must not cause any error.
        The ``role`` key in particular must still be forced to ``"user"``.
        """
        resp = client.post(
            "/users/",
            json={
                "username": "extrauser",
                "email": "extra@example.com",
                "password": "securepass",
                "role": "admin",   # must be ignored — forced to "user"
                "id": 999,         # must be ignored
                "foo": "bar",      # completely unrecognised key
            },
        )
        assert resp.status_code == 201


# ===========================================================================
# POST /users/login  — authentication
# ===========================================================================

class TestUserLogin:
    """POST /users/login — exchange credentials for a signed bearer token."""

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_valid_credentials_return_200(self, client, regular_user):
        user_dict, password = regular_user
        resp = client.post(
            "/users/login",
            json={"username": user_dict["username"], "password": password},
        )
        assert resp.status_code == 200

    def test_response_contains_token_string(self, client, regular_user):
        user_dict, password = regular_user
        resp = client.post(
            "/users/login",
            json={"username": user_dict["username"], "password": password},
        )
        data = resp.get_json()
        assert "token" in data
        assert isinstance(data["token"], str)
        assert len(data["token"]) > 10  # non-trivial signed token

    def test_token_grants_access_to_protected_route(self, client, regular_user):
        """The returned token must satisfy ``require_auth`` on GET /users/."""
        user_dict, password = regular_user
        login = client.post(
            "/users/login",
            json={"username": user_dict["username"], "password": password},
        )
        token = login.get_json()["token"]
        resp = client.get(
            "/users/", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200

    # ------------------------------------------------------------------
    # Bad credentials
    # ------------------------------------------------------------------

    def test_wrong_password_returns_401(self, client, regular_user):
        user_dict, _ = regular_user
        resp = client.post(
            "/users/login",
            json={"username": user_dict["username"], "password": "wrongpass"},
        )
        assert resp.status_code == 401
        assert "error" in resp.get_json()

    def test_nonexistent_username_returns_401(self, client):
        resp = client.post(
            "/users/login",
            json={"username": "ghostuser", "password": "somepassword"},
        )
        assert resp.status_code == 401

    def test_error_message_is_deliberately_vague(self, client, regular_user):
        """Both 'wrong password' and 'unknown user' must return the same message
        to prevent username enumeration via timing or response differences.
        """
        user_dict, _ = regular_user
        bad_pass = client.post(
            "/users/login",
            json={"username": user_dict["username"], "password": "WRONG"},
        )
        no_user = client.post(
            "/users/login",
            json={"username": "nobody", "password": "WRONG"},
        )
        assert bad_pass.get_json()["error"] == no_user.get_json()["error"]

    def test_password_off_by_one_char_returns_401(self, client, regular_user):
        user_dict, password = regular_user
        resp = client.post(
            "/users/login",
            json={"username": user_dict["username"], "password": password[:-1]},
        )
        assert resp.status_code == 401

    # ------------------------------------------------------------------
    # Missing / empty fields
    # ------------------------------------------------------------------

    def test_missing_username_field_returns_400(self, client):
        resp = client.post("/users/login", json={"password": "somepassword"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_missing_password_field_returns_400(self, client):
        resp = client.post("/users/login", json={"username": "someuser"})
        assert resp.status_code == 400

    def test_empty_string_username_returns_400(self, client):
        resp = client.post(
            "/users/login", json={"username": "", "password": "somepassword"}
        )
        assert resp.status_code == 400

    def test_empty_string_password_returns_400(self, client):
        resp = client.post(
            "/users/login", json={"username": "someuser", "password": ""}
        )
        assert resp.status_code == 400

    def test_whitespace_only_password_returns_401(self, client):
        """A whitespace-only password (e.g. ``"   "``) is a non-empty string,
        so it passes the route's required-field guard (``not "   "`` is False).
        The route does *not* strip the password before the check, so execution
        proceeds to ``authenticate_user``, which compares the value against
        bcrypt hashes and finds no match — yielding 401, not 400.
        """
        resp = client.post(
            "/users/login",
            json={"username": "someuser", "password": "   "},
        )
        assert resp.status_code == 401

    # ------------------------------------------------------------------
    # Malformed requests
    # ------------------------------------------------------------------

    def test_non_json_body_returns_400(self, client):
        resp = client.post(
            "/users/login",
            data="username=u&password=p",
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 400

    def test_empty_body_returns_400(self, client):
        resp = client.post(
            "/users/login", data="", content_type="application/json"
        )
        assert resp.status_code == 400

    def test_empty_json_object_returns_400(self, client):
        """An empty JSON object ``{}`` is falsy — ``require_json_body`` rejects
        it with 400 before the route's credential-field guard even runs.
        """
        resp = client.post("/users/login", json={})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_username_with_surrounding_whitespace_still_authenticates(
        self, client, regular_user
    ):
        """The login route calls ``username.strip()`` before lookup.  Credentials
        submitted with leading/trailing spaces around the username must still
        authenticate successfully when the underlying account exists.
        """
        user_dict, password = regular_user
        resp = client.post(
            "/users/login",
            json={"username": f"  {user_dict['username']}  ", "password": password},
        )
        assert resp.status_code == 200
        assert "token" in resp.get_json()

    def test_correct_username_wrong_case_returns_401(self, client, regular_user):
        """Username lookup is case-sensitive (exact SQL equality match).
        Sending ``REGULARUSER`` when the stored name is ``regularuser``
        must return 401.
        """
        user_dict, password = regular_user
        resp = client.post(
            "/users/login",
            json={"username": user_dict["username"].upper(), "password": password},
        )
        assert resp.status_code == 401


# ===========================================================================
# GET /users/  — list all users
# ===========================================================================

class TestListUsers:
    """GET /users/ — list all registered accounts (requires auth)."""

    def test_returns_200_with_valid_token(self, client, user_token):
        resp = client.get(
            "/users/", headers={"Authorization": f"Bearer {user_token}"}
        )
        assert resp.status_code == 200

    def test_returns_json_array(self, client, user_token):
        resp = client.get(
            "/users/", headers={"Authorization": f"Bearer {user_token}"}
        )
        assert isinstance(resp.get_json(), list)

    def test_empty_database_returns_empty_array(self, client, user_token):
        """When only the token-owner exists the list is still non-empty, but
        calling with a freshly minted token on a DB that ONLY has the owning
        user should return exactly one entry.  What matters here is the shape
        — an array — not the length.
        """
        resp = client.get(
            "/users/", headers={"Authorization": f"Bearer {user_token}"}
        )
        data = resp.get_json()
        assert isinstance(data, list)

    def test_response_objects_have_expected_keys(self, client, regular_user, user_token):
        resp = client.get(
            "/users/", headers={"Authorization": f"Bearer {user_token}"}
        )
        for user in resp.get_json():
            assert "id" in user
            assert "username" in user
            assert "email" in user
            assert "role" in user

    def test_response_objects_never_contain_password(self, client, user_token):
        resp = client.get(
            "/users/", headers={"Authorization": f"Bearer {user_token}"}
        )
        for user in resp.get_json():
            assert "password" not in user

    def test_multiple_users_are_all_returned(self, client, regular_user, admin_user, user_token):
        resp = client.get(
            "/users/", headers={"Authorization": f"Bearer {user_token}"}
        )
        usernames = {u["username"] for u in resp.get_json()}
        assert "regularuser" in usernames
        assert "adminuser" in usernames

    # ------------------------------------------------------------------
    # Authentication guard
    # ------------------------------------------------------------------

    def test_no_auth_header_returns_401(self, client):
        resp = client.get("/users/")
        assert resp.status_code == 401
        assert "error" in resp.get_json()

    def test_malformed_bearer_token_returns_401(self, client):
        resp = client.get(
            "/users/", headers={"Authorization": "Bearer this.is.garbage"}
        )
        assert resp.status_code == 401

    def test_missing_bearer_prefix_returns_401(self, client, user_token):
        # Header present but without "Bearer " prefix
        resp = client.get(
            "/users/", headers={"Authorization": user_token}
        )
        assert resp.status_code == 401

    def test_empty_authorization_header_returns_401(self, client):
        resp = client.get("/users/", headers={"Authorization": ""})
        assert resp.status_code == 401


# ===========================================================================
# GET /users/<id>  — get single user
# ===========================================================================

class TestGetUser:
    """GET /users/<id> — fetch one user by primary key (requires auth)."""

    def test_happy_path_returns_200(self, client, regular_user, user_token):
        user_dict, _ = regular_user
        resp = client.get(
            f"/users/{user_dict['id']}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200

    def test_response_contains_correct_user_data(self, client, regular_user, user_token):
        user_dict, _ = regular_user
        resp = client.get(
            f"/users/{user_dict['id']}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        data = resp.get_json()
        assert data["id"] == user_dict["id"]
        assert data["username"] == user_dict["username"]
        assert data["email"] == user_dict["email"]
        assert data["role"] == user_dict["role"]

    def test_response_never_contains_password(self, client, regular_user, user_token):
        user_dict, _ = regular_user
        resp = client.get(
            f"/users/{user_dict['id']}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert "password" not in resp.get_json()

    def test_nonexistent_id_returns_404(self, client, user_token):
        resp = client.get(
            "/users/99999",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_no_auth_returns_401(self, client, regular_user):
        user_dict, _ = regular_user
        resp = client.get(f"/users/{user_dict['id']}")
        assert resp.status_code == 401

    def test_admin_can_fetch_other_user(self, client, regular_user, admin_token):
        user_dict, _ = regular_user
        resp = client.get(
            f"/users/{user_dict['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["id"] == user_dict["id"]

    def test_non_integer_id_in_url_returns_404(self, client, user_token):
        """Flask's ``<int:user_id>`` URL converter rejects non-numeric path
        segments; the request falls through to the global 404 handler.
        """
        resp = client.get(
            "/users/notanumber",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_zero_id_returns_404(self, client, user_token):
        """Auto-increment PKs start at 1; ID 0 should never exist."""
        resp = client.get(
            "/users/0",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 404
        assert "error" in resp.get_json()


# ===========================================================================
# DELETE /users/<id>  — delete user
# ===========================================================================

class TestDeleteUser:
    """DELETE /users/<id> — remove a user account (requires auth + ownership
    or admin role).
    """

    def test_admin_can_delete_any_user(self, client, regular_user, admin_token):
        user_dict, _ = regular_user
        resp = client.delete(
            f"/users/{user_dict['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.get_json() == {"message": "Deleted"}

    def test_user_can_delete_own_account(self, client, regular_user, user_token):
        user_dict, _ = regular_user
        resp = client.delete(
            f"/users/{user_dict['id']}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200
        assert resp.get_json() == {"message": "Deleted"}

    def test_user_cannot_delete_a_different_user_returns_403(
        self, client, regular_user, user_token
    ):
        # Create a second user inline so no extra fixture dependency is needed.
        create = client.post(
            "/users/",
            json={
                "username": "victim",
                "email": "victim@example.com",
                "password": "password123",
            },
        )
        victim_id = create.get_json()["id"]

        resp = client.delete(
            f"/users/{victim_id}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403
        assert resp.get_json() == {"error": "Forbidden"}

    def test_delete_nonexistent_user_as_admin_returns_404(
        self, client, admin_token
    ):
        resp = client.delete(
            "/users/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_no_auth_returns_401(self, client, regular_user):
        user_dict, _ = regular_user
        resp = client.delete(f"/users/{user_dict['id']}")
        assert resp.status_code == 401

    def test_deleted_user_can_no_longer_be_fetched(
        self, client, regular_user, admin_user, admin_token
    ):
        user_dict, _ = regular_user
        # Admin deletes the regular user.
        client.delete(
            f"/users/{user_dict['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Subsequent GET must return 404.
        resp = client.get(
            f"/users/{user_dict['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    def test_regular_user_token_cannot_delete_admin(
        self, client, admin_user, user_token
    ):
        admin_dict, _ = admin_user
        resp = client.delete(
            f"/users/{admin_dict['id']}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403

    def test_admin_can_delete_own_account(self, client, admin_user, admin_token):
        """An admin may delete their own account.  The ownership check is
        bypassed for admins (``role == "admin"``), so a self-delete is
        allowed and returns 200.
        """
        admin_dict, _ = admin_user
        resp = client.delete(
            f"/users/{admin_dict['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.get_json() == {"message": "Deleted"}

    def test_non_integer_id_in_url_returns_404(self, client, admin_token):
        """Flask's ``<int:user_id>`` converter rejects non-numeric URL segments
        regardless of authentication level.
        """
        resp = client.delete(
            "/users/notanumber",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    def test_double_delete_returns_404_on_second_attempt(
        self, client, regular_user, admin_token
    ):
        """Attempting to delete the same user twice must yield 404 on the
        second call — the resource no longer exists after the first delete.
        """
        user_dict, _ = regular_user
        client.delete(
            f"/users/{user_dict['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        resp = client.delete(
            f"/users/{user_dict['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404
        assert "error" in resp.get_json()


# ===========================================================================
# GET /users/search  — username search
# ===========================================================================

class TestSearchUsers:
    """GET /users/search?q=<term> — substring match on username (requires
    auth).
    """

    def test_happy_path_returns_200(self, client, regular_user, user_token):
        resp = client.get(
            "/users/search?q=regular",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200

    def test_returns_json_array(self, client, user_token):
        resp = client.get(
            "/users/search?q=x",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert isinstance(resp.get_json(), list)

    def test_response_objects_have_id_and_username_only(
        self, client, regular_user, user_token
    ):
        """Search results expose only ``id`` and ``username`` — not email or
        role — to minimise data leakage.
        """
        resp = client.get(
            "/users/search?q=regular",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        for item in resp.get_json():
            assert "id" in item
            assert "username" in item
            assert "email" not in item
            assert "role" not in item
            assert "password" not in item

    def test_matching_users_are_returned(self, client, regular_user, user_token):
        user_dict, _ = regular_user
        resp = client.get(
            f"/users/search?q={user_dict['username']}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        usernames = [u["username"] for u in resp.get_json()]
        assert user_dict["username"] in usernames

    def test_non_matching_query_returns_empty_list(self, client, regular_user, user_token):
        resp = client.get(
            "/users/search?q=zzz_no_match_zzz",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.get_json() == []

    def test_search_filters_correctly_between_multiple_users(
        self, client, regular_user, admin_user, user_token
    ):
        # "admin" appears in "adminuser" but NOT in "regularuser".
        resp = client.get(
            "/users/search?q=admin",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        usernames = [u["username"] for u in resp.get_json()]
        assert "adminuser" in usernames
        assert "regularuser" not in usernames

    def test_empty_query_returns_all_users(
        self, client, regular_user, admin_user, user_token
    ):
        resp = client.get(
            "/users/search?q=",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        usernames = [u["username"] for u in resp.get_json()]
        assert "regularuser" in usernames
        assert "adminuser" in usernames

    def test_missing_q_param_returns_all_users(
        self, client, regular_user, admin_user, user_token
    ):
        """When ``q`` is absent the service treats it as empty string."""
        resp = client.get(
            "/users/search",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_very_long_query_does_not_cause_server_error(
        self, client, user_token
    ):
        """The service caps query length at 100 chars — a 200-char query must
        not raise a 500.
        """
        long_q = "a" * 200
        resp = client.get(
            f"/users/search?q={long_q}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200

    def test_no_auth_returns_401(self, client):
        resp = client.get("/users/search?q=user")
        assert resp.status_code == 401

    def test_whitespace_only_query_returns_all_users(
        self, client, regular_user, admin_user, user_token
    ):
        """The service trims whitespace before building the LIKE pattern, so
        ``q="   "`` collapses to ``""`` and therefore returns all users — the
        same result as an absent ``q`` parameter.
        """
        resp = client.get(
            "/users/search?q=   ",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200
        usernames = [u["username"] for u in resp.get_json()]
        assert "regularuser" in usernames
        assert "adminuser" in usernames

    def test_single_character_query_returns_partial_matches(
        self, client, regular_user, user_token
    ):
        """A one-character query should still execute correctly.  ``q=r``
        must match ``regularuser`` (contains the letter ``r``).
        """
        resp = client.get(
            "/users/search?q=r",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200
        usernames = [u["username"] for u in resp.get_json()]
        assert "regularuser" in usernames

    def test_search_result_objects_contain_only_id_and_username(
        self, client, regular_user, user_token
    ):
        """Search results expose only ``id`` and ``username``; sensitive
        fields such as ``email``, ``role``, and ``password`` must be absent.
        """
        resp = client.get(
            "/users/search?q=regular",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        for item in resp.get_json():
            assert set(item.keys()) == {"id", "username"}

    def test_search_returns_correct_id_for_matched_user(
        self, client, regular_user, user_token
    ):
        user_dict, _ = regular_user
        resp = client.get(
            f"/users/search?q={user_dict['username']}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        ids = [u["id"] for u in resp.get_json()]
        assert user_dict["id"] in ids
