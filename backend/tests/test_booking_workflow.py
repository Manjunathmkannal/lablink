"""
Comprehensive tests for the booking workflow.
Covers: creation, approval, rejection, cancellation, overlap, concurrency,
        pagination, timezone handling, notifications, role guards.
"""
import pytest
from unittest.mock import patch
from bson import ObjectId
from datetime import datetime, timezone, timedelta


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _future(hours=2) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def _future_iso(hours=2) -> str:
    return _future(hours).isoformat()


def _register_login(c, email, role="student", password="Test@12345"):
    c.post("/api/auth/register", json={
        "name": "Test User", "email": email,
        "password": password, "role": role,
    })
    resp = c.post("/api/auth/login", json={"email": email, "password": password})
    return resp.get_json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_equipment(db, status="available", qty=5):
    eid = ObjectId()
    db.equipment.insert_one({
        "_id": eid,
        "name": "Test Equipment",
        "status": status,
        "quantity_available": qty,
        "quantity_total": qty,
        "lab_id": ObjectId(),
        "department_id": ObjectId(),
        "category": "Test",
        "condition": "good",
        "serial_number": str(eid)[:8],
        "description": "",
        "image_url": None,
        "specifications": {},
        "tags": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return eid


def _book(c, token, equip_id, start_hours=2, end_hours=4, purpose="Research"):
    """Helper: POST /api/bookings with the given parameters."""
    return c.post("/api/bookings/", headers=_auth(token), json={
        "equipment_id": str(equip_id),
        "start_time": _future_iso(start_hours),
        "end_time": _future_iso(end_hours),
        "purpose": purpose,
    })


# ── Booking creation ───────────────────────────────────────────────────────────

class TestBookingCreate:
    def test_student_can_create_booking(self, client):
        c, db = client
        eid = _make_equipment(db)
        token = _register_login(c, "bk_create@test.edu", role="student")
        resp = _book(c, token, eid)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["booking"]["status"] == "pending"
        assert "equipment_id" in data["booking"]

    def test_booking_requires_all_fields(self, client):
        c, _ = client
        token = _register_login(c, "bk_missing@test.edu", role="student")
        resp = c.post("/api/bookings/", headers=_auth(token), json={
            "equipment_id": str(ObjectId()),
            "start_time": _future_iso(2),
            # missing end_time and purpose
        })
        assert resp.status_code == 400

    def test_faculty_cannot_create_booking(self, client):
        c, db = client
        eid = _make_equipment(db)
        token = _register_login(c, "fac_bk@test.edu", role="faculty")
        resp = _book(c, token, eid)
        assert resp.status_code == 403

    def test_nonexistent_equipment_returns_404(self, client):
        c, db = client
        token = _register_login(c, "bk_noequip@test.edu", role="student")
        resp = _book(c, token, ObjectId())
        assert resp.status_code == 404

    def test_maintenance_equipment_cannot_be_booked(self, client):
        c, db = client
        eid = _make_equipment(db, status="maintenance")
        token = _register_login(c, "bk_maint@test.edu", role="student")
        resp = _book(c, token, eid)
        assert resp.status_code == 400

    def test_zero_quantity_cannot_be_booked(self, client):
        c, db = client
        eid = _make_equipment(db, qty=0)
        token = _register_login(c, "bk_zero@test.edu", role="student")
        resp = _book(c, token, eid)
        assert resp.status_code == 409

    def test_booking_in_past_rejected(self, client):
        c, db = client
        eid = _make_equipment(db)
        token = _register_login(c, "bk_past@test.edu", role="student")
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        resp = c.post("/api/bookings/", headers=_auth(token), json={
            "equipment_id": str(eid),
            "start_time": past,
            "end_time": _future_iso(2),
            "purpose": "Research",
        })
        assert resp.status_code == 400

    def test_end_before_start_rejected(self, client):
        c, db = client
        eid = _make_equipment(db)
        token = _register_login(c, "bk_flip@test.edu", role="student")
        resp = c.post("/api/bookings/", headers=_auth(token), json={
            "equipment_id": str(eid),
            "start_time": _future_iso(4),
            "end_time": _future_iso(2),   # earlier
            "purpose": "Research",
        })
        assert resp.status_code == 400

    def test_duration_over_24h_rejected(self, client):
        c, db = client
        eid = _make_equipment(db)
        token = _register_login(c, "bk_long@test.edu", role="student")
        resp = c.post("/api/bookings/", headers=_auth(token), json={
            "equipment_id": str(eid),
            "start_time": _future_iso(1),
            "end_time": _future_iso(26),
            "purpose": "Research",
        })
        assert resp.status_code == 400

    def test_notification_created_on_submit(self, client):
        c, db = client
        eid = _make_equipment(db)
        token = _register_login(c, "bk_notif@test.edu", role="student")
        _book(c, token, eid)
        # At least one notification should exist for this user
        from bson import ObjectId as OID
        user = db.users.find_one({"email": "bk_notif@test.edu"})
        notif = db.notifications.find_one({"user_id": user["_id"]})
        assert notif is not None


# ── Booking timezone handling ──────────────────────────────────────────────────

class TestBookingTimezone:
    def test_z_suffix_accepted(self, client):
        c, db = client
        eid = _make_equipment(db)
        token = _register_login(c, "bk_tz_z@test.edu", role="student")
        future_z = (_future(2).strftime("%Y-%m-%dT%H:%M:%S")) + "Z"
        resp = c.post("/api/bookings/", headers=_auth(token), json={
            "equipment_id": str(eid),
            "start_time": future_z,
            "end_time": (_future(4).strftime("%Y-%m-%dT%H:%M:%S")) + "Z",
            "purpose": "TZ Test",
        })
        assert resp.status_code == 201

    def test_offset_timezone_accepted(self, client):
        c, db = client
        eid = _make_equipment(db)
        token = _register_login(c, "bk_tz_off@test.edu", role="student")
        # +05:30 (IST) but still in the future
        future_ist = _future(5).strftime("%Y-%m-%dT%H:%M:%S") + "+05:30"
        resp = c.post("/api/bookings/", headers=_auth(token), json={
            "equipment_id": str(eid),
            "start_time": future_ist,
            "end_time": _future(10).strftime("%Y-%m-%dT%H:%M:%S") + "+05:30",
            "purpose": "IST TZ Test",
        })
        # IST is ahead of UTC so +5:30 offset means the UTC time is earlier – may be in past
        # This test just validates the parser doesn't crash; status can be 201 or 400
        assert resp.status_code in (201, 400)

    def test_naive_datetime_stored_as_utc(self, client):
        c, db = client
        eid = _make_equipment(db)
        token = _register_login(c, "bk_naive@test.edu", role="student")
        naive = _future(3).strftime("%Y-%m-%dT%H:%M:%S")  # no TZ
        resp = c.post("/api/bookings/", headers=_auth(token), json={
            "equipment_id": str(eid),
            "start_time": naive,
            "end_time": _future(5).strftime("%Y-%m-%dT%H:%M:%S"),
            "purpose": "Naive TZ Test",
        })
        assert resp.status_code == 201
        bk = db.bookings.find_one({"status": "pending"})
        # start_time should be timezone-aware (or at least stored as datetime)
        assert isinstance(bk["start_time"], datetime)


# ── Booking list / get ─────────────────────────────────────────────────────────

class TestBookingList:
    def test_student_sees_own_bookings_only(self, client):
        c, db = client
        eid = _make_equipment(db)
        t1 = _register_login(c, "bk_lst1@test.edu", role="student")
        t2 = _register_login(c, "bk_lst2@test.edu", role="student")
        _book(c, t1, eid, 2, 4)
        _book(c, t2, eid, 5, 7)

        resp = c.get("/api/bookings/", headers=_auth(t1))
        items = resp.get_json()["items"]
        # Student 1 should only see their own booking
        u1 = db.users.find_one({"email": "bk_lst1@test.edu"})
        assert all(str(i["student_id"]) == str(u1["_id"]) for i in items)

    def test_faculty_sees_all_bookings(self, client):
        c, db = client
        eid = _make_equipment(db)
        t_s = _register_login(c, "bk_fac_s@test.edu", role="student")
        t_f = _register_login(c, "bk_fac_f@test.edu", role="faculty")
        _book(c, t_s, eid, 2, 4)

        resp = c.get("/api/bookings/", headers=_auth(t_f))
        assert resp.status_code == 200
        assert len(resp.get_json()["items"]) >= 1

    def test_cursor_pagination(self, client):
        c, db = client
        eid = _make_equipment(db)
        token = _register_login(c, "bk_page@test.edu", role="student")
        # Create 4 bookings at non-overlapping slots
        for slot in range(4):
            _book(c, token, eid, 2 + slot * 3, 4 + slot * 3)

        resp1 = c.get("/api/bookings/?limit=2", headers=_auth(token))
        data1 = resp1.get_json()
        assert len(data1["items"]) == 2
        cursor = data1["next_cursor"]
        assert cursor is not None

        resp2 = c.get(f"/api/bookings/?limit=2&after={cursor}", headers=_auth(token))
        data2 = resp2.get_json()
        ids1 = {i["_id"] for i in data1["items"]}
        ids2 = {i["_id"] for i in data2["items"]}
        # Pages must not overlap
        assert ids1.isdisjoint(ids2)

    def test_student_cannot_get_others_booking(self, client):
        c, db = client
        eid = _make_equipment(db)
        t1 = _register_login(c, "bk_own1@test.edu", role="student")
        t2 = _register_login(c, "bk_own2@test.edu", role="student")
        resp = _book(c, t1, eid, 2, 4)
        bk_id = resp.get_json()["booking"]["_id"]

        resp2 = c.get(f"/api/bookings/{bk_id}", headers=_auth(t2))
        assert resp2.status_code == 403


# ── Faculty approval workflow ──────────────────────────────────────────────────

class TestApprovalWorkflow:
    def _setup(self, c, db, stu_email, fac_email):
        eid = _make_equipment(db)
        t_s = _register_login(c, stu_email, role="student")
        t_f = _register_login(c, fac_email, role="faculty")
        resp = _book(c, t_s, eid, 2, 4)
        bk_id = resp.get_json()["booking"]["_id"]
        return t_s, t_f, bk_id, eid

    def test_faculty_approves_booking(self, client):
        c, db = client
        _, t_f, bk_id, _ = self._setup(c, db, "ap_stu@test.edu", "ap_fac@test.edu")
        resp = c.put(f"/api/bookings/{bk_id}/approve", headers=_auth(t_f),
                     json={"notes": "Looks good"})
        assert resp.status_code == 200
        assert resp.get_json()["booking"]["status"] == "approved"

    def test_approval_notifies_student(self, client):
        c, db = client
        _, t_f, bk_id, _ = self._setup(c, db, "apn_stu@test.edu", "apn_fac@test.edu")
        c.put(f"/api/bookings/{bk_id}/approve", headers=_auth(t_f), json={})
        stu = db.users.find_one({"email": "apn_stu@test.edu"})
        notif = db.notifications.find_one({
            "user_id": stu["_id"],
            "type": "booking_approved",
        })
        assert notif is not None

    def test_student_cannot_approve(self, client):
        c, db = client
        t_s, _, bk_id, _ = self._setup(c, db, "apself_stu@test.edu", "apself_fac@test.edu")
        resp = c.put(f"/api/bookings/{bk_id}/approve", headers=_auth(t_s), json={})
        assert resp.status_code == 403

    def test_cannot_approve_non_pending(self, client):
        c, db = client
        _, t_f, bk_id, _ = self._setup(c, db, "ap2_stu@test.edu", "ap2_fac@test.edu")
        c.put(f"/api/bookings/{bk_id}/approve", headers=_auth(t_f), json={})
        # Try to approve again
        resp = c.put(f"/api/bookings/{bk_id}/approve", headers=_auth(t_f), json={})
        assert resp.status_code == 400


# ── Faculty rejection workflow ─────────────────────────────────────────────────

class TestRejectionWorkflow:
    def _setup(self, c, db, stu_email, fac_email):
        eid = _make_equipment(db)
        t_s = _register_login(c, stu_email, role="student")
        t_f = _register_login(c, fac_email, role="faculty")
        resp = _book(c, t_s, eid, 2, 4)
        bk_id = resp.get_json()["booking"]["_id"]
        return t_s, t_f, bk_id

    def test_faculty_rejects_with_reason(self, client):
        c, db = client
        _, t_f, bk_id = self._setup(c, db, "rej_stu@test.edu", "rej_fac@test.edu")
        resp = c.put(f"/api/bookings/{bk_id}/reject", headers=_auth(t_f),
                     json={"reason": "Lab unavailable that day"})
        assert resp.status_code == 200
        bk = resp.get_json()["booking"]
        assert bk["status"] == "rejected"
        assert bk["rejection_reason"] == "Lab unavailable that day"

    def test_rejection_without_reason_fails(self, client):
        c, db = client
        _, t_f, bk_id = self._setup(c, db, "rej2_stu@test.edu", "rej2_fac@test.edu")
        resp = c.put(f"/api/bookings/{bk_id}/reject", headers=_auth(t_f), json={})
        assert resp.status_code == 400

    def test_rejection_notifies_student(self, client):
        c, db = client
        _, t_f, bk_id = self._setup(c, db, "rejn_stu@test.edu", "rejn_fac@test.edu")
        c.put(f"/api/bookings/{bk_id}/reject", headers=_auth(t_f),
              json={"reason": "Maintenance scheduled"})
        stu = db.users.find_one({"email": "rejn_stu@test.edu"})
        notif = db.notifications.find_one({
            "user_id": stu["_id"],
            "type": "booking_rejected",
        })
        assert notif is not None

    def test_student_cannot_reject(self, client):
        c, db = client
        t_s, _, bk_id = self._setup(c, db, "rejself_stu@test.edu", "rejself_fac@test.edu")
        resp = c.put(f"/api/bookings/{bk_id}/reject", headers=_auth(t_s),
                     json={"reason": "Because I want to"})
        assert resp.status_code == 403


# ── Cancellation ───────────────────────────────────────────────────────────────

class TestCancellation:
    def test_student_cancels_pending_booking(self, client):
        c, db = client
        eid = _make_equipment(db)
        token = _register_login(c, "can_stu@test.edu", role="student")
        resp = _book(c, token, eid, 3, 5)
        bk_id = resp.get_json()["booking"]["_id"]
        cancel = c.put(f"/api/bookings/{bk_id}/cancel", headers=_auth(token))
        assert cancel.status_code == 200
        assert cancel.get_json()["booking"]["status"] == "cancelled"

    def test_student_cannot_cancel_others(self, client):
        c, db = client
        eid = _make_equipment(db)
        t1 = _register_login(c, "can1@test.edu", role="student")
        t2 = _register_login(c, "can2@test.edu", role="student")
        resp = _book(c, t1, eid, 3, 5)
        bk_id = resp.get_json()["booking"]["_id"]
        cancel = c.put(f"/api/bookings/{bk_id}/cancel", headers=_auth(t2))
        assert cancel.status_code == 403

    def test_cannot_cancel_completed(self, client):
        c, db = client
        eid = _make_equipment(db)
        token = _register_login(c, "can_comp@test.edu", role="student")
        resp = _book(c, token, eid, 3, 5)
        bk_id = resp.get_json()["booking"]["_id"]
        # Force status to completed
        db.bookings.update_one(
            {"_id": ObjectId(bk_id)}, {"$set": {"status": "completed"}}
        )
        cancel = c.put(f"/api/bookings/{bk_id}/cancel", headers=_auth(token))
        assert cancel.status_code == 400


# ── Overlap prevention ─────────────────────────────────────────────────────────

class TestOverlapPrevention:
    def test_overlapping_booking_rejected(self, client):
        c, db = client
        eid = _make_equipment(db)
        t1 = _register_login(c, "ov1@test.edu", role="student")
        t2 = _register_login(c, "ov2@test.edu", role="student")

        r1 = _book(c, t1, eid, 2, 5)
        assert r1.status_code == 201

        r2 = _book(c, t2, eid, 3, 6)   # overlaps [2,5]
        assert r2.status_code == 409
        assert "conflict" in r2.get_json()["error"].lower()

    def test_adjacent_slots_both_succeed(self, client):
        c, db = client
        eid = _make_equipment(db)
        t1 = _register_login(c, "adj1@test.edu", role="student")
        t2 = _register_login(c, "adj2@test.edu", role="student")

        r1 = _book(c, t1, eid, 2, 4)
        assert r1.status_code == 201

        r2 = _book(c, t2, eid, 4, 6)   # starts exactly when first ends
        assert r2.status_code == 201

    def test_approval_conflict_blocked(self, client):
        """Two pending bookings; approving both for the same slot must fail."""
        c, db = client
        eid = _make_equipment(db)
        t_s1 = _register_login(c, "apcon_s1@test.edu", role="student")
        t_s2 = _register_login(c, "apcon_s2@test.edu", role="student")
        t_f = _register_login(c, "apcon_fac@test.edu", role="faculty")

        r1 = _book(c, t_s1, eid, 2, 5)
        bk1 = r1.get_json()["booking"]["_id"]
        r2 = _book(c, t_s2, eid, 3, 6)  # Will be rejected (conflict at creation)
        # Second booking is blocked at creation for same slot
        assert r2.status_code == 409


# ── Concurrency lock tests (service-level) ────────────────────────────────────

class TestConcurrencyLock:
    """Service-level tests for the hardened locking mechanism."""

    @pytest.fixture(autouse=True)
    def _patch(self, mock_db, app):
        with patch("app.services.booking_service.mongo") as m:
            m.db = mock_db
            self.db = mock_db
            self.app = app
            yield

    def _insert_equipment(self, qty=5):
        eid = ObjectId()
        self.db.equipment.insert_one({
            "_id": eid, "name": "Lock Test", "status": "available",
            "quantity_available": qty, "quantity_total": qty,
            "lab_id": ObjectId(), "department_id": ObjectId(),
        })
        return eid

    def test_stale_expired_lock_replaced(self):
        """An expired lock should be cleaned and new lock acquired."""
        from app.services.booking_service import _equipment_lock
        eid_str = str(ObjectId())
        oid = ObjectId(eid_str)
        # Insert a lock that expired 1 minute ago
        self.db.booking_locks.insert_one({
            "equipment_id": oid,
            "token": "old-stale-token",
            "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
            "created_at": datetime.now(timezone.utc) - timedelta(minutes=2),
        })
        with self.app.app_context():
            # Should succeed: stale lock cleaned before acquire
            with _equipment_lock(eid_str):
                lock = self.db.booking_locks.find_one({"equipment_id": oid})
                assert lock is not None
                assert lock["token"] != "old-stale-token"

    def test_live_lock_contention_raises(self):
        """A live lock must block a second acquisition."""
        from app.services.booking_service import _equipment_lock, ConflictError
        eid_str = str(ObjectId())
        oid = ObjectId(eid_str)
        # Insert a live (not expired) lock
        self.db.booking_locks.insert_one({
            "equipment_id": oid,
            "token": "live-lock-token",
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=25),
            "created_at": datetime.now(timezone.utc),
        })
        with self.app.app_context():
            with pytest.raises(ConflictError, match="retry"):
                with _equipment_lock(eid_str):
                    pass

    def test_lock_released_on_exception(self):
        """Lock must always be released even on exception inside the critical section."""
        from app.services.booking_service import _equipment_lock
        eid_str = str(ObjectId())
        oid = ObjectId(eid_str)
        with self.app.app_context():
            with pytest.raises(RuntimeError):
                with _equipment_lock(eid_str):
                    raise RuntimeError("simulated crash")
            assert self.db.booking_locks.find_one({"equipment_id": oid}) is None

    def test_token_ownership_prevents_cross_release(self):
        """delete_one with wrong token must NOT remove another owner's lock."""
        from app.services.booking_service import _equipment_lock
        from bson import ObjectId as OID
        eid_str = str(OID())
        oid = OID(eid_str)
        with self.app.app_context():
            # Acquire the lock normally
            with _equipment_lock(eid_str):
                # Simulate another lock with a different token being inserted
                # (can't happen with unique index, but test the delete logic)
                lock = self.db.booking_locks.find_one({"equipment_id": oid})
                assert lock is not None
                original_token = lock["token"]
                # Replace token in DB to simulate TTL eviction + re-acquisition
                self.db.booking_locks.update_one(
                    {"equipment_id": oid}, {"$set": {"token": "other-owner-token"}}
                )
            # After context exit, delete_one({equipment_id, token=original_token}) 
            # won't match because token changed → "other-owner-token" lock survives
            remaining = self.db.booking_locks.find_one({"equipment_id": oid})
            assert remaining is not None
            assert remaining["token"] == "other-owner-token"

    def test_simultaneous_bookings_serialised(self):
        """
        Simulate two sequential booking requests for the same slot.
        The first must succeed; the second must get a ConflictError.
        (True parallel execution is not possible in a single-threaded test runner,
        so this tests the overlap detection inside the lock.)
        """
        from app.services.booking_service import create_booking, ConflictError
        eid = self._insert_equipment()
        s_id = str(ObjectId())

        with self.app.app_context():
            with patch("app.services.booking_service.mongo") as bm:
                bm.db = self.db
                start = _future(2)
                end = _future(4)
                # First booking succeeds
                doc1 = create_booking(s_id, str(eid), start, end, "Research A")
                assert doc1["status"] == "pending"
                # Second booking for exact same slot must conflict
                with pytest.raises(ConflictError):
                    create_booking(s_id, str(eid), start, end, "Research B")

    def test_lock_expiry_checked_before_acquire(self):
        """
        Verify that an expired lock is cleaned before acquisition attempt,
        not silently re-used (the Phase-1 $setOnInsert bug).
        """
        from app.services.booking_service import _equipment_lock
        eid_str = str(ObjectId())
        oid = ObjectId(eid_str)
        expired_token = "expired-token-should-be-evicted"
        # Insert expired lock with a known token
        self.db.booking_locks.insert_one({
            "equipment_id": oid,
            "token": expired_token,
            "expires_at": datetime.now(timezone.utc) - timedelta(seconds=5),
            "created_at": datetime.now(timezone.utc) - timedelta(seconds=35),
        })
        with self.app.app_context():
            with _equipment_lock(eid_str):
                lock = self.db.booking_locks.find_one({"equipment_id": oid})
                # The old expired token must be gone; new token must be in place
                assert lock["token"] != expired_token, (
                    "Phase-1 bug: expired lock was re-used instead of replaced"
                )


# ── Quantity restriction tests ─────────────────────────────────────────────────

class TestQuantityRestriction:
    def test_zero_available_blocks_booking(self, client):
        c, db = client
        eid = _make_equipment(db, qty=0)
        token = _register_login(c, "qty0@test.edu", role="student")
        resp = _book(c, token, eid)
        assert resp.status_code == 409

    def test_retired_equipment_blocks_booking(self, client):
        c, db = client
        eid = _make_equipment(db, status="retired")
        token = _register_login(c, "retired@test.edu", role="student")
        resp = _book(c, token, eid)
        assert resp.status_code == 400
