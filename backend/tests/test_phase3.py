"""
Phase 3 tests: project requests, faculty workflow, lab assistant,
admin management routes, and notification delivery.
"""
import pytest
from bson import ObjectId
from datetime import datetime, timezone, timedelta


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _future_iso(hours=48):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _register_login(c, email, role="student", password="Test@12345"):
    c.post("/api/auth/register", json={
        "name": "Test", "email": email, "password": password, "role": role,
    })
    resp = c.post("/api/auth/login", json={"email": email, "password": password})
    return resp.get_json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_equipment(db, status="available", qty=5):
    eid = ObjectId()
    db.equipment.insert_one({
        "_id": eid, "name": "Test Equip", "status": status,
        "quantity_available": qty, "quantity_total": qty,
        "lab_id": ObjectId(), "department_id": ObjectId(),
        "category": "Test", "condition": "good",
        "serial_number": str(eid)[:8], "description": "",
        "image_url": None, "specifications": {}, "tags": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return eid


def _project_payload(equip_id=None):
    return {
        "title": "AI Research Project",
        "description": "Using Jetson Nano for edge inference",
        "deadline": _future_iso(72),
        "equipment_needed": [
            {"equipment_id": str(equip_id or ObjectId()), "quantity": 1, "duration_hours": 4}
        ],
    }


# ════════════════════════════════════════════════════════════════════
# PROJECT REQUEST TESTS
# ════════════════════════════════════════════════════════════════════

class TestProjectCreate:
    def test_student_can_create_project(self, client):
        c, db = client
        token = _register_login(c, "proj_create@test.edu", "student")
        resp = c.post("/api/projects/", headers=_auth(token),
                      json=_project_payload())
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["project_request"]["status"] == "draft"
        assert data["project_request"]["title"] == "AI Research Project"

    def test_faculty_cannot_create_project(self, client):
        c, db = client
        token = _register_login(c, "proj_fac@test.edu", "faculty")
        resp = c.post("/api/projects/", headers=_auth(token),
                      json=_project_payload())
        assert resp.status_code == 403

    def test_missing_title_rejected(self, client):
        c, _ = client
        token = _register_login(c, "proj_notitle@test.edu", "student")
        payload = _project_payload()
        del payload["title"]
        resp = c.post("/api/projects/", headers=_auth(token), json=payload)
        assert resp.status_code == 400
        assert "title" in resp.get_json()["error"]

    def test_missing_equipment_rejected(self, client):
        c, _ = client
        token = _register_login(c, "proj_noequip@test.edu", "student")
        payload = _project_payload()
        payload["equipment_needed"] = []
        resp = c.post("/api/projects/", headers=_auth(token), json=payload)
        assert resp.status_code == 400

    def test_invalid_deadline_rejected(self, client):
        c, _ = client
        token = _register_login(c, "proj_baddl@test.edu", "student")
        payload = _project_payload()
        payload["deadline"] = "not-a-date"
        resp = c.post("/api/projects/", headers=_auth(token), json=payload)
        assert resp.status_code == 400


class TestProjectList:
    def test_student_sees_own_only(self, client):
        c, db = client
        t1 = _register_login(c, "plist1@test.edu", "student")
        t2 = _register_login(c, "plist2@test.edu", "student")
        c.post("/api/projects/", headers=_auth(t1), json=_project_payload())
        c.post("/api/projects/", headers=_auth(t2), json=_project_payload())

        resp = c.get("/api/projects/", headers=_auth(t1))
        assert resp.status_code == 200
        u1 = db.users.find_one({"email": "plist1@test.edu"})
        for item in resp.get_json()["items"]:
            assert str(item["student_id"]) == str(u1["_id"])

    def test_faculty_sees_all(self, client):
        c, db = client
        t_s = _register_login(c, "plist_s@test.edu", "student")
        t_f = _register_login(c, "plist_f@test.edu", "faculty")
        c.post("/api/projects/", headers=_auth(t_s), json=_project_payload())
        resp = c.get("/api/projects/", headers=_auth(t_f))
        assert resp.status_code == 200
        assert resp.get_json()["total"] >= 1


class TestProjectUpdate:
    def test_student_can_update_draft(self, client):
        c, db = client
        token = _register_login(c, "pupd@test.edu", "student")
        r = c.post("/api/projects/", headers=_auth(token), json=_project_payload())
        pid = r.get_json()["project_request"]["_id"]
        resp = c.put(f"/api/projects/{pid}", headers=_auth(token),
                     json={"title": "Updated Title"})
        assert resp.status_code == 200
        assert resp.get_json()["project_request"]["title"] == "Updated Title"

    def test_cannot_update_submitted(self, client):
        c, db = client
        token = _register_login(c, "pnotsub@test.edu", "student")
        r = c.post("/api/projects/", headers=_auth(token), json=_project_payload())
        pid = r.get_json()["project_request"]["_id"]
        c.put(f"/api/projects/{pid}/submit", headers=_auth(token))
        resp = c.put(f"/api/projects/{pid}", headers=_auth(token),
                     json={"title": "Hack"})
        assert resp.status_code == 400

    def test_student_cannot_update_others(self, client):
        c, db = client
        t1 = _register_login(c, "pown1@test.edu", "student")
        t2 = _register_login(c, "pown2@test.edu", "student")
        r = c.post("/api/projects/", headers=_auth(t1), json=_project_payload())
        pid = r.get_json()["project_request"]["_id"]
        resp = c.put(f"/api/projects/{pid}", headers=_auth(t2),
                     json={"title": "Steal"})
        assert resp.status_code == 400
        assert "own" in resp.get_json()["error"].lower()


class TestProjectSubmitAndReview:
    def _create_and_submit(self, c, stu_email):
        token = _register_login(c, stu_email, "student")
        r = c.post("/api/projects/", headers=_auth(token), json=_project_payload())
        pid = r.get_json()["project_request"]["_id"]
        c.put(f"/api/projects/{pid}/submit", headers=_auth(token))
        return token, pid

    def test_submit_changes_status(self, client):
        c, db = client
        token, pid = self._create_and_submit(c, "psub_s@test.edu")
        resp = c.get(f"/api/projects/{pid}", headers=_auth(token))
        assert resp.get_json()["status"] == "submitted"

    def test_faculty_approves_project(self, client):
        c, db = client
        _, pid = self._create_and_submit(c, "pappr_s@test.edu")
        t_f = _register_login(c, "pappr_f@test.edu", "faculty")
        resp = c.put(f"/api/projects/{pid}/review", headers=_auth(t_f),
                     json={"decision": "approved", "notes": "Excellent project"})
        assert resp.status_code == 200
        assert resp.get_json()["project_request"]["status"] == "approved"

    def test_faculty_rejects_with_notes(self, client):
        c, db = client
        _, pid = self._create_and_submit(c, "prej_s@test.edu")
        t_f = _register_login(c, "prej_f@test.edu", "faculty")
        resp = c.put(f"/api/projects/{pid}/review", headers=_auth(t_f),
                     json={"decision": "rejected", "notes": "Insufficient detail"})
        assert resp.status_code == 200
        assert resp.get_json()["project_request"]["status"] == "rejected"

    def test_reject_without_notes_fails(self, client):
        c, db = client
        _, pid = self._create_and_submit(c, "prej2_s@test.edu")
        t_f = _register_login(c, "prej2_f@test.edu", "faculty")
        resp = c.put(f"/api/projects/{pid}/review", headers=_auth(t_f),
                     json={"decision": "rejected"})
        assert resp.status_code == 400

    def test_student_cannot_review(self, client):
        c, db = client
        t_s, pid = self._create_and_submit(c, "pself_s@test.edu")
        resp = c.put(f"/api/projects/{pid}/review", headers=_auth(t_s),
                     json={"decision": "approved"})
        assert resp.status_code == 403

    def test_cannot_review_draft(self, client):
        c, db = client
        t_s = _register_login(c, "pdraft_s@test.edu", "student")
        r = c.post("/api/projects/", headers=_auth(t_s), json=_project_payload())
        pid = r.get_json()["project_request"]["_id"]
        t_f = _register_login(c, "pdraft_f@test.edu", "faculty")
        resp = c.put(f"/api/projects/{pid}/review", headers=_auth(t_f),
                     json={"decision": "approved"})
        assert resp.status_code == 400

    def test_review_notifies_student(self, client):
        c, db = client
        _, pid = self._create_and_submit(c, "pnotif_s@test.edu")
        t_f = _register_login(c, "pnotif_f@test.edu", "faculty")
        c.put(f"/api/projects/{pid}/review", headers=_auth(t_f),
              json={"decision": "approved", "notes": "Go ahead"})
        stu = db.users.find_one({"email": "pnotif_s@test.edu"})
        notif = db.notifications.find_one({"user_id": stu["_id"]})
        assert notif is not None


# ════════════════════════════════════════════════════════════════════
# FACULTY ROUTE TESTS
# ════════════════════════════════════════════════════════════════════

class TestFacultyDashboard:
    def test_dashboard_returns_counts(self, client):
        c, db = client
        token = _register_login(c, "facdash@test.edu", "faculty")
        resp = c.get("/api/faculty/dashboard", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert "pending_bookings_count" in data
        assert "pending_projects_count" in data
        assert "approved_today" in data

    def test_student_cannot_see_faculty_dashboard(self, client):
        c, _ = client
        token = _register_login(c, "facstu@test.edu", "student")
        resp = c.get("/api/faculty/dashboard", headers=_auth(token))
        assert resp.status_code == 403


class TestFacultyRequests:
    def test_pending_requests_list(self, client):
        c, db = client
        # Create a pending booking
        eid = _make_equipment(db)
        t_s = _register_login(c, "facreq_s@test.edu", "student")
        c.post("/api/bookings/", headers=_auth(t_s), json={
            "equipment_id": str(eid),
            "start_time": _future_iso(2),
            "end_time": _future_iso(4),
            "purpose": "Research",
        })
        t_f = _register_login(c, "facreq_f@test.edu", "faculty")
        resp = c.get("/api/faculty/requests", headers=_auth(t_f))
        assert resp.status_code == 200
        assert resp.get_json()["total"] >= 1


class TestFacultySchedule:
    def test_schedule_returns_week_range(self, client):
        c, _ = client
        token = _register_login(c, "facsched@test.edu", "faculty")
        resp = c.get("/api/faculty/schedule?date=2027-01-15", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert "week_start" in data
        assert "week_end" in data
        assert "bookings" in data

    def test_invalid_date_returns_400(self, client):
        c, _ = client
        token = _register_login(c, "facsched2@test.edu", "faculty")
        resp = c.get("/api/faculty/schedule?date=bad-date", headers=_auth(token))
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# LAB ASSISTANT ROUTE TESTS
# ════════════════════════════════════════════════════════════════════

class TestLabAssistant:
    def test_lab_assistant_can_list_equipment(self, client):
        c, db = client
        _make_equipment(db)
        token = _register_login(c, "la_list@test.edu", "lab_assistant")
        resp = c.get("/api/lab/equipment", headers=_auth(token))
        assert resp.status_code == 200
        assert "items" in resp.get_json()

    def test_student_cannot_list_lab_equipment(self, client):
        c, _ = client
        token = _register_login(c, "la_stu@test.edu", "student")
        resp = c.get("/api/lab/equipment", headers=_auth(token))
        assert resp.status_code == 403

    def test_update_condition_endpoint(self, client):
        c, db = client
        eid = _make_equipment(db)
        token = _register_login(c, "la_cond@test.edu", "lab_assistant")
        resp = c.put(f"/api/lab/equipment/{eid}/condition", headers=_auth(token),
                     json={"condition": "fair"})
        assert resp.status_code == 200
        assert resp.get_json()["equipment"]["condition"] == "fair"

    def test_update_status_endpoint(self, client):
        c, db = client
        eid = _make_equipment(db)
        token = _register_login(c, "la_stat@test.edu", "lab_assistant")
        resp = c.put(f"/api/lab/equipment/{eid}/status", headers=_auth(token),
                     json={"status": "maintenance"})
        assert resp.status_code == 200
        assert resp.get_json()["equipment"]["status"] == "maintenance"

    def test_invalid_status_rejected(self, client):
        c, db = client
        eid = _make_equipment(db)
        token = _register_login(c, "la_invstat@test.edu", "lab_assistant")
        resp = c.put(f"/api/lab/equipment/{eid}/status", headers=_auth(token),
                     json={"status": "broken"})
        assert resp.status_code == 400

    def test_handovers_list(self, client):
        c, db = client
        token = _register_login(c, "la_hand@test.edu", "lab_assistant")
        resp = c.get("/api/lab/handovers", headers=_auth(token))
        assert resp.status_code == 200
        assert "handovers" in resp.get_json()

    def test_mark_return(self, client):
        c, db = client
        # Insert a booking in approved status
        eid = _make_equipment(db)
        bk_id = ObjectId()
        db.bookings.insert_one({
            "_id": bk_id,
            "equipment_id": eid,
            "student_id": ObjectId(),
            "lab_id": ObjectId(),
            "status": "approved",
            "start_time": datetime.now(timezone.utc),
            "end_time": datetime.now(timezone.utc) + timedelta(hours=2),
            "purpose": "Test",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })
        token = _register_login(c, "la_ret@test.edu", "lab_assistant")
        resp = c.post(f"/api/lab/handovers/{bk_id}/return", headers=_auth(token))
        assert resp.status_code == 200
        updated = db.bookings.find_one({"_id": bk_id})
        assert updated["status"] == "completed"

    def test_maintenance_list(self, client):
        c, _ = client
        token = _register_login(c, "la_maint@test.edu", "lab_assistant")
        resp = c.get("/api/lab/maintenance", headers=_auth(token))
        assert resp.status_code == 200
        assert "maintenance_records" in resp.get_json()


# ════════════════════════════════════════════════════════════════════
# ADMIN MANAGEMENT TESTS
# ════════════════════════════════════════════════════════════════════

class TestAdminDashboard:
    def test_admin_dashboard_returns_stats(self, client):
        c, _ = client
        token = _register_login(c, "adm_dash@test.edu", "admin")
        resp = c.get("/api/admin/dashboard", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        for key in ("total_users", "total_equipment", "total_bookings", "pending_bookings"):
            assert key in data

    def test_student_cannot_access_admin_dashboard(self, client):
        c, _ = client
        token = _register_login(c, "adm_stu@test.edu", "student")
        resp = c.get("/api/admin/dashboard", headers=_auth(token))
        assert resp.status_code == 403


class TestAdminUserManagement:
    def test_admin_lists_users(self, client):
        c, _ = client
        token = _register_login(c, "adm_lstusr@test.edu", "admin")
        resp = c.get("/api/admin/users", headers=_auth(token))
        assert resp.status_code == 200
        assert "items" in resp.get_json()

    def test_admin_creates_user(self, client):
        c, _ = client
        token = _register_login(c, "adm_crtusr@test.edu", "admin")
        resp = c.post("/api/admin/users", headers=_auth(token), json={
            "name": "New Faculty",
            "email": "newfac@test.edu",
            "password": "Faculty@123",
            "role": "faculty",
        })
        assert resp.status_code == 201
        assert resp.get_json()["user"]["role"] == "faculty"

    def test_admin_cannot_create_duplicate(self, client):
        c, _ = client
        token = _register_login(c, "adm_dup@test.edu", "admin")
        payload = {"name": "Dup", "email": "dupuser@test.edu", "password": "Dup@12345", "role": "student"}
        c.post("/api/admin/users", headers=_auth(token), json=payload)
        resp = c.post("/api/admin/users", headers=_auth(token), json=payload)
        assert resp.status_code == 400

    def test_admin_updates_user(self, client):
        c, db = client
        token = _register_login(c, "adm_updusr@test.edu", "admin")
        # Create user first
        c.post("/api/admin/users", headers=_auth(token), json={
            "name": "ToUpdate", "email": "toupdate@test.edu",
            "password": "Update@123", "role": "student",
        })
        user = db.users.find_one({"email": "toupdate@test.edu"})
        resp = c.put(f"/api/admin/users/{user['_id']}", headers=_auth(token),
                     json={"name": "UpdatedName"})
        assert resp.status_code == 200
        assert resp.get_json()["user"]["name"] == "UpdatedName"

    def test_admin_deletes_user(self, client):
        c, db = client
        token = _register_login(c, "adm_delusr@test.edu", "admin")
        c.post("/api/admin/users", headers=_auth(token), json={
            "name": "ToDelete", "email": "todelete@test.edu",
            "password": "Delete@123", "role": "student",
        })
        user = db.users.find_one({"email": "todelete@test.edu"})
        resp = c.delete(f"/api/admin/users/{user['_id']}", headers=_auth(token))
        assert resp.status_code == 200
        assert db.users.find_one({"email": "todelete@test.edu"}) is None

    def test_admin_cannot_delete_self(self, client):
        c, db = client
        token = _register_login(c, "adm_self@test.edu", "admin")
        me = db.users.find_one({"email": "adm_self@test.edu"})
        resp = c.delete(f"/api/admin/users/{me['_id']}", headers=_auth(token))
        assert resp.status_code == 400
        assert "own" in resp.get_json()["error"].lower()


class TestAdminDepartmentManagement:
    def test_admin_creates_department(self, client):
        c, _ = client
        token = _register_login(c, "adm_dept@test.edu", "admin")
        resp = c.post("/api/admin/departments", headers=_auth(token),
                      json={"name": "Physics", "code": "PHY"})
        assert resp.status_code == 201
        assert resp.get_json()["department"]["name"] == "Physics"

    def test_duplicate_department_rejected(self, client):
        c, _ = client
        token = _register_login(c, "adm_deptdup@test.edu", "admin")
        c.post("/api/admin/departments", headers=_auth(token), json={"name": "UniqueD", "code": "UD"})
        resp = c.post("/api/admin/departments", headers=_auth(token), json={"name": "UniqueD", "code": "UD"})
        assert resp.status_code == 400

    def test_list_departments_accessible_to_all(self, client):
        c, _ = client
        token = _register_login(c, "adm_deptlist@test.edu", "student")
        resp = c.get("/api/admin/departments", headers=_auth(token))
        assert resp.status_code == 200

    def test_admin_deletes_department(self, client):
        c, db = client
        token = _register_login(c, "adm_deptdel@test.edu", "admin")
        r = c.post("/api/admin/departments", headers=_auth(token),
                   json={"name": "TempDept", "code": "TD"})
        did = r.get_json()["department"]["_id"]
        resp = c.delete(f"/api/admin/departments/{did}", headers=_auth(token))
        assert resp.status_code == 200


class TestAdminLabManagement:
    def _make_dept(self, db):
        did = ObjectId()
        db.departments.insert_one({"_id": did, "name": f"D{did}", "code": "D"})
        return did

    def test_admin_creates_lab(self, client):
        c, db = client
        did = self._make_dept(db)
        token = _register_login(c, "adm_lab@test.edu", "admin")
        resp = c.post("/api/admin/laboratories", headers=_auth(token), json={
            "name": "AI Lab", "department_id": str(did),
            "location": "Block A", "capacity": 20,
        })
        assert resp.status_code == 201
        assert resp.get_json()["laboratory"]["name"] == "AI Lab"

    def test_lab_requires_department(self, client):
        c, _ = client
        token = _register_login(c, "adm_labno@test.edu", "admin")
        resp = c.post("/api/admin/laboratories", headers=_auth(token),
                      json={"name": "No Dept Lab"})
        assert resp.status_code == 400

    def test_list_labs_accessible_to_all(self, client):
        c, _ = client
        token = _register_login(c, "adm_lablist@test.edu", "student")
        resp = c.get("/api/admin/laboratories", headers=_auth(token))
        assert resp.status_code == 200


class TestAdminBookingView:
    def test_admin_sees_all_bookings(self, client):
        c, db = client
        eid = _make_equipment(db)
        t_s = _register_login(c, "admbk_s@test.edu", "student")
        c.post("/api/bookings/", headers=_auth(t_s), json={
            "equipment_id": str(eid),
            "start_time": _future_iso(2),
            "end_time": _future_iso(4),
            "purpose": "Test",
        })
        t_a = _register_login(c, "admbk_a@test.edu", "admin")
        resp = c.get("/api/admin/bookings", headers=_auth(t_a))
        assert resp.status_code == 200
        assert resp.get_json()["total"] >= 1

    def test_admin_filters_by_status(self, client):
        c, db = client
        eid = _make_equipment(db)
        t_s = _register_login(c, "admbkst_s@test.edu", "student")
        c.post("/api/bookings/", headers=_auth(t_s), json={
            "equipment_id": str(eid),
            "start_time": _future_iso(2),
            "end_time": _future_iso(4),
            "purpose": "Test",
        })
        t_a = _register_login(c, "admbkst_a@test.edu", "admin")
        resp = c.get("/api/admin/bookings?status=pending", headers=_auth(t_a))
        data = resp.get_json()
        assert all(i["status"] == "pending" for i in data["items"])
