import uuid
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.mongo_repository import repository
from app.services.course_rag import CourseRAGService
from app.agent.gemini_advisor import GeminiAdvisor
from app.core.config import settings

client = TestClient(app)

def get_demo_auth_headers():
    unique_email = f"demo_tester_{uuid.uuid4().hex[:6]}@example.com"
    reg = client.post("/api/auth/register", json={
        "email": unique_email,
        "password": "strongPassword123",
        "name": "Demo Tester",
        "role": "learner",
        "is_employee": True,
        "employee_id": "E2001"
    })
    token = reg.json()["token"]
    return {"Authorization": f"Bearer {token}"}

def test_acceptance_1_all_three_courses_exist_and_have_rich_content():
    """
    Acceptance Criteria 1:
    - Python Basics (C101), Excel Foundations (C301), Cloud Fundamentals (C501) open with real lessons.
    - Each course has >= 3 modules, >= 2 substantive lessons per module.
    - Every lesson includes explanation, practical example, key takeaways, and hands-on exercise.
    - Demo courses are explicitly labeled with a demo disclaimer.
    - Broken placeholder URLs (learning.internal.corp) are removed.
    """
    demo_course_ids = ["C101", "C301", "C501"]
    for course_id in demo_course_ids:
        res = client.get(f"/api/courses/{course_id}")
        assert res.status_code == 200, f"Course {course_id} failed to load: {res.text}"
        course = res.json()

        # Check demo labeling
        assert course.get("is_demo") is True, f"Course {course_id} must have is_demo=True"
        assert "demo" in course.get("demo_disclaimer", "").lower(), f"Course {course_id} missing demo disclaimer"

        # Check placeholder URL removed
        source_url = course.get("source_url", "")
        assert "learning.internal.corp" not in source_url, f"Course {course_id} contains broken placeholder URL: {source_url}"

        # Check modules count (>= 3 modules per course)
        modules = course.get("modules", [])
        assert len(modules) >= 3, f"Course {course_id} has {len(modules)} modules; required >= 3"

        total_lessons = 0
        for mod in modules:
            assert mod.get("module_id") is not None
            assert mod.get("title") is not None
            lessons = mod.get("lessons", [])
            assert len(lessons) >= 2, f"Module {mod.get('module_id')} has {len(lessons)} lessons; required >= 2"
            total_lessons += len(lessons)

            for lsn in lessons:
                assert lsn.get("lesson_id"), "Lesson ID required"
                assert lsn.get("title"), "Lesson title required"
                
                # Explanation
                assert len(lsn.get("explanation", "")) > 40, f"Lesson {lsn.get('lesson_id')} explanation too short"
                
                # Practical Example
                prac = lsn.get("practical_example", "")
                assert isinstance(prac, str) and len(prac) >= 30, f"Lesson {lsn.get('lesson_id')} practical_example must be non-empty string"

                # Key Takeaways
                takeaways = lsn.get("key_takeaways", [])
                assert isinstance(takeaways, list) and len(takeaways) >= 2, f"Lesson {lsn.get('lesson_id')} requires >= 2 takeaways"

                # Exercise
                exercise = lsn.get("exercise", "")
                assert isinstance(exercise, str) and len(exercise) >= 20, f"Lesson {lsn.get('lesson_id')} exercise too short"

        assert total_lessons >= 6, f"Course {course_id} total lessons {total_lessons} < 6"

def test_acceptance_2_module_quizzes_render_and_grade_correctly():
    """
    Acceptance Criteria 2:
    - Module-level quizzes exist for each course.
    - Quizzes can be fetched by module_id.
    - Submitting quiz answers grades accurately with rubric and score.
    """
    headers = get_demo_auth_headers()
    for course_id in ["C101", "C301", "C501"]:
        course_res = client.get(f"/api/courses/{course_id}", headers=headers)
        course = course_res.json()
        for mod in course.get("modules", []):
            mod_id = mod["module_id"]
            quiz_res = client.get(f"/api/courses/{course_id}/quiz?module_id={mod_id}", headers=headers)
            assert quiz_res.status_code == 200, f"Failed to get quiz for {course_id} module {mod_id}"
            quiz = quiz_res.json()
            assert quiz is not None, f"Quiz is None for {course_id} module {mod_id}"
            assert len(quiz.get("questions", [])) >= 2, f"Quiz for {mod_id} must have >= 2 questions"

            # Check question structure
            q1 = quiz["questions"][0]
            assert "question_id" in q1
            assert "prompt" in q1
            assert len(q1.get("options", [])) >= 3
            assert "correct_option_index" in q1

    # Test quiz submission and grading for C101 module M101-1
    quiz_res = client.get("/api/courses/C101/quiz?module_id=M101-1", headers=headers)
    quiz = quiz_res.json()
    answers = {}
    for q in quiz["questions"]:
        answers[q["question_id"]] = q["correct_option_index"]

    sub_res = client.post("/api/assessments", json={
        "employee_id": "E2001",
        "course_id": "C101",
        "assessment_id": quiz["assessment_id"],
        "answers": answers
    }, headers=headers)
    assert sub_res.status_code == 200
    res_data = sub_res.json()
    assert res_data["score"] == 100
    assert res_data["passed"] is True
    assert "Rubric" in res_data["evidence"]

def test_acceptance_3_rag_retrieves_relevant_course_chunks():
    """
    Acceptance Criteria 3:
    - Asking a question retrieves relevant course chunks from Chroma vector database.
    - Verified against Python Basics, Excel Foundations, and Cloud Fundamentals queries.
    """
    # 1. Python query
    py_result = CourseRAGService.search("What is a Python variable and dynamic typing?", course_id="C101", top_k=3)
    assert py_result["found"] is True
    assert len(py_result["chunks"]) > 0
    assert any("Python Basics" in c["course_title"] for c in py_result["citations"])
    assert any("Python" in c["source_reference"] for c in py_result["citations"])

    # 2. Excel query
    xl_result = CourseRAGService.search("How to use SUM, AVERAGE, and basic formulas in Excel?", course_id="C301", top_k=3)
    assert xl_result["found"] is True
    assert len(xl_result["chunks"]) > 0
    assert any("Excel Foundations" in c["course_title"] for c in xl_result["citations"])
    assert any("Formulas" in c["source_reference"] or "Math" in c["source_reference"] for c in xl_result["citations"])

    # 3. Cloud query
    cl_result = CourseRAGService.search("Explain IaaS, PaaS, and SaaS cloud service models", course_id="C501", top_k=3)
    assert cl_result["found"] is True
    assert len(cl_result["chunks"]) > 0
    assert any("Cloud Fundamentals" in c["course_title"] for c in cl_result["citations"])
    assert any("Service Models" in c["source_reference"] for c in cl_result["citations"])

def test_acceptance_4_and_5_ai_answers_accurate_citations_and_no_hallucinations():
    """
    Acceptance Criteria 4 & 5:
    - Relevant questions return accurate lesson references.
    - Unsupported questions clearly state the answer was not found in the course material.
    - Unsupported questions do not receive fabricated course citations (citations list is empty).
    """
    # Check unsupported query retrieval directly
    unsupported_query = "How do I bake a triple chocolate fudge cake with sourdough starter?"
    rag_unsupported = CourseRAGService.search(unsupported_query, course_id="C101", top_k=3)
    assert rag_unsupported["found"] is False
    assert rag_unsupported["citations"] == []

    # Check via chat endpoint with unsupported query
    headers = get_demo_auth_headers()
    conv_id = f"CONV-DEMO-{uuid.uuid4().hex[:6]}"
    chat_res = client.post(f"/api/chat/conversations/{conv_id}/messages", json={
        "employee_id": "E2001",
        "course_id": "C101",
        "message": "How do I bake a triple chocolate fudge cake with sourdough starter?"
    }, headers=headers)
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    reply = chat_data["reply"]
    citations = chat_data.get("citations", [])

    # Must NOT fabricate course citations for cake recipe
    assert citations == [], f"Fabricated citations found for unsupported query: {citations}"
    assert "not found in the course material" in reply.lower() or "not covered" in reply.lower()

def test_acceptance_6_course_progress_persists_and_separates_users():
    """
    Acceptance Criteria 6:
    - Marking a lesson complete saves against authenticated user ID.
    - Progress is restored upon subsequent requests (refresh simulation).
    - Opening a course/lesson does NOT mark it complete.
    - Different users' progress records remain completely isolated.
    """
    # Create two distinct test users
    user_a_email = f"user_a_{uuid.uuid4().hex[:6]}@example.com"
    user_b_email = f"user_b_{uuid.uuid4().hex[:6]}@example.com"

    reg_a = client.post("/api/auth/register", json={
        "email": user_a_email,
        "password": "password123",
        "name": "User Alpha",
        "role": "learner",
        "is_employee": False
    })
    token_a = reg_a.json()["token"]

    reg_b = client.post("/api/auth/register", json={
        "email": user_b_email,
        "password": "password123",
        "name": "User Beta",
        "role": "learner",
        "is_employee": False
    })
    token_b = reg_b.json()["token"]

    # 1. Simulating opening a course/lesson: Just fetching does NOT create progress
    get_course = client.get("/api/courses/C101", headers={"Authorization": f"Bearer {token_a}"})
    assert get_course.status_code == 200
    init_prog_a = client.get("/api/learning-progress?course_id=C101", headers={"Authorization": f"Bearer {token_a}"})
    assert len(init_prog_a.json()) == 0, "Opening course must not mark lessons complete!"

    # 2. User A explicitly marks lesson L101-1 complete
    mark_res = client.post("/api/learning-progress", json={
        "course_id": "C101",
        "lesson_id": "L101-1",
        "status": "completed",
        "time_spent_minutes": 15
    }, headers={"Authorization": f"Bearer {token_a}"})
    assert mark_res.status_code == 200
    assert mark_res.json()["status"] == "completed"

    # 3. Simulate page refresh / re-login for User A
    refresh_prog_a = client.get("/api/learning-progress?course_id=C101", headers={"Authorization": f"Bearer {token_a}"})
    assert refresh_prog_a.status_code == 200
    records_a = refresh_prog_a.json()
    assert len(records_a) == 1
    assert records_a[0]["lesson_id"] == "L101-1"
    assert records_a[0]["status"] == "completed"

    # 4. User B must NOT have User A's completed lesson
    prog_b = client.get("/api/learning-progress?course_id=C101", headers={"Authorization": f"Bearer {token_b}"})
    assert prog_b.status_code == 200
    records_b = prog_b.json()
    assert len(records_b) == 0, "User B should not have User A's progress records"

def test_acceptance_7_and_8_failed_ai_connection_error_and_no_generic_hints():
    """
    Acceptance Criteria 7 & 8:
    - Failed AI connection returns clear configuration or service error.
    - The original generic hint response is no longer returned for normal learning questions.
    """
    headers = get_demo_auth_headers()
    conv_id = f"CONV-FAIL-{uuid.uuid4().hex[:6]}"
    with patch.object(settings, "get_gemini_api_keys", return_value=["dummy-invalid-key"]):
        with patch.object(GeminiAdvisor, "_execute_gemini_call", side_effect=Exception("API connection refused / invalid key")):
            res = client.post(f"/api/chat/conversations/{conv_id}/messages", json={
                "employee_id": "E2001",
                "course_id": "C101",
                "message": "What is a Python variable?"
            }, headers=headers)
            assert res.status_code == 200
            data = res.json()
            reply = data["reply"]

            # Must show clear service/configuration error
            assert "AI Service Error" in reply or "AI Advisor Configuration" in reply
            # Must NOT return old generic template hint
            assert "Hint & Study Guidance" not in reply
            assert "Hint: Review the core concepts" not in reply
            # Must NOT leak secret keys
            assert "dummy-invalid-key" not in reply

def test_acceptance_9_multi_gemini_api_key_failover_without_ui_leak():
    """
    Acceptance Criteria 9 (Multi-Key Support):
    - System iterates through GEMINI_API_KEYS if first key hits 429 quota exhaustion or failure.
    - Second key succeeds transparently.
    - Multiple keys or failover details are NOT leaked to the user/UI.
    """
    headers = get_demo_auth_headers()
    keys = ["key-quota-exhausted-429", "key-working-backup"]
    call_count = 0

    def mock_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Simulate 429 Resource Exhausted on first key
            raise Exception("429 Resource Exhausted: Quota exceeded for model gemini-2.5-flash")
        # Second key succeeds
        return ("A Python variable is a reserved memory location that stores values.", [{"tool": "gemini_generate"}])

    conv_id = f"CONV-FAILOVER-{uuid.uuid4().hex[:6]}"
    with patch.object(settings, "get_gemini_api_keys", return_value=keys):
        with patch.object(GeminiAdvisor, "_execute_gemini_call", side_effect=mock_execute):
            res = client.post(f"/api/chat/conversations/{conv_id}/messages", json={
                "employee_id": "E2001",
                "course_id": "C101",
                "message": "What is a Python variable?"
            }, headers=headers)

            assert res.status_code == 200
            data = res.json()
            reply = data["reply"]

            # Assert fallback was triggered and succeeded
            assert call_count == 2, f"Expected 2 calls (failover), but got {call_count}"
            assert "reserved memory location" in reply

            # Assert keys are not in reply or citations
            assert "key-quota-exhausted-429" not in reply
            assert "key-working-backup" not in reply
            assert "failover" not in reply.lower()  # Hidden from user/UI
