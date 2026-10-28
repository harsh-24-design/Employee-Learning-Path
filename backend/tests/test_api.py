import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def get_auth_token(email="employee@example.com", password="employee123"):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["token"]

def test_health_check_api():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_unauthenticated_request_rejected():
    response = client.get("/api/employees/me")
    assert response.status_code == 401

def test_employee_profile_api():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/employees/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["employee_id"] == "E2001"
    assert "skills" in data

def test_roles_and_courses_api():
    res_roles = client.get("/api/roles")
    assert res_roles.status_code == 200
    assert len(res_roles.json()) > 0
    
    res_courses = client.get("/api/courses")
    assert res_courses.status_code == 200
    assert len(res_courses.json()) > 0

def test_skill_gap_analysis_api():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "employee_id": "E2001",
        "target_role": "Data Analyst"
    }
    response = client.post("/api/skill-gaps/analyze", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "gaps" in data
    assert data["employee_id"] == "E2001"

def test_learning_plan_generate_api():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "employee_id": "E2001",
        "target_role": "Data Analyst",
        "budget": 500.0,
        "weekly_hours": 10.0
    }
    response = client.post("/api/learning-plans/generate", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "ordered_courses" in data
    assert "content_hash" in data

def test_dashboard_api():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/dashboard", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "overall_progress_percent" in data
    assert "active_courses_count" in data
