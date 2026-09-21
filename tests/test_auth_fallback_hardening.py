"""
MandiQ Authentication Fallback Hardening Test Suite.
Verifies backend enforcement of authentication decisions:
1. Correct credentials + server available -> HTTP 200 with valid JWT.
2. Wrong password + server 401 -> HTTP 401 Unauthorized (Invalid username or password).
3. Disabled account + server 401 -> HTTP 401 Unauthorized (User account is disabled).
4. Insufficient role / forbidden endpoint -> HTTP 403 Forbidden.
5. Forged offline tokens (offline_pwa_token_*) sent to backend -> HTTP 401 Unauthorized.
6. Verify token endpoint rejects forged offline tokens with valid=False.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.security import hash_password, create_access_jwt
from backend.app.models.user import User
from backend.app.models.mandi import Mandi
from backend.app.services.auth_service import ensure_default_operational_users


def setup_auth_fixture(db: Session):
    mandi = Mandi(
        name="Sehore Krishi Upaj Mandi",
        district="Sehore",
        state="Madhya Pradesh",
        daily_capacity_qt=2500.0,
        active_weighbridges=2,
        is_operational=True
    )
    db.add(mandi)
    db.commit()
    db.refresh(mandi)

    ensure_default_operational_users(db, mandi_id=mandi.mandi_id)

    # Add a disabled user for testing
    disabled_user = db.query(User).filter(User.username == "disabled_operator").first()
    if not disabled_user:
        disabled_user = User(
            username="disabled_operator",
            hashed_password=hash_password("Operator@MandiQ2026"),
            full_name="Disabled Operator",
            role="OPERATOR",
            mandi_id=mandi.mandi_id,
            is_active=False
        )
        db.add(disabled_user)
        db.commit()

    return mandi


def test_correct_credentials_returns_jwt_login(client: TestClient, db_session: Session):
    """1. Correct credentials + server available -> JWT login (HTTP 200)."""
    setup_auth_fixture(db_session)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "farmer", "password": "Farmer@MandiQ2026"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["username"] == "farmer"
    assert data["role"] == "FARMER"


def test_wrong_password_returns_server_401(client: TestClient, db_session: Session):
    """2. Wrong password + server 401 -> login fails with 401."""
    setup_auth_fixture(db_session)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "farmer", "password": "WrongPassword123"}
    )
    assert response.status_code == 401
    assert "invalid username or password" in response.json()["detail"].lower()


def test_disabled_account_returns_server_401(client: TestClient, db_session: Session):
    """3. Disabled account + server 401 -> login fails with 401."""
    setup_auth_fixture(db_session)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "disabled_operator", "password": "Operator@MandiQ2026"}
    )
    assert response.status_code == 401
    assert "disabled" in response.json()["detail"].lower()


def test_unauthorized_role_returns_server_403(client: TestClient, db_session: Session):
    """4. Server 403 -> access to unauthorized role endpoint fails with 403."""
    setup_auth_fixture(db_session)
    farmer_user = db_session.query(User).filter(User.username == "farmer").first()
    farmer_jwt = create_access_jwt({
        "sub": str(farmer_user.user_id),
        "user_id": farmer_user.user_id,
        "username": farmer_user.username,
        "role": farmer_user.role
    })

    # Farmer trying to access admin users endpoint -> 403
    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {farmer_jwt}"}
    )
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


def test_forged_offline_token_sent_to_backend_returns_401(client: TestClient, db_session: Session):
    """6. Forged offline token sent to backend -> 401."""
    setup_auth_fixture(db_session)
    forged_tokens = [
        "offline_pwa_token_farmer_1726000000",
        "offline_pwa_token_operator_1726000000",
        "offline_pwa_token_admin_1726000000",
        "offline_pwa_token_supervisor_1726000000",
    ]

    for token in forged_tokens:
        # 1. Protected /auth/me endpoint
        r_me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert r_me.status_code == 401
        assert "offline provisional" in r_me.json()["detail"].lower()

        # 2. Protected operational endpoint
        r_op = client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert r_op.status_code == 401
        assert "offline provisional" in r_op.json()["detail"].lower()

        # 3. Explicit /auth/verify endpoint
        r_verify = client.post(
            "/api/v1/auth/verify",
            json={"token": token}
        )
        assert r_verify.status_code == 200
        assert r_verify.json()["valid"] is False
        assert "offline provisional" in r_verify.json()["message"].lower()
