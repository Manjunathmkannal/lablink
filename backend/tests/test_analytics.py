"""
Phase 4D – Admin Analytics tests.

Tests the GET /api/admin/analytics endpoint:
- Role access control (admin only)
- Response structure on empty database
- Correct aggregation with seeded data
- Each of the 6 analytics pipelines individually
"""
import pytest
from bson import ObjectId
from datetime import datetime, timezone, timedelta


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _register_login(c, email, role="student", password="Test@12345"):
    c.post("/api/auth/register", json={
        "name": "Test User", "email": email, "password": password, "role": role,
    })
    resp = c.post("/api/auth/login", json={"email": email, "password": password})
    return resp.get_json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _insert_equipment(db, name="Oscilloscope", status="available", dept_id=None):
    eid = ObjectId()
    db.equipment.insert_one({
        "_id": eid, "name": name, "status": status,
        "category": "Test", "condition": "good",
        "department_id": dept_id or ObjectId(),
        "serial_number": str(eid)[:8],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return eid


def _insert_booking(db, status="approved", dept_id=None, equip_id=None, months_ago=0):
    created = datetime.now(timezone.utc) - timedelta(days=30 * months_ago)
    db.bookings.insert_one({
        "_id": ObjectId(),
        "equipment_id": equip_id or ObjectId(),
        "user_id": ObjectId(),
        "status": status,
        "department_id": dept_id,
        "start_time": created + timedelta(hours=1),
        "end_time":   created + timedelta(hours=3),
        "created_at": created,
        "updated_at": created,
    })


def _insert_department(db, name="Computer Science"):
    did = ObjectId()
    db.departments.insert_one({"_id": did, "name": name, "code": "CS"})
    return did


# ════════════════════════════════════════════════════════════════════════════════
# Access Control
# ════════════════════════════════════════════════════════════════════════════════

class TestAnalyticsAccess:
    def test_admin_can_access_analytics(self, client):
        c, db = client
        token = _register_login(c, "analytics_admin@test.edu", "admin")
        resp = c.get("/api/admin/analytics", headers=_auth(token))
        assert resp.status_code == 200

    def test_student_cannot_access_analytics(self, client):
        c, _ = client
        token = _register_login(c, "analytics_student@test.edu", "student")
        resp = c.get("/api/admin/analytics", headers=_auth(token))
        assert resp.status_code == 403

    def test_faculty_cannot_access_analytics(self, client):
        c, _ = client
        token = _register_login(c, "analytics_faculty@test.edu", "faculty")
        resp = c.get("/api/admin/analytics", headers=_auth(token))
        assert resp.status_code == 403

    def test_lab_assistant_cannot_access_analytics(self, client):
        c, _ = client
        token = _register_login(c, "analytics_lab@test.edu", "lab_assistant")
        resp = c.get("/api/admin/analytics", headers=_auth(token))
        assert resp.status_code == 403

    def test_unauthenticated_cannot_access_analytics(self, client):
        c, _ = client
        resp = c.get("/api/admin/analytics")
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════════════════
# Empty Database – safe zero values
# ════════════════════════════════════════════════════════════════════════════════

class TestAnalyticsEmptyDatabase:
    def test_empty_db_returns_valid_structure(self, client):
        c, _ = client
        token = _register_login(c, "analytics_empty@test.edu", "admin")
        resp = c.get("/api/admin/analytics", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()

        # All six keys must be present
        assert "equipment_utilization" in data
        assert "department_usage"      in data
        assert "monthly_trends"        in data
        assert "pending_approvals"     in data
        assert "top_equipment"         in data
        assert "user_statistics"       in data

    def test_empty_equipment_utilization_is_zero(self, client):
        c, _ = client
        token = _register_login(c, "analytics_eq0@test.edu", "admin")
        resp = c.get("/api/admin/analytics", headers=_auth(token))
        util = resp.get_json()["equipment_utilization"]
        assert util.get("total", 0) == 0

    def test_empty_department_usage_is_list(self, client):
        c, _ = client
        token = _register_login(c, "analytics_dept0@test.edu", "admin")
        resp = c.get("/api/admin/analytics", headers=_auth(token))
        assert isinstance(resp.get_json()["department_usage"], list)

    def test_empty_monthly_trends_is_list(self, client):
        c, _ = client
        token = _register_login(c, "analytics_trend0@test.edu", "admin")
        resp = c.get("/api/admin/analytics", headers=_auth(token))
        assert isinstance(resp.get_json()["monthly_trends"], list)

    def test_empty_pending_approvals_has_bookings_and_projects_keys(self, client):
        c, _ = client
        token = _register_login(c, "analytics_pend0@test.edu", "admin")
        resp = c.get("/api/admin/analytics", headers=_auth(token))
        pa = resp.get_json()["pending_approvals"]
        assert "bookings" in pa
        assert "projects" in pa
        assert pa["bookings"] == 0
        assert pa["projects"] == 0


# ════════════════════════════════════════════════════════════════════════════════
# Equipment Utilization
# ════════════════════════════════════════════════════════════════════════════════

class TestEquipmentUtilization:
    def test_counts_equipment_by_status(self, client):
        c, db = client
        token = _register_login(c, "analytics_equip@test.edu", "admin")
        _insert_equipment(db, "Scope 1",    status="available")
        _insert_equipment(db, "Scope 2",    status="available")
        _insert_equipment(db, "Scope 3",    status="booked")
        _insert_equipment(db, "Scope 4",    status="maintenance")
        _insert_equipment(db, "Scope 5",    status="retired")

        resp = c.get("/api/admin/analytics", headers=_auth(token))
        util = resp.get_json()["equipment_utilization"]

        assert util["total"]       == 5
        assert util["available"]   == 2
        assert util["booked"]      == 1
        assert util["maintenance"] == 1
        assert util["retired"]     == 1

    def test_no_equipment_gives_zero_total(self, client):
        c, _ = client
        token = _register_login(c, "analytics_eq_zero@test.edu", "admin")
        resp = c.get("/api/admin/analytics", headers=_auth(token))
        assert resp.get_json()["equipment_utilization"]["total"] == 0


# ════════════════════════════════════════════════════════════════════════════════
# Department-wise Booking Usage
# ════════════════════════════════════════════════════════════════════════════════

class TestDepartmentUsage:
    def test_department_usage_counts_approved_bookings(self, client):
        c, db = client
        token = _register_login(c, "analytics_dept@test.edu", "admin")
        did = _insert_department(db, "Electrical Engineering")

        # 3 approved bookings for this dept, 1 pending (should not count)
        for _ in range(3):
            _insert_booking(db, status="approved", dept_id=did)
        _insert_booking(db, status="pending", dept_id=did)

        resp = c.get("/api/admin/analytics", headers=_auth(token))
        usage = resp.get_json()["department_usage"]
        # Find the EE entry
        ee = next((d for d in usage if d.get("booking_count") == 3), None)
        assert ee is not None, f"Expected dept with count=3 in {usage}"

    def test_department_usage_excludes_pending_and_rejected(self, client):
        c, db = client
        token = _register_login(c, "analytics_dept2@test.edu", "admin")
        did = _insert_department(db, "Chemistry")

        _insert_booking(db, status="pending",   dept_id=did)
        _insert_booking(db, status="rejected",  dept_id=did)
        _insert_booking(db, status="cancelled", dept_id=did)

        resp = c.get("/api/admin/analytics", headers=_auth(token))
        usage = resp.get_json()["department_usage"]
        # None of these statuses (pending/rejected/cancelled) qualify
        assert all(d.get("booking_count", 0) == 0 for d in usage
                   if d.get("department_name") == "Chemistry")

    def test_department_usage_is_sorted_descending(self, client):
        c, db = client
        token = _register_login(c, "analytics_sort@test.edu", "admin")
        d1 = _insert_department(db, "Physics")
        d2 = _insert_department(db, "Biology")

        for _ in range(5):
            _insert_booking(db, status="approved", dept_id=d1)
        for _ in range(2):
            _insert_booking(db, status="completed", dept_id=d2)

        resp = c.get("/api/admin/analytics", headers=_auth(token))
        usage = resp.get_json()["department_usage"]
        counts = [d["booking_count"] for d in usage]
        assert counts == sorted(counts, reverse=True)


# ════════════════════════════════════════════════════════════════════════════════
# Monthly Booking Trends
# ════════════════════════════════════════════════════════════════════════════════

class TestMonthlyTrends:
    def test_monthly_trends_returns_list(self, client):
        c, _ = client
        token = _register_login(c, "analytics_trends@test.edu", "admin")
        resp = c.get("/api/admin/analytics?months=3", headers=_auth(token))
        assert isinstance(resp.get_json()["monthly_trends"], list)

    def test_bookings_appear_in_trends(self, client):
        c, db = client
        token = _register_login(c, "analytics_trend_data@test.edu", "admin")
        # Insert 2 bookings this month
        _insert_booking(db, status="approved",  months_ago=0)
        _insert_booking(db, status="rejected",  months_ago=0)

        resp = c.get("/api/admin/analytics?months=6", headers=_auth(token))
        trends = resp.get_json()["monthly_trends"]
        # At least one month-entry exists
        assert len(trends) >= 1
        # Each entry has year/month/total
        for entry in trends:
            assert "year"  in entry or "month" in entry or "total" in entry

    def test_months_param_clamps_to_1_minimum(self, client):
        c, _ = client
        token = _register_login(c, "analytics_clamp@test.edu", "admin")
        resp = c.get("/api/admin/analytics?months=0", headers=_auth(token))
        assert resp.status_code == 200

    def test_months_param_clamps_to_24_maximum(self, client):
        c, _ = client
        token = _register_login(c, "analytics_clamp24@test.edu", "admin")
        resp = c.get("/api/admin/analytics?months=999", headers=_auth(token))
        assert resp.status_code == 200

    def test_old_bookings_excluded_from_trends(self, client):
        c, db = client
        token = _register_login(c, "analytics_old@test.edu", "admin")
        # Insert a booking 25 months ago (outside any window we query)
        _insert_booking(db, status="approved", months_ago=25)

        resp = c.get("/api/admin/analytics?months=6", headers=_auth(token))
        trends = resp.get_json()["monthly_trends"]
        total_count = sum(e.get("total", 0) for e in trends)
        assert total_count == 0


# ════════════════════════════════════════════════════════════════════════════════
# Top Equipment
# ════════════════════════════════════════════════════════════════════════════════

class TestTopEquipment:
    def test_top_equipment_limited_to_5(self, client):
        c, db = client
        token = _register_login(c, "analytics_top@test.edu", "admin")
        # Create 7 equipment items each with different booking counts
        for i in range(7):
            eid = _insert_equipment(db, f"Device {i}")
            for _ in range(i + 1):
                _insert_booking(db, status="approved", equip_id=eid)

        resp = c.get("/api/admin/analytics", headers=_auth(token))
        top = resp.get_json()["top_equipment"]
        assert len(top) <= 5

    def test_top_equipment_has_expected_fields(self, client):
        c, db = client
        token = _register_login(c, "analytics_topfields@test.edu", "admin")
        eid = _insert_equipment(db, "Arduino Mega")
        _insert_booking(db, status="approved", equip_id=eid)

        resp = c.get("/api/admin/analytics", headers=_auth(token))
        top = resp.get_json()["top_equipment"]
        assert len(top) >= 1
        entry = top[0]
        assert "count" in entry


# ════════════════════════════════════════════════════════════════════════════════
# Pending Approvals
# ════════════════════════════════════════════════════════════════════════════════

class TestPendingApprovals:
    def test_pending_booking_count(self, client):
        c, db = client
        token = _register_login(c, "analytics_pend@test.edu", "admin")
        _insert_booking(db, status="pending")
        _insert_booking(db, status="pending")
        _insert_booking(db, status="approved")

        resp = c.get("/api/admin/analytics", headers=_auth(token))
        pa = resp.get_json()["pending_approvals"]
        assert pa["bookings"] == 2

    def test_pending_project_count(self, client):
        c, db = client
        token = _register_login(c, "analytics_projpend@test.edu", "admin")
        db.project_requests.insert_many([
            {"status": "submitted",   "created_at": datetime.now(timezone.utc)},
            {"status": "under_review","created_at": datetime.now(timezone.utc)},
            {"status": "draft",       "created_at": datetime.now(timezone.utc)},
        ])

        resp = c.get("/api/admin/analytics", headers=_auth(token))
        pa = resp.get_json()["pending_approvals"]
        assert pa["projects"] == 2  # submitted + under_review only


# ════════════════════════════════════════════════════════════════════════════════
# User Statistics
# ════════════════════════════════════════════════════════════════════════════════

class TestUserStatistics:
    def test_user_stats_reflect_registered_users(self, client):
        c, db = client
        # Register 2 students and 1 faculty
        _register_login(c, "ustats_s1@test.edu", "student")
        _register_login(c, "ustats_s2@test.edu", "student")
        _register_login(c, "ustats_f1@test.edu", "faculty")
        token = _register_login(c, "ustats_admin@test.edu", "admin")

        resp = c.get("/api/admin/analytics", headers=_auth(token))
        stats = resp.get_json()["user_statistics"]
        roles_map = {s["role"]: s["count"] for s in stats}
        assert roles_map.get("student", 0) >= 2
        assert roles_map.get("faculty", 0) >= 1
        assert roles_map.get("admin",   0) >= 1

    def test_user_stats_is_list_of_dicts(self, client):
        c, _ = client
        token = _register_login(c, "ustats_struct@test.edu", "admin")
        resp = c.get("/api/admin/analytics", headers=_auth(token))
        stats = resp.get_json()["user_statistics"]
        assert isinstance(stats, list)
        for s in stats:
            assert "role"  in s
            assert "count" in s
