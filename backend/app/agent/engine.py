import hashlib
import json
import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple, Set

from app.models.schemas import (
    Course,
    SkillGapItem,
    LearningPlan,
    PlanMode,
    Milestone,
    BudgetBreakdown,
    BudgetOptionComparison
)

class CycleDetectedException(Exception):
    """Raised when a circular dependency is detected in course prerequisites."""
    pass

class IncompletePrerequisiteException(Exception):
    """Raised when a required prerequisite course does not exist in the catalogue."""
    pass

class LearningPathEngine:
    """
    Deterministic calculation engine supporting:
    - Standard and Custom Goal Skill Gaps (FR-02, Requirement 3)
    - Prerequisite DAG Sequencing with Kahn's Algorithm (FR-04)
    - Multi-Platform Subscription & Certificate Budgeting (Requirement 4, 5, 6)
    - Dual-Mode Learning Plans (Requirement 2 & 7)
    """

    @staticmethod
    def calculate_skill_gaps(
        current_skills: Dict[str, int],
        target_competencies: Dict[str, int],
        catalogue_courses: List[Course]
    ) -> Tuple[List[SkillGapItem], List[str]]:
        gaps: List[SkillGapItem] = []
        unfulfillable: List[str] = []

        catalogue_skills = {c.skill.lower(): [] for c in catalogue_courses}
        for c in catalogue_courses:
            catalogue_skills[c.skill.lower()].append(c.course_id)

        for skill, target_prof in target_competencies.items():
            curr_prof = current_skills.get(skill, 0)
            gap = max(0, target_prof - curr_prof)
            
            if gap <= 0:
                continue

            available_courses = catalogue_skills.get(skill.lower(), [])
            has_courses = len(available_courses) > 0
            if not has_courses:
                unfulfillable.append(skill)

            gaps.append(SkillGapItem(
                skill=skill,
                current_proficiency=curr_prof,
                target_proficiency=target_prof,
                gap=gap,
                has_catalogue_courses=has_courses,
                recommended_course_ids=available_courses
            ))

        gaps.sort(key=lambda x: x.gap, reverse=True)
        return gaps, unfulfillable

    @staticmethod
    def resolve_prerequisites_dag(
        gaps: List[SkillGapItem],
        catalogue_courses: List[Course],
        completed_course_ids: Set[str],
        preferred_platform: Optional[str] = None,
        wants_certificate: bool = False
    ) -> List[Course]:
        course_by_id: Dict[str, Course] = {c.course_id: c for c in catalogue_courses}
        courses_by_skill: Dict[str, List[Course]] = {}
        for c in catalogue_courses:
            courses_by_skill.setdefault(c.skill.lower(), []).append(c)
        for s in courses_by_skill:
            # Sort by level, then prioritize requested platform and certificate availability
            courses_by_skill[s].sort(key=lambda x: (
                x.level,
                0 if preferred_platform and x.platform.lower() == preferred_platform.lower() else 1,
                0 if wants_certificate and x.certificate_info.available else 1,
                x.cost
            ))

        # 1. Determine directly needed courses
        direct_course_ids: Set[str] = set()
        for gap_item in gaps:
            skill_courses = courses_by_skill.get(gap_item.skill.lower(), [])
            # Find best course bridging each gap level
            for c in skill_courses:
                if gap_item.current_proficiency < c.level <= gap_item.target_proficiency:
                    if c.course_id not in completed_course_ids:
                        direct_course_ids.add(c.course_id)

        # 2. Expand prerequisites recursively
        all_required_ids: Set[str] = set(direct_course_ids)
        queue = list(direct_course_ids)
        visited = set()

        while queue:
            cid = queue.pop(0)
            if cid in visited:
                continue
            visited.add(cid)

            c = course_by_id.get(cid)
            if not c:
                raise IncompletePrerequisiteException(f"Course {cid} not found in approved catalogue.")

            if c.prerequisite_id:
                prereq_id = c.prerequisite_id
                if prereq_id not in course_by_id:
                    raise IncompletePrerequisiteException(
                        f"Prerequisite {prereq_id} for course {c.course_id} is missing from catalogue."
                    )
                if prereq_id not in completed_course_ids:
                    all_required_ids.add(prereq_id)
                    queue.append(prereq_id)

        target_ids = all_required_ids - completed_course_ids
        if not target_ids:
            return []

        # 3. Kahn's Topological Sorting
        adj: Dict[str, List[str]] = {cid: [] for cid in target_ids}
        in_degree: Dict[str, int] = {cid: 0 for cid in target_ids}

        for cid in target_ids:
            c = course_by_id[cid]
            if c.prerequisite_id and c.prerequisite_id in target_ids:
                adj[c.prerequisite_id].append(cid)
                in_degree[cid] += 1

        ready_queue = [cid for cid, deg in in_degree.items() if deg == 0]
        ready_queue.sort(key=lambda x: (course_by_id[x].level, course_by_id[x].course_id))

        ordered_ids: List[str] = []
        while ready_queue:
            curr = ready_queue.pop(0)
            ordered_ids.append(curr)

            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    ready_queue.append(neighbor)
            ready_queue.sort(key=lambda x: (course_by_id[x].level, course_by_id[x].course_id))

        if len(ordered_ids) < len(target_ids):
            unresolved = set(target_ids) - set(ordered_ids)
            raise CycleDetectedException(f"Prerequisite cycle detected involving: {unresolved}")

        result: List[Course] = []
        for cid in ordered_ids:
            orig = course_by_id[cid]
            is_foundation = (cid not in direct_course_ids)
            c_dict = orig.model_dump()
            c_dict["is_foundation"] = is_foundation
            result.append(Course(**c_dict))

        return result

    @staticmethod
    def calculate_effective_cost(course: Course, weekly_hours: float, wants_certificate: bool = False) -> float:
        """
        Calculates effective cost considering pricing model and certificate fees.
        """
        cost = course.cost
        # If subscription model, calculate months needed
        if course.pricing_model == "subscription" and course.subscription_monthly_cost:
            weeks = course.hours / (weekly_hours or 10.0)
            months = max(1, math.ceil(weeks / 4.33))
            cost = course.subscription_monthly_cost * months

        # Add separate certificate fee if user specifically wants certificate and it's not included
        if wants_certificate and course.certificate_info.available:
            if not course.certificate_info.is_included_in_price:
                cost += course.certificate_info.separate_certificate_fee

        return round(cost, 2)

    @classmethod
    def apply_constraints(
        cls,
        ordered_courses: List[Course],
        weekly_hours: float,
        budget: Optional[float],
        wants_certificate: bool = False
    ) -> Tuple[List[Course], float, float, float, bool, List[str], List[str]]:
        if weekly_hours <= 0:
            weekly_hours = 1.0

        is_extended = (weekly_hours <= 3.0)
        effective_budget = budget if budget is not None else float("inf")

        selected_courses: List[Course] = []
        deferred_courses: List[str] = []
        remaining_gaps: Set[str] = set()

        if effective_budget == 0.0:
            included_ids = set()
            for c in ordered_courses:
                course_eff_cost = cls.calculate_effective_cost(c, weekly_hours, wants_certificate)
                if course_eff_cost == 0.0:
                    if not c.prerequisite_id or c.prerequisite_id in included_ids:
                        selected_courses.append(c)
                        included_ids.add(c.course_id)
                    else:
                        deferred_courses.append(c.course_id)
                        remaining_gaps.add(c.skill)
                else:
                    deferred_courses.append(c.course_id)
                    remaining_gaps.add(c.skill)
        else:
            total_est_cost = sum(cls.calculate_effective_cost(c, weekly_hours, wants_certificate) for c in ordered_courses)
            if total_est_cost <= effective_budget:
                selected_courses = list(ordered_courses)
            else:
                # Reduced plan preserving prerequisites
                current_cost = 0.0
                included_ids = set()
                for c in ordered_courses:
                    c_cost = cls.calculate_effective_cost(c, weekly_hours, wants_certificate)
                    if current_cost + c_cost <= effective_budget:
                        if not c.prerequisite_id or c.prerequisite_id in included_ids:
                            selected_courses.append(c)
                            included_ids.add(c.course_id)
                            current_cost += c_cost
                        else:
                            deferred_courses.append(c.course_id)
                            remaining_gaps.add(c.skill)
                    else:
                        deferred_courses.append(c.course_id)
                        remaining_gaps.add(c.skill)

        total_hours = sum(c.hours for c in selected_courses)
        total_cost = sum(cls.calculate_effective_cost(c, weekly_hours, wants_certificate) for c in selected_courses)
        estimated_weeks = round(total_hours / weekly_hours, 1) if weekly_hours > 0 else 0.0

        return (
            selected_courses,
            total_hours,
            total_cost,
            estimated_weeks,
            is_extended,
            sorted(list(remaining_gaps)),
            deferred_courses
        )

    @classmethod
    def build_milestones(
        cls,
        selected_courses: List[Course],
        weekly_hours: float,
        start_date: Optional[datetime] = None
    ) -> List[Milestone]:
        if not selected_courses:
            return []

        start = start_date or datetime.now(timezone.utc)
        milestones: List[Milestone] = []

        foundations = [c for c in selected_courses if c.is_foundation or c.level <= 1]
        intermediates = [c for c in selected_courses if not c.is_foundation and c.level == 2]
        advanced = [c for c in selected_courses if not c.is_foundation and c.level >= 3]

        if not intermediates and not advanced and len(selected_courses) > 1:
            mid = max(1, len(selected_courses) // 2)
            foundations = selected_courses[:mid]
            intermediates = selected_courses[mid:]
        elif not foundations and not intermediates:
            foundations = selected_courses

        phases = [
            ("M1", "Foundation & Prerequisites", "Establish core syntax, foundational concepts, and prerequisite knowledge.", foundations, "Self-check Quizzes & Lesson Practice Exercises"),
            ("M2", "Core Competency Mastery", "Develop practical, applied capabilities and workflow pipelines.", intermediates, "Practical Problem-Solving & Module Quizzes"),
            ("M3", "Advanced Evaluation & Credentialing", "Integrate advanced problem-solving, project capstones, and verified assessment.", advanced, "Comprehensive Rubric Assessment & Credential Verification")
        ]

        current_offset_hours = 0.0
        for m_id, title, desc, phase_courses, assess_act in phases:
            if not phase_courses:
                continue
            hrs = sum(c.hours for c in phase_courses)
            current_offset_hours += hrs
            offset_weeks = current_offset_hours / max(1.0, weekly_hours)
            m_target = (start + timedelta(days=int(offset_weeks * 7))).strftime("%Y-%m-%d")

            milestones.append(Milestone(
                milestone_id=m_id,
                title=title,
                description=desc,
                course_ids=[c.course_id for c in phase_courses],
                estimated_hours=hrs,
                target_date=m_target,
                assessment_activity=assess_act,
                is_completed=False
            ))

        return milestones

    @classmethod
    def build_budget_breakdown(
        cls,
        selected_courses: List[Course],
        weekly_hours: float,
        budget_limit: Optional[float],
        wants_certificate: bool = False
    ) -> BudgetBreakdown:
        total_cost = 0.0
        paid_cost = 0.0
        sub_cost = 0.0
        cert_fees = 0.0
        has_coursera_or_edx = False

        for c in selected_courses:
            eff = cls.calculate_effective_cost(c, weekly_hours, wants_certificate)
            total_cost += eff
            if c.pricing_model == "subscription":
                sub_cost += eff
            elif c.pricing_model == "paid_one_time":
                paid_cost += eff

            if wants_certificate and c.certificate_info.available and not c.certificate_info.is_included_in_price:
                cert_fees += c.certificate_info.separate_certificate_fee

            if c.platform.lower() in ["coursera", "edx"]:
                has_coursera_or_edx = True

        is_within = (budget_limit is None) or (total_cost <= budget_limit)

        staged_suggestion = None
        if not is_within:
            staged_suggestion = (
                f"Current plan cost (${total_cost:.2f}) exceeds your budget limit (${budget_limit:.2f}). "
                "Recommended Staged Strategy: "
                "1) Audit Coursera/edX courses or use freeCodeCamp for free foundational study. "
                "2) Apply for platform financial assistance before the paid phase. "
                "3) Purchase certifications only for your capstone milestones."
            )
        elif budget_limit == 0:
            staged_suggestion = (
                "Zero-budget plan active. All selected courses are 100% free with open audit materials. "
                "Certificates requiring fees are deferred."
            )

        sub_hours = sum(c.hours for c in selected_courses if c.pricing_model == "subscription")
        sub_months = max(1.0, math.ceil((sub_hours / max(1.0, weekly_hours)) / 4.33)) if sub_hours > 0 else 0.0

        comparisons = [
            BudgetOptionComparison(
                model_type="free_audit",
                provider_summary="Free Audit / Open Courseware (freeCodeCamp, Internal, Course Audits)",
                estimated_cost=0.0,
                estimated_months=0.0,
                certificate_included=False,
                financial_assistance_available=True,
                financial_assistance_details="Coursera and edX offer up to 90%-100% financial assistance upon application."
            ),
            BudgetOptionComparison(
                model_type="paid_one_time",
                provider_summary="Standard Single-Purchase Lifetime Access (Udemy, Internal Certification)",
                estimated_cost=round(paid_cost, 2),
                estimated_months=0.0,
                certificate_included=True,
                financial_assistance_available=False
            ),
            BudgetOptionComparison(
                model_type="monthly_subscription",
                provider_summary="Platform Subscription (Coursera Plus, edX Subscription)",
                estimated_cost=round(sub_cost, 2),
                estimated_months=float(sub_months),
                certificate_included=True,
                financial_assistance_available=has_coursera_or_edx,
                financial_assistance_details="Available via provider financial aid applications." if has_coursera_or_edx else None
            )
        ]

        return BudgetBreakdown(
            total_estimated_cost=round(total_cost, 2),
            budget_limit=budget_limit,
            is_within_budget=is_within,
            free_alternatives_cost=0.0,
            paid_courses_cost=round(paid_cost, 2),
            subscription_cost=round(sub_cost, 2),
            certificate_fees_cost=round(cert_fees, 2),
            staged_path_suggestion=staged_suggestion,
            comparisons=comparisons
        )

    @classmethod
    def generate_plan(
        cls,
        employee_id: str,
        target_role: Optional[str],
        current_skills: Dict[str, int],
        target_competencies: Dict[str, int],
        catalogue_courses: List[Course],
        completed_course_ids: Set[str],
        weekly_hours: float = 10.0,
        budget: Optional[float] = 500.0,
        mode: PlanMode = "self_directed",
        is_custom_goal: bool = False,
        goal_description: Optional[str] = None,
        assigned_by: Optional[str] = None,
        assignment_deadline: Optional[str] = None,
        manager_notes: Optional[str] = None,
        wants_certificate: bool = False,
        preferred_platform: Optional[str] = None,
        training_intensity: str = "normal",
        target_date: Optional[str] = None
    ) -> LearningPlan:
        gaps, unfulfillable = cls.calculate_skill_gaps(current_skills, target_competencies, catalogue_courses)

        ordered_all = cls.resolve_prerequisites_dag(
            gaps=gaps,
            catalogue_courses=catalogue_courses,
            completed_course_ids=completed_course_ids,
            preferred_platform=preferred_platform,
            wants_certificate=wants_certificate
        )

        (
            selected_courses,
            total_hours,
            total_cost,
            estimated_weeks,
            is_extended,
            remaining_gaps,
            deferred_courses
        ) = cls.apply_constraints(
            ordered_courses=ordered_all,
            weekly_hours=weekly_hours,
            budget=budget,
            wants_certificate=wants_certificate
        )

        pace_factor = 1.0
        if training_intensity == "light":
            pace_factor = 0.8
        elif training_intensity == "intensive":
            pace_factor = 1.3
        
        if pace_factor != 1.0 and weekly_hours > 0:
            effective_weekly = max(1.0, weekly_hours * pace_factor)
            estimated_weeks = round(total_hours / effective_weekly, 1)

        now = datetime.now(timezone.utc)
        calculated_target_date = target_date
        if not calculated_target_date and estimated_weeks > 0:
            calculated_target_date = (now + timedelta(days=int(estimated_weeks * 7))).strftime("%Y-%m-%d")

        milestones = cls.build_milestones(selected_courses, weekly_hours, now)
        budget_breakdown = cls.build_budget_breakdown(selected_courses, weekly_hours, budget, wants_certificate)

        course_ids_str = ",".join(c.course_id for c in selected_courses)
        hash_payload = f"{employee_id}|{mode}|{target_role}|{course_ids_str}|{total_cost}|{total_hours}|{weekly_hours}|{budget}"
        content_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()

        plan_id = f"PLAN-{uuid.uuid4().hex[:10].upper()}"
        now_str = now.isoformat()
        all_remaining = sorted(list(set(remaining_gaps + unfulfillable)))

        return LearningPlan(
            plan_id=plan_id,
            employee_id=employee_id,
            mode=mode,
            target_role=target_role or "Custom Learning Goal",
            is_custom_goal=is_custom_goal,
            goal_description=goal_description,
            current_skill_snapshot=current_skills,
            target_competencies=target_competencies,
            ordered_courses=selected_courses,
            total_hours=total_hours,
            total_cost=total_cost,
            estimated_weeks=estimated_weeks,
            is_extended_timeline=is_extended,
            budget_limit=budget,
            weekly_hours=weekly_hours,
            training_intensity=training_intensity,
            target_completion_date=calculated_target_date,
            milestones=milestones,
            budget_breakdown=budget_breakdown,
            remaining_gaps=all_remaining,
            deferred_courses=deferred_courses,
            content_hash=content_hash,
            version=1,
            assigned_by=assigned_by,
            assignment_deadline=assignment_deadline,
            manager_notes=manager_notes,
            created_at=now_str
        )
