import pytest
from app.agent.engine import LearningPathEngine, CycleDetectedException, IncompletePrerequisiteException
from app.models.schemas import Course, SkillGapItem
from app.agent.tools import (
    generate_learning_plan,
    save_learning_plan,
    update_learning_plan,
    record_lesson_progress
)
from app.repositories.mongo_repository import repository

def test_checklist_1_foundation_recommendation():
    """
    Checklist 1: Employee with no prior skill receives a foundation-level recommendation.
    """
    catalogue = [
        Course(course_id="C101", title="Python Basics", skill="Python", level=1, hours=10, cost=0),
        Course(course_id="C102", title="Intermediate Python", skill="Python", level=2, hours=15, cost=50, prerequisite_id="C101"),
    ]
    current_skills = {"Python": 0}
    role_competencies = {"Python": 2}
    
    gaps, unfulfillable = LearningPathEngine.calculate_skill_gaps(current_skills, role_competencies, catalogue)
    assert len(gaps) == 1
    assert gaps[0].gap == 2
    
    plan_courses = LearningPathEngine.resolve_prerequisites_dag(gaps, catalogue, set())
    assert len(plan_courses) == 2
    # Foundation level C101 must be the first recommended course
    assert plan_courses[0].course_id == "C101"
    assert plan_courses[0].level == 1
    assert plan_courses[1].course_id == "C102"

def test_checklist_2_missing_prerequisite_added_before_advanced():
    """
    Checklist 2: Missing prerequisite is added before an advanced course.
    """
    catalogue = [
        Course(course_id="C101", title="Python Basics", skill="Python", level=1, hours=10, cost=0),
        Course(course_id="C102", title="Intermediate Python", skill="Python", level=2, hours=15, cost=50, prerequisite_id="C101"),
        Course(course_id="C103", title="Advanced Python", skill="Python", level=3, hours=20, cost=100, prerequisite_id="C102")
    ]
    # Employee directly requests target level 3 without C101 or C102
    current_skills = {"Python": 0}
    role_competencies = {"Python": 3}
    
    gaps, _ = LearningPathEngine.calculate_skill_gaps(current_skills, role_competencies, catalogue)
    ordered = LearningPathEngine.resolve_prerequisites_dag(gaps, catalogue, set())
    
    c_ids = [c.course_id for c in ordered]
    assert c_ids == ["C101", "C102", "C103"]
    # Prerequisite C101 comes before C102, which comes before C103
    assert c_ids.index("C101") < c_ids.index("C102") < c_ids.index("C103")

def test_checklist_3_catalogue_integrity():
    """
    Checklist 3: A course absent from the catalogue is not invented.
    """
    catalogue = [
        Course(course_id="C101", title="Python Basics", skill="Python", level=1, hours=10, cost=0)
    ]
    # Target requires Rust, which is NOT in catalogue
    current_skills = {}
    role_competencies = {"Rust": 3}
    
    gaps, unfulfillable = LearningPathEngine.calculate_skill_gaps(current_skills, role_competencies, catalogue)
    assert "Rust" in unfulfillable
    
    ordered = LearningPathEngine.resolve_prerequisites_dag(gaps, catalogue, set())
    # No courses invented for Rust
    assert len(ordered) == 0

def test_checklist_4_zero_budget_constraint():
    """
    Checklist 4: Zero budget only permits courses whose recorded cost is zero.
    """
    ordered = [
        Course(course_id="C101", title="Python Basics", skill="Python", level=1, hours=10, cost=0),
        Course(course_id="C102", title="Intermediate Python", skill="Python", level=2, hours=15, cost=100, prerequisite_id="C101"),
        Course(course_id="C201", title="SQL Basics", skill="SQL", level=1, hours=10, cost=0)
    ]
    selected, total_hours, total_cost, weeks, extended, gaps, deferred = LearningPathEngine.apply_constraints(
        ordered_courses=ordered,
        weekly_hours=10.0,
        budget=0.0
    )
    
    assert total_cost == 0.0
    for c in selected:
        assert c.cost == 0.0
    assert "C102" in deferred

def test_checklist_5_extended_timeline_hours():
    """
    Checklist 5: Limited weekly study hours produce a longer plan with extended timeline flag.
    """
    ordered = [
        Course(course_id="C101", title="Python Basics", skill="Python", level=1, hours=20, cost=0)
    ]
    # 2 hours per week (<= 3 hrs/week)
    selected, total_hours, total_cost, weeks, extended, gaps, deferred = LearningPathEngine.apply_constraints(
        ordered_courses=ordered,
        weekly_hours=2.0,
        budget=500.0
    )
    assert extended is True
    assert weeks == 10.0  # 20 hours / 2 hrs/week = 10 weeks

def test_checklist_6_plan_revision_preserves_history():
    """
    Checklist 6: Increasing weekly hours updates the plan and preserves history.
    """
    import uuid
    emp_id = f"E_TEST_HIST_{uuid.uuid4().hex[:6]}"
    # Generate initial plan
    plan_v1 = generate_learning_plan(emp_id, "Data Analyst", budget=500.0, weekly_hours=5.0)
    save_learning_plan(emp_id, plan_v1)
    
    # Update weekly hours to 15.0
    plan_v2 = update_learning_plan(emp_id, weekly_hours=15.0)
    assert plan_v2 is not None
    assert plan_v2.version == plan_v1.version + 1
    assert plan_v2.weekly_hours == 15.0
    assert plan_v2.estimated_weeks < plan_v1.estimated_weeks
    
    # Confirm both versions exist in the repository
    all_plans = repository.find("learning_plans", {"employee_id": emp_id})
    assert len(all_plans) >= 2

def test_checklist_7_idempotent_progress_update():
    """
    Checklist 7: Completing a lesson updates progress exactly once.
    """
    emp_id = "E2001"
    course_id = "C101"
    lesson_id = "L101-1"
    
    p1 = record_lesson_progress(emp_id, course_id, lesson_id, status="completed", time_spent_minutes=45)
    # Re-calling complete for the same lesson
    p2 = record_lesson_progress(emp_id, course_id, lesson_id, status="completed", time_spent_minutes=0)
    
    # Must update same record rather than creating a duplicate
    records = repository.find("learning_progress", {
        "employee_id": emp_id,
        "course_id": course_id,
        "lesson_id": lesson_id
    })
    assert len(records) == 1
    assert records[0]["status"] == "completed"

def test_checklist_14_schema_validation_rejections():
    """
    Checklist 14: Invalid scores, durations, and proficiency levels are rejected by schema.
    """
    from pydantic import ValidationError
    
    # Proficiency > 5 must fail
    with pytest.raises(ValidationError):
        Course(course_id="C999", title="Invalid", skill="Test", level=6, hours=10, cost=0)
        
    # Negative hours must fail
    with pytest.raises(ValidationError):
        Course(course_id="C999", title="Invalid", skill="Test", level=1, hours=-5, cost=0)
