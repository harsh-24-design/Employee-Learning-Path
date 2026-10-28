import uuid
import pytest
from app.repositories.mongo_repository import repository
from app.models.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    CustomGoalRequest,
    CompanyGoalAssignmentRequest,
    RoleCreateUpdateRequest,
    RoleCompetency,
    Course
)
from app.agent.tools import (
    generate_learning_plan,
    save_learning_plan,
    get_active_plan_for_mode,
    get_employee_plan_history,
    get_team_members_summary,
    identify_skill_gaps,
    search_courses
)
from app.agent.engine import LearningPathEngine
from app.api.routes import (
    register_user,
    login_user,
    create_custom_learning_goal,
    assign_company_learning_goal,
    get_self_directed_plan,
    get_company_assigned_plan,
    discover_courses,
    create_role,
    get_team_overview
)

def test_req_1_independent_learner_self_registration():
    """
    Requirement 1: System must allow independent learners to register WITHOUT a company employee ID.
    """
    unique_email = f"indep_{uuid.uuid4().hex[:6]}@example.com"
    req = UserRegisterRequest(
        email=unique_email,
        password="securePassword123",
        name="Independent Learner Test",
        role="learner",
        is_employee=False,
        employee_id=None,
        department="Independent Self-Learner"
    )
    res = register_user(req)
    assert res.token is not None and len(res.token) > 20
    assert res.user.email == unique_email
    assert res.user.is_employee is False
    assert res.user.employee_id is not None
    assert res.user.employee_id.startswith("LRN-")

    # Confirm user can log in with their credentials
    login_req = UserLoginRequest(email=unique_email, password="securePassword123")
    login_res = login_user(login_req)
    assert login_res.user.email == unique_email
    assert login_res.user.employee_id == res.user.employee_id

def test_req_2_dual_mode_learning_isolation():
    """
    Requirement 2: Self-directed learning and company-assigned learning must remain separate.
    """
    emp_id = f"E_DUAL_{uuid.uuid4().hex[:6]}"
    
    # 1. Employee creates a self-directed personal learning goal (e.g. Python & Cloud)
    self_plan = generate_learning_plan(
        employee_id=emp_id,
        target_role="Python Developer",
        mode="self_directed",
        budget=300.0,
        weekly_hours=8.0
    )
    save_learning_plan(emp_id, self_plan)

    # 2. Manager assigns a separate company-assigned upskilling requirement
    assign_req = CompanyGoalAssignmentRequest(
        employee_id=emp_id,
        target_role="Data Analyst",
        assignment_deadline="2026-12-31",
        budget=500.0,
        weekly_hours=12.0,
        manager_notes="Mandatory corporate compliance transition."
    )
    company_plan = assign_company_learning_goal(assign_req, x_employee_id="M1001")

    # 3. Retrieve each plan independently and verify no cross-over
    retrieved_self = get_active_plan_for_mode(emp_id, "self_directed")
    retrieved_company = get_active_plan_for_mode(emp_id, "company_assigned")

    assert retrieved_self is not None
    assert retrieved_company is not None
    assert retrieved_self.mode == "self_directed"
    assert retrieved_company.mode == "company_assigned"
    assert retrieved_self.target_role == "Python Developer"
    assert retrieved_company.target_role == "Data Analyst"
    assert retrieved_company.assigned_by == "M1001"
    assert retrieved_company.assignment_deadline == "2026-12-31"

def test_req_3_target_role_and_competency_management():
    """
    Requirement 3: Role definitions maintained by admin, role gaps analyzed, uncatalogued role flagged.
    """
    # 1. Admin creates a new specialized role definition
    role_name = f"ML_Engineer_{uuid.uuid4().hex[:4]}"
    req = RoleCreateUpdateRequest(
        role_name=role_name,
        description="Machine Learning Engineer role profile",
        prerequisites=["Python", "Linear Algebra"],
        relevant_resources=["Coursera Deep Learning", "Fast.ai"],
        competencies=[
            RoleCompetency(skill="Python", required_proficiency=3),
            RoleCompetency(skill="Machine Learning", required_proficiency=2)
        ]
    )
    role_res = create_role(req)
    assert role_res.role_name == role_name
    assert len(role_res.competencies) == 2

    # 2. Evaluate skill gaps against this new role
    emp_id = f"E_ROLE_{uuid.uuid4().hex[:6]}"
    gap_res = identify_skill_gaps(emp_id, role_name)
    assert gap_res.role_competency_available is True
    assert gap_res.total_gaps >= 1

    # 3. When an unknown role is requested, clearly indicate role data is unavailable
    unknown_role = "Quantum_Cryptographer_Specialist"
    unknown_gap = identify_skill_gaps(emp_id, unknown_role)
    assert unknown_gap.role_competency_available is False
    assert "not found in role catalogue" in unknown_gap.notes

def test_req_4_multi_platform_course_discovery():
    """
    Requirement 4: Multi-platform courses from Coursera, edX, Udemy, freeCodeCamp with provider, verification status, and URLs.
    """
    coursera_courses = discover_courses(platform="Coursera")
    assert len(coursera_courses) > 0
    for c in coursera_courses:
        assert c.platform == "Coursera"
        assert c.source_verification_status in ["verified", "unconfirmed"]
        assert c.source_url.startswith("https://")

    free_courses = discover_courses(pricing_model="free")
    assert len(free_courses) > 0
    for c in free_courses:
        assert c.cost == 0.0

def test_req_5_personalized_budget_and_staged_planning():
    """
    Requirement 5: Personalized budget planning, effective subscription cost calculation, and staged suggestions.
    """
    sub_course = Course(
        course_id="C_SUB_TEST",
        title="Subscription Specialization",
        skill="Data Analysis",
        level=2,
        hours=120.0,
        cost=196.0,
        platform="Coursera",
        pricing_model="subscription",
        subscription_monthly_cost=49.0
    )
    eff_cost = LearningPathEngine.calculate_effective_cost(sub_course, weekly_hours=10.0)
    assert eff_cost == 147.0

    budget_breakdown = LearningPathEngine.build_budget_breakdown(
        selected_courses=[sub_course],
        weekly_hours=10.0,
        budget_limit=50.0
    )
    assert budget_breakdown.is_within_budget is False
    assert budget_breakdown.staged_path_suggestion is not None
    assert "exceeds your budget limit" in budget_breakdown.staged_path_suggestion

def test_req_6_certificate_credential_recommendations():
    """
    Requirement 6: Certificate types distinguished (completion, assessed, professional, accredited), fees, and disclaimers.
    """
    courses = discover_courses(certificate_type="professional_certificate")
    assert len(courses) > 0
    for c in courses:
        assert c.certificate_info.available is True
        assert c.certificate_info.type == "professional_certificate"
        assert c.certificate_info.issuer != ""

def test_req_7_milestones_and_training_intensity():
    """
    Requirement 7: Personalized roadmap generates sequenced milestones, targets dates, and adjusts for training intensity.
    """
    emp_id = f"E_INTENSE_{uuid.uuid4().hex[:6]}"
    
    light_plan = generate_learning_plan(
        employee_id=emp_id,
        target_role="Data Analyst",
        weekly_hours=10.0,
        training_intensity="light"
    )
    intensive_plan = generate_learning_plan(
        employee_id=emp_id,
        target_role="Data Analyst",
        weekly_hours=10.0,
        training_intensity="intensive"
    )
    assert light_plan.estimated_weeks > intensive_plan.estimated_weeks

    assert len(light_plan.milestones) >= 1
    assert light_plan.milestones[0].milestone_id.startswith("M")
    assert light_plan.milestones[0].assessment_activity is not None

def test_req_10_manager_team_oversight():
    """
    Requirement 10: Manager can view authorized team members' assigned goals and progress percentages.
    """
    team = get_team_overview()
    assert isinstance(team, list)
    assert len(team) > 0
    first_member = team[0]
    assert hasattr(first_member, "employee_id")
    assert hasattr(first_member, "has_active_assigned_plan")
    assert hasattr(first_member, "assigned_progress_percent")
