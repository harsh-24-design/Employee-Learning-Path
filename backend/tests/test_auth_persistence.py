import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.repositories.mongo_repository import repository

client = TestClient(app)

def test_user_registration_and_validation():
    # 1. Reject invalid email
    bad_email_res = client.post("/api/auth/register", json={
        "email": "invalid-email-format",
        "password": "validPassword123",
        "name": "Test User"
    })
    assert bad_email_res.status_code == 422 or bad_email_res.status_code == 400

    # 2. Reject short password (< 6 chars)
    short_pass_res = client.post("/api/auth/register", json={
        "email": f"valid_{uuid.uuid4().hex[:6]}@example.com",
        "password": "123",
        "name": "Test User"
    })
    assert short_pass_res.status_code == 422 or short_pass_res.status_code == 400

    # 3. Successful registration
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = client.post("/api/auth/register", json={
        "email": email,
        "password": "strongPassword123",
        "name": "Alice Independent",
        "role": "learner",
        "is_employee": False
    })
    assert reg_res.status_code == 200
    data = reg_res.json()
    assert "token" in data
    assert data["user"]["email"] == email
    assert data["user"]["role"] == "learner"

    # 4. Attempt to self-register as admin must be blocked / forced to learner
    admin_attempt_email = f"sneaky_{uuid.uuid4().hex[:6]}@example.com"
    reg_admin_res = client.post("/api/auth/register", json={
        "email": admin_attempt_email,
        "password": "strongPassword123",
        "name": "Sneaky Admin",
        "role": "admin"
    })
    assert reg_admin_res.status_code == 200
    assert reg_admin_res.json()["user"]["role"] != "admin"

def test_duplicate_email_registration_rejected():
    email = f"dup_{uuid.uuid4().hex[:6]}@example.com"
    first = client.post("/api/auth/register", json={
        "email": email,
        "password": "password123",
        "name": "Original User"
    })
    assert first.status_code == 200

    duplicate = client.post("/api/auth/register", json={
        "email": email,
        "password": "anotherPassword456",
        "name": "Impostor User"
    })
    assert duplicate.status_code == 400
    assert "already exists" in duplicate.json()["detail"].lower()

def test_login_and_credential_verification():
    email = f"login_test_{uuid.uuid4().hex[:6]}@example.com"
    password = "correctPassword123"
    client.post("/api/auth/register", json={
        "email": email,
        "password": password,
        "name": "Login Tester"
    })

    # 1. Login with incorrect password
    bad_login = client.post("/api/auth/login", json={
        "email": email,
        "password": "wrongPassword!!!"
    })
    assert bad_login.status_code == 401

    # 2. Login with non-existent email
    bad_email_login = client.post("/api/auth/login", json={
        "email": "ghost_user_does_not_exist@example.com",
        "password": "password"
    })
    assert bad_email_login.status_code == 401

    # 3. Login with correct credentials
    good_login = client.post("/api/auth/login", json={
        "email": email,
        "password": password
    })
    assert good_login.status_code == 200
    auth_data = good_login.json()
    assert "token" in auth_data
    assert auth_data["user"]["email"] == email

def test_session_restoration_via_auth_me():
    email = f"session_{uuid.uuid4().hex[:6]}@example.com"
    reg = client.post("/api/auth/register", json={
        "email": email,
        "password": "password123",
        "name": "Session Tester"
    })
    token = reg.json()["token"]

    # Call /auth/me with Bearer token simulating page refresh
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    user_profile = me_res.json()
    assert user_profile["email"] == email
    assert user_profile["name"] == "Session Tester"

def test_logout_and_session_revocation():
    email = f"logout_{uuid.uuid4().hex[:6]}@example.com"
    reg = client.post("/api/auth/register", json={
        "email": email,
        "password": "password123",
        "name": "Logout Tester"
    })
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify protected access works before logout
    profile_before = client.get("/api/employees/me", headers=headers)
    assert profile_before.status_code == 200

    # Logout
    logout_res = client.post("/api/auth/logout", headers=headers)
    assert logout_res.status_code == 200

    # Access after logout must be denied
    profile_after = client.get("/api/employees/me", headers=headers)
    assert profile_after.status_code == 401

def test_dynamic_roadmap_creation_and_persistence_across_sessions():
    email = f"roadmap_{uuid.uuid4().hex[:6]}@example.com"
    reg = client.post("/api/auth/register", json={
        "email": email,
        "password": "password123",
        "name": "Roadmap Learner"
    })
    token = reg.json()["token"]
    emp_id = reg.json()["user"]["employee_id"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. New user has NO pre-generated plan
    plan_initial = client.get("/api/learning-plans/self-directed", headers=headers)
    assert plan_initial.status_code == 200
    assert plan_initial.json() is None

    # 2. User generates their own personalized roadmap for Data Analyst
    gen_res = client.post("/api/learning-plans/generate", json={
        "employee_id": emp_id,
        "target_role": "Data Analyst",
        "mode": "self_directed",
        "budget": 350.0,
        "weekly_hours": 12.0
    }, headers=headers)
    assert gen_res.status_code == 200
    created_plan = gen_res.json()
    assert created_plan["target_role"] == "Data Analyst"
    assert len(created_plan["ordered_courses"]) > 0

    # 3. Simulate logging out and logging back in
    client.post("/api/auth/logout", headers=headers)
    login_res = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    new_token = login_res.json()["token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # 4. Resume roadmap: same plan retrieved
    resumed_plan_res = client.get("/api/learning-plans/self-directed", headers=new_headers)
    assert resumed_plan_res.status_code == 200
    resumed_plan = resumed_plan_res.json()
    assert resumed_plan is not None
    assert resumed_plan["target_role"] == "Data Analyst"
    assert resumed_plan["budget_limit"] == 350.0

def test_cross_user_isolation():
    # User A
    user_a_email = f"user_a_{uuid.uuid4().hex[:6]}@example.com"
    reg_a = client.post("/api/auth/register", json={
        "email": user_a_email,
        "password": "password123",
        "name": "User Alpha"
    })
    token_a = reg_a.json()["token"]
    emp_a = reg_a.json()["user"]["employee_id"]

    # User B
    user_b_email = f"user_b_{uuid.uuid4().hex[:6]}@example.com"
    reg_b = client.post("/api/auth/register", json={
        "email": user_b_email,
        "password": "password123",
        "name": "User Beta"
    })
    token_b = reg_b.json()["token"]
    emp_b = reg_b.json()["user"]["employee_id"]

    # User A creates a roadmap
    client.post("/api/learning-plans/generate", json={
        "employee_id": emp_a,
        "target_role": "Data Analyst",
        "mode": "self_directed",
        "budget": 400.0,
        "weekly_hours": 10.0
    }, headers={"Authorization": f"Bearer {token_a}"})

    # User B attempts to access User A's profile and roadmap using header spoofing
    sneak_profile = client.get("/api/employees/me", headers={
        "Authorization": f"Bearer {token_b}",
        "x-employee-id": emp_a
    })
    assert sneak_profile.status_code == 403

    sneak_progress = client.get("/api/learning-progress", headers={
        "Authorization": f"Bearer {token_b}",
        "x-employee-id": emp_a
    })
    assert sneak_progress.status_code == 403

def test_progress_tracking_persistence():
    email = f"progress_{uuid.uuid4().hex[:6]}@example.com"
    reg = client.post("/api/auth/register", json={
        "email": email,
        "password": "password123",
        "name": "Progress Tracker"
    })
    token = reg.json()["token"]
    emp_id = reg.json()["user"]["employee_id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Record progress
    rec_res = client.post("/api/learning-progress", json={
        "employee_id": emp_id,
        "course_id": "C101",
        "lesson_id": "L1",
        "status": "completed",
        "time_spent_minutes": 45
    }, headers=headers)
    assert rec_res.status_code == 200

    # Retrieve progress
    get_res = client.get("/api/learning-progress?course_id=C101", headers=headers)
    assert get_res.status_code == 200
    items = get_res.json()
    assert len(items) >= 1
    assert items[0]["lesson_id"] == "L1"
    assert items[0]["status"] == "completed"

def test_database_connection_resilience_and_health():
    # Health endpoint reports database status clearly
    health = client.get("/api/health")
    assert health.status_code == 200
    data = health.json()
    assert "database_mode" in data
    assert data["status"] == "healthy"
