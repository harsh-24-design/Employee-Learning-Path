import os
import csv
import json
import uuid
from typing import Dict, Any, List, Tuple
import pandas as pd
from pypdf import PdfReader
from app.core.config import settings
from app.repositories.mongo_repository import repository
from app.core.security import hash_password

class DataIngestionService:
    """
    Ingests and validates:
    - courses.csv & multiplatform_courses.json
    - employee_skills.csv
    - competency_matrix.xlsx
    - learning_policy.pdf
    - lessons_and_quizzes.json
    - Seeds default users (Learner, Employee, Manager, Admin)
    """

    @classmethod
    def ingest_all(cls, data_dir: str = settings.DATA_DIR) -> Dict[str, Any]:
        results = {
            "success": True,
            "imported_files": [],
            "total_records": 0,
            "errors": []
        }

        # 0. Load lessons and quizzes dataset
        lessons_data = {}
        lessons_file = os.path.join(data_dir, "lessons_and_quizzes.json")
        if os.path.exists(lessons_file):
            try:
                with open(lessons_file, "r", encoding="utf-8") as lf:
                    lessons_data = json.load(lf)
                results["imported_files"].append("lessons_and_quizzes.json")
            except Exception as e:
                results["errors"].append(f"lessons_and_quizzes.json parse error: {e}")

        # 1. Base Courses from CSV
        courses_file = os.path.join(data_dir, "courses.csv")
        if os.path.exists(courses_file):
            c_count, c_errors = cls.ingest_courses(courses_file, lessons_data)
            results["imported_files"].append("courses.csv")
            results["total_records"] += c_count
            results["errors"].extend(c_errors)

        # 1b. Multi-Platform Courses from JSON
        multi_file = os.path.join(data_dir, "multiplatform_courses.json")
        if os.path.exists(multi_file):
            m_count, m_errors = cls.ingest_multiplatform_courses(multi_file)
            results["imported_files"].append("multiplatform_courses.json")
            results["total_records"] += m_count
            results["errors"].extend(m_errors)

        # 2. Employee Skills & Profile
        skills_file = os.path.join(data_dir, "employee_skills.csv")
        if os.path.exists(skills_file):
            s_count, s_errors = cls.ingest_employee_skills(skills_file)
            results["imported_files"].append("employee_skills.csv")
            results["total_records"] += s_count
            results["errors"].extend(s_errors)

        # 3. Competency Matrix (Roles)
        matrix_file = os.path.join(data_dir, "competency_matrix.xlsx")
        if os.path.exists(matrix_file):
            r_count, r_errors = cls.ingest_competency_matrix(matrix_file)
            results["imported_files"].append("competency_matrix.xlsx")
            results["total_records"] += r_count
            results["errors"].extend(r_errors)

        # 4. Learning Policy PDF
        policy_file = os.path.join(data_dir, "learning_policy.pdf")
        if os.path.exists(policy_file):
            p_count, p_errors = cls.ingest_policy_pdf(policy_file)
            results["imported_files"].append("learning_policy.pdf")
            results["total_records"] += p_count
            results["errors"].extend(p_errors)

        # 5. Seed Users
        cls.seed_default_users()

        # 6. Build Chroma Vector Store Index for Demo Course RAG
        try:
            from app.services.course_rag import CourseRAGService
            rag_res = CourseRAGService.build_index()
            results["imported_files"].append("chroma_vector_index")
            results["total_records"] += rag_res.get("indexed_chunks", 0)
        except Exception as e:
            results["errors"].append(f"CourseRAGService index build warning: {e}")

        if results["errors"]:
            results["success"] = False

        return results

    @classmethod
    def ingest_courses(cls, file_path: str, lessons_data: Dict[str, Any] = None) -> Tuple[int, List[str]]:
        errors: List[str] = []
        valid_courses = []
        seen_ids = set()
        lessons_data = lessons_data or {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader, start=2):
                    cid = row.get("course_id", "").strip()
                    if not cid:
                        continue
                    if cid in seen_ids:
                        continue
                    seen_ids.add(cid)

                    try:
                        level = int(row.get("level", 1))
                        hours = float(row.get("hours", 0))
                        cost = float(row.get("cost", 0))
                    except ValueError as ve:
                        errors.append(f"Row {idx}: numeric parse error ({ve})")
                        continue

                    prereq = row.get("prerequisite_id", "").strip() or None

                    course_lessons = []
                    course_modules = []
                    demo_disclaimer = None
                    is_demo = False

                    if cid in lessons_data:
                        c_meta = lessons_data[cid]
                        if "lessons" in c_meta:
                            course_lessons = c_meta["lessons"]
                        if "modules" in c_meta:
                            course_modules = c_meta["modules"]
                        demo_disclaimer = c_meta.get("demo_disclaimer")
                        is_demo = bool(demo_disclaimer or cid in ("C101", "C301", "C501"))
                    else:
                        title_clean = row.get("title", "").strip()
                        course_lessons = [
                            {"lesson_id": f"L-{cid}-1", "title": f"{title_clean} - Core Concepts", "duration_minutes": int(hours * 30), "content": "Foundations and syntax."},
                            {"lesson_id": f"L-{cid}-2", "title": f"{title_clean} - Practical Exercises", "duration_minutes": int(hours * 30), "content": "Applied problems and workflows."}
                        ]

                    cert_type = "completion_certificate" if cost > 0 else "none"
                    valid_courses.append({
                        "course_id": cid,
                        "title": row.get("title", "").strip(),
                        "provider": "Internal Enterprise Academy",
                        "platform": "Internal",
                        "description": f"Internal training curriculum for {row.get('skill', '').strip()}.",
                        "skill": row.get("skill", "").strip(),
                        "level": level,
                        "hours": hours,
                        "cost": cost,
                        "currency": "USD",
                        "pricing_model": "free" if cost == 0 else "paid_one_time",
                        "subscription_monthly_cost": None,
                        "prerequisite_id": prereq,
                        "is_foundation": False,
                        "lessons": course_lessons,
                        "modules": course_modules,
                        "is_demo": is_demo,
                        "demo_disclaimer": demo_disclaimer,
                        "source_url": "",  # Internal courses open in-app; no broken external URL
                        "catalogue_status": "approved",
                        "source_verification_status": "verified",
                        "last_checked_date": "2026-10-25",
                        "certificate_info": {
                            "available": cost > 0 or level >= 2,
                            "type": cert_type,
                            "issuer": "Enterprise Learning Committee",
                            "is_included_in_price": True,
                            "separate_certificate_fee": 0.0,
                            "verification_url": None
                        }
                    })

            for course in valid_courses:
                repository.update("courses", {"course_id": course["course_id"]}, course, upsert=True)

            return len(valid_courses), errors

        except Exception as e:
            return 0, [f"Failed to read courses.csv: {str(e)}"]

    @classmethod
    def ingest_multiplatform_courses(cls, file_path: str) -> Tuple[int, List[str]]:
        errors: List[str] = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            count = 0
            for item in data:
                cid = item.get("course_id")
                if not cid:
                    continue
                repository.update("courses", {"course_id": cid}, item, upsert=True)
                count += 1

            return count, errors
        except Exception as e:
            return 0, [f"Failed to load multiplatform courses: {str(e)}"]

    @classmethod
    def ingest_employee_skills(cls, file_path: str) -> Tuple[int, List[str]]:
        errors: List[str] = []
        count = 0
        employees_seen = set()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader, start=2):
                    emp_id = row.get("employee_id", "").strip()
                    skill = row.get("skill", "").strip()
                    try:
                        prof = int(row.get("proficiency", 0))
                    except ValueError:
                        continue

                    if not emp_id or not skill:
                        continue

                    employees_seen.add(emp_id)
                    repository.update_employee_skill(
                        employee_id=emp_id,
                        skill=skill,
                        self_level=prof,
                        verified_level=prof if prof > 0 else None,
                        source="initial_import"
                    )
                    count += 1

            for emp_id in employees_seen:
                existing = repository.get_employee(emp_id)
                if not existing:
                    repository.insert("employees", {
                        "employee_id": emp_id,
                        "name": f"Employee {emp_id}",
                        "department": "Data & Analytics",
                        "target_role": "Data Analyst",
                        "preferences": {
                            "preferred_learning_style": "mixed",
                            "daily_study_hours": 1.5,
                            "weekly_hours_available": 10.0,
                            "training_intensity": "normal",
                            "budget_limit": 500.0,
                            "target_completion_date": None,
                            "wants_certificate": False,
                            "preferred_certificate_type": None,
                            "preferred_platforms": []
                        },
                        "completed_course_ids": []
                    })

            return count, errors

        except Exception as e:
            return 0, [f"Failed to read employee_skills.csv: {str(e)}"]

    @classmethod
    def ingest_competency_matrix(cls, file_path: str) -> Tuple[int, List[str]]:
        errors: List[str] = []
        roles_count = 0

        try:
            df = pd.read_excel(file_path)
            cols = {c.strip().lower(): c for c in df.columns}
            role_col = cols.get("role") or cols.get("target_role")
            skill_col = cols.get("skill") or cols.get("competency")
            prof_col = cols.get("required_proficiency") or cols.get("proficiency") or cols.get("target_proficiency")

            if not (role_col and skill_col and prof_col):
                return 0, [f"competency_matrix.xlsx missing columns."]

            grouped = df.groupby(role_col)
            for role_name, group in grouped:
                role_str = str(role_name).strip()
                competencies = []
                for _, row in group.iterrows():
                    sk = str(row[skill_col]).strip()
                    try:
                        p = int(row[prof_col])
                    except (ValueError, TypeError):
                        continue
                    competencies.append({"skill": sk, "required_proficiency": p})

                role_doc = {
                    "role_name": role_str,
                    "description": f"Role profile for {role_str} with {len(competencies)} target competencies.",
                    "competencies": competencies
                }
                repository.update("roles", {"role_name": role_str}, role_doc, upsert=True)
                roles_count += 1

            return roles_count, errors

        except Exception as e:
            return 0, [f"Failed to read competency_matrix.xlsx: {str(e)}"]

    @classmethod
    def ingest_policy_pdf(cls, file_path: str) -> Tuple[int, List[str]]:
        errors: List[str] = []
        try:
            reader = PdfReader(file_path)
            full_text = ""
            for idx, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    full_text += f"\n--- Page {idx+1} ---\n" + text

            policy_doc = {
                "document_name": "learning_policy.pdf",
                "content": full_text.strip(),
                "page_count": len(reader.pages)
            }
            repository.update("policies", {"document_name": "learning_policy.pdf"}, policy_doc, upsert=True)
            return 1, errors

        except Exception as e:
            return 0, [f"Failed to read learning_policy.pdf: {str(e)}"]

    @classmethod
    def seed_default_users(cls):
        """Seed default user accounts if not present."""
        default_users = [
            {
                "user_id": "USR-LEARNER-01",
                "email": "learner@example.com",
                "password_hash": hash_password("learner123"),
                "name": "Priya Sharma (Individual Learner)",
                "role": "learner",
                "is_employee": False,
                "employee_id": None,
                "department": "Independent Self-Learner"
            },
            {
                "user_id": "USR-EMP-E2001",
                "email": "employee@example.com",
                "password_hash": hash_password("employee123"),
                "name": "Alex Mercer (Employee E2001)",
                "role": "learner",
                "is_employee": True,
                "employee_id": "E2001",
                "department": "Data & Analytics"
            },
            {
                "user_id": "USR-MGR-M1001",
                "email": "manager@example.com",
                "password_hash": hash_password("manager123"),
                "name": "David Chen (Engineering Manager)",
                "role": "manager",
                "is_employee": True,
                "employee_id": "M1001",
                "department": "Engineering Leadership"
            },
            {
                "user_id": "USR-ADM-A1001",
                "email": "admin@example.com",
                "password_hash": hash_password("admin123"),
                "name": "System Administrator",
                "role": "admin",
                "is_employee": True,
                "employee_id": "A1001",
                "department": "Learning & Development Admin"
            }
        ]

        for u in default_users:
            existing = repository.find_one("users", {"email": u["email"]})
            if not existing:
                repository.insert("users", u)
