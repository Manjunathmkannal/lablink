"""
Comprehensive tests for the equipment module.
Covers: CRUD, search, filter, pagination, deletion block, role permissions.
"""
import pytest
from unittest.mock import patch
from bson import ObjectId
from datetime import datetime, timezone


# ── Fixtures ───────────────────────────────────────────────────────────────────
# mock_db, app, client come from conftest.py


def _make_equipment(
    db,
    name="Oscilloscope",
    category="Instrument",
    status="available",
    qty=5,
    dept_id=None,
    lab_id=None,
):
    doc = {
        "_id": ObjectId(),
        "name": name,
        "description": f"A {name}",
        "category": category,
        "lab_id": lab_id or ObjectId(),
        "department_id": dept_id or ObjectId(),
        "serial_number": str(ObjectId())[:8],
        "quantity_total": qty,
        "quantity_available": qty,
        "condition": "good",
        "status": status,
        "image_url": None,
        "specifications": {},
        "tags": [name.lower()],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    db.equipment.insert_one(doc)
    return doc


def _register_login(c, email, role="student", password="Test@12345"):
    c.post("/api/auth/register", json={
        "name": "Test User", "email": email,
        "password": password, "role": role,
    })
    resp = c.post("/api/auth/login", json={"email": email, "password": password})
    return resp.get_json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Equipment list / search / filter ──────────────────────────────────────────

class TestEquipmentList:
    def test_list_returns_all(self, client):
        c, db = client
        dept = ObjectId()
        _make_equipment(db, name="Scope A", dept_id=dept)
        _make_equipment(db, name="Scope B", dept_id=dept)
        token = _register_login(c, "list@test.edu")
        resp = c.get("/api/equipment/", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 2

    def test_filter_by_status(self, client):
        c, db = client
        _make_equipment(db, name="Available", status="available")
        _make_equipment(db, name="Broken", status="maintenance")
        token = _register_login(c, "filterstatus@test.edu")
        resp = c.get("/api/equipment/?status=available", headers=_auth(token))
        assert resp.status_code == 200
        items = resp.get_json()["items"]
        assert all(i["status"] == "available" for i in items)

    def test_filter_by_category(self, client):
        c, db = client
        _make_equipment(db, name="Scope", category="Measurement")
        _make_equipment(db, name="Pi", category="Development Kit")
        token = _register_login(c, "filtercat@test.edu")
        resp = c.get("/api/equipment/?category=Measurement", headers=_auth(token))
        data = resp.get_json()
        assert all("Measurement" in i["category"] for i in data["items"])

    def test_pagination_page_and_per_page(self, client):
        c, db = client
        for i in range(5):
            _make_equipment(db, name=f"Item{i}")
        token = _register_login(c, "page@test.edu")
        resp = c.get("/api/equipment/?page=1&per_page=2", headers=_auth(token))
        data = resp.get_json()
        assert len(data["items"]) <= 2
        assert "pages" in data
        assert "total" in data

    def test_pagination_page2(self, client):
        c, db = client
        for i in range(6):
            _make_equipment(db, name=f"Paged{i}")
        token = _register_login(c, "page2@test.edu")
        r1 = c.get("/api/equipment/?page=1&per_page=3", headers=_auth(token))
        r2 = c.get("/api/equipment/?page=2&per_page=3", headers=_auth(token))
        ids1 = {i["_id"] for i in r1.get_json()["items"]}
        ids2 = {i["_id"] for i in r2.get_json()["items"]}
        # Page 2 items should not overlap with page 1
        assert ids1.isdisjoint(ids2)

    def test_requires_auth(self, client):
        c, _ = client
        resp = c.get("/api/equipment/")
        assert resp.status_code == 401


# ── Equipment detail ───────────────────────────────────────────────────────────

class TestEquipmentDetail:
    def test_get_existing(self, client):
        c, db = client
        eq = _make_equipment(db, name="DetailScope")
        token = _register_login(c, "detail@test.edu")
        resp = c.get(f"/api/equipment/{eq['_id']}", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "DetailScope"

    def test_get_nonexistent(self, client):
        c, _ = client
        token = _register_login(c, "noequip@test.edu")
        resp = c.get(f"/api/equipment/{ObjectId()}", headers=_auth(token))
        assert resp.status_code == 404


# ── Equipment create (admin only) ─────────────────────────────────────────────

class TestEquipmentCreate:
    def _admin_token(self, c):
        return _register_login(c, "admin_create@test.edu", role="admin")

    def test_admin_can_create(self, client):
        c, db = client
        token = self._admin_token(c)
        resp = c.post("/api/equipment/", headers=_auth(token), json={
            "name": "New Scope",
            "category": "Instrument",
            "quantity_total": 3,
            "condition": "good",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["equipment"]["name"] == "New Scope"
        assert data["equipment"]["quantity_available"] == 3

    def test_missing_name_rejected(self, client):
        c, _ = client
        token = self._admin_token(c)
        resp = c.post("/api/equipment/", headers=_auth(token), json={
            "category": "Instrument",
            "quantity_total": 2,
        })
        assert resp.status_code == 400

    def test_missing_category_rejected(self, client):
        c, _ = client
        token = self._admin_token(c)
        resp = c.post("/api/equipment/", headers=_auth(token), json={
            "name": "X",
            "quantity_total": 1,
        })
        assert resp.status_code == 400

    def test_student_cannot_create(self, client):
        c, _ = client
        token = _register_login(c, "stu_create@test.edu", role="student")
        resp = c.post("/api/equipment/", headers=_auth(token), json={
            "name": "X", "category": "Y", "quantity_total": 1,
        })
        assert resp.status_code == 403

    def test_faculty_cannot_create(self, client):
        c, _ = client
        token = _register_login(c, "fac_create@test.edu", role="faculty")
        resp = c.post("/api/equipment/", headers=_auth(token), json={
            "name": "X", "category": "Y", "quantity_total": 1,
        })
        assert resp.status_code == 403


# ── Equipment update ───────────────────────────────────────────────────────────

class TestEquipmentUpdate:
    def test_admin_can_update(self, client):
        c, db = client
        eq = _make_equipment(db, name="OldName")
        token = _register_login(c, "admin_upd@test.edu", role="admin")
        resp = c.put(f"/api/equipment/{eq['_id']}", headers=_auth(token),
                     json={"name": "NewName"})
        assert resp.status_code == 200
        assert resp.get_json()["equipment"]["name"] == "NewName"

    def test_lab_assistant_updates_condition(self, client):
        c, db = client
        eq = _make_equipment(db, name="CondScope")
        token = _register_login(c, "labassist_upd@test.edu", role="lab_assistant")
        resp = c.put(f"/api/equipment/{eq['_id']}", headers=_auth(token),
                     json={"condition": "fair", "status": "available"})
        assert resp.status_code == 200
        assert resp.get_json()["equipment"]["condition"] == "fair"

    def test_lab_assistant_needs_condition(self, client):
        c, db = client
        eq = _make_equipment(db, name="CondScope2")
        token = _register_login(c, "la2@test.edu", role="lab_assistant")
        resp = c.put(f"/api/equipment/{eq['_id']}", headers=_auth(token),
                     json={"name": "Trying"})
        assert resp.status_code == 400

    def test_student_cannot_update(self, client):
        c, db = client
        eq = _make_equipment(db, name="StuUpd")
        token = _register_login(c, "stu_upd@test.edu", role="student")
        resp = c.put(f"/api/equipment/{eq['_id']}", headers=_auth(token),
                     json={"name": "Hack"})
        assert resp.status_code == 403

    def test_update_nonexistent_returns_404(self, client):
        c, _ = client
        token = _register_login(c, "admin_404upd@test.edu", role="admin")
        resp = c.put(f"/api/equipment/{ObjectId()}", headers=_auth(token),
                     json={"name": "X"})
        assert resp.status_code == 404


# ── Equipment delete ───────────────────────────────────────────────────────────

class TestEquipmentDelete:
    def test_admin_can_delete(self, client):
        c, db = client
        eq = _make_equipment(db, name="DeleteMe")
        token = _register_login(c, "admin_del@test.edu", role="admin")
        resp = c.delete(f"/api/equipment/{eq['_id']}", headers=_auth(token))
        assert resp.status_code == 200
        # Confirm gone
        assert db.equipment.find_one({"_id": eq["_id"]}) is None

    def test_delete_nonexistent_returns_404(self, client):
        c, _ = client
        token = _register_login(c, "admin_del404@test.edu", role="admin")
        resp = c.delete(f"/api/equipment/{ObjectId()}", headers=_auth(token))
        assert resp.status_code == 404

    def test_delete_blocked_with_active_booking(self, client):
        c, db = client
        eq = _make_equipment(db, name="ActiveBooked")
        # Insert an active booking
        db.bookings.insert_one({
            "_id": ObjectId(),
            "equipment_id": eq["_id"],
            "status": "approved",
            "student_id": ObjectId(),
            "start_time": datetime.now(timezone.utc),
            "end_time": datetime.now(timezone.utc),
        })
        token = _register_login(c, "admin_blocked@test.edu", role="admin")
        resp = c.delete(f"/api/equipment/{eq['_id']}", headers=_auth(token))
        assert resp.status_code == 409
        assert "active" in resp.get_json()["error"].lower() or "booking" in resp.get_json()["error"].lower()

    def test_student_cannot_delete(self, client):
        c, db = client
        eq = _make_equipment(db, name="NoDelete")
        token = _register_login(c, "stu_del@test.edu", role="student")
        resp = c.delete(f"/api/equipment/{eq['_id']}", headers=_auth(token))
        assert resp.status_code == 403


# ── Availability calendar ─────────────────────────────────────────────────────

class TestAvailabilityCalendar:
    def test_day_view_returns_structure(self, client):
        c, db = client
        eq = _make_equipment(db, name="CalEquip")
        token = _register_login(c, "cal@test.edu")
        resp = c.get(
            f"/api/equipment/{eq['_id']}/availability?view=day&date=2027-01-15",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "bookings" in data
        assert "suggested_slots" in data
        assert data["view"] == "day"

    def test_week_view_returns_structure(self, client):
        c, db = client
        eq = _make_equipment(db, name="WeekEquip")
        token = _register_login(c, "week@test.edu")
        resp = c.get(
            f"/api/equipment/{eq['_id']}/availability?view=week&date=2027-01-15",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["view"] == "week"

    def test_month_view_returns_structure(self, client):
        c, db = client
        eq = _make_equipment(db, name="MonthEquip")
        token = _register_login(c, "month@test.edu")
        resp = c.get(
            f"/api/equipment/{eq['_id']}/availability?view=month&date=2027-01-01",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["view"] == "month"

    def test_invalid_date_returns_400(self, client):
        c, db = client
        eq = _make_equipment(db, name="InvDateEquip")
        token = _register_login(c, "invdate@test.edu")
        resp = c.get(
            f"/api/equipment/{eq['_id']}/availability?date=not-a-date",
            headers=_auth(token),
        )
        assert resp.status_code == 400
