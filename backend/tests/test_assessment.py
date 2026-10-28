import pytest
from app.repositories.mongo_repository import repository
from app.agent.tools import record_lesson_progress, record_assessment_result, get_employee_skills

def test_checklist_8_lesson_completion_does_not_falsely_certify_mastery():
    """
    Checklist 8: A lesson completion alone does not falsely certify mastery.
    Proficiency updates strictly require verified assessment rubrics.
    """
    emp_id = "E2002"
    # Check baseline Python proficiency
    initial_skills = get_employee_skills(emp_id)
    initial_python = initial_skills.get("Python", 1)
    
    # 1. Complete lesson in advanced python C102
    record_lesson_progress(
        employee_id=emp_id,
        course_id="C102",
        lesson_id="L102-1",
        status="completed",
        time_spent_minutes=90
    )
    
    # Skill level must NOT have increased just because lesson was marked complete
    post_lesson_skills = get_employee_skills(emp_id)
    assert post_lesson_skills.get("Python") == initial_python
    
    # 2. Failing an assessment does NOT increase proficiency
    record_assessment_result(
        employee_id=emp_id,
        course_id="C102",
        assessment_id="QZ-C102",
        score=50,  # Below passing 75
        evidence="Answered 1/2 correct",
        skill_id="Python",
        target_level=2,
        passing_score=75
    )
    post_fail_skills = get_employee_skills(emp_id)
    assert post_fail_skills.get("Python") == initial_python
    
    # 3. Passing the assessment with rubric evidence DOES update verified proficiency
    res = record_assessment_result(
        employee_id=emp_id,
        course_id="C102",
        assessment_id="QZ-C102",
        score=85,  # Passing
        evidence="Rubric verified score: 85%",
        skill_id="Python",
        target_level=2,
        passing_score=75
    )
    assert res.passed is True
    assert res.updated_verified_level == 2
    
    post_pass_skills = get_employee_skills(emp_id)
    assert post_pass_skills.get("Python") == 2
