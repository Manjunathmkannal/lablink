"""
Unit tests for the booking service: concurrency protection and overlap detection.
Uses mongomock – no real MongoDB required.
"""
import pytest
import mongomock
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from bson import ObjectId


# ── Helpers ────────────────────────────────────────────────────────────────────

def _future(hours=2) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def _equip_id():
    return ObjectId()


def _student_id():
    return ObjectId()


def _insert_booking(db, equipment_id, start_offset_h, end_offset_h, status="approved"):
    """Insert a booking directly into the mongomock database."""
    start = _future(start_offset_h)
    end = _future(end_offset_h)
    doc = {
        "_id": ObjectId(),
        "student_id": _student_id(),
        "equipment_id": equipment_id,
        "lab_id": ObjectId(),
        "start_time": start,
        "end_time": end,
        "purpose": "Test booking",
        "status": status,
        "approved_by": None,
        "rejection_reason": None,
        "project_request_id": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    db.bookings.insert_one(doc)
    return doc


def _insert_equipment(db, equipment_id=None):
    eid = equipment_id or ObjectId()
    db.equipment.insert_one({
        "_id": eid,
        "name": "Test Equipment",
        "status": "available",
        "quantity_available": 2,
        "quantity_total": 2,
        "lab_id": ObjectId(),
        "department_id": ObjectId(),
    })
    return eid


# ── Overlap detection tests ────────────────────────────────────────────────────

class TestCheckOverlap:
    """Direct tests of the _check_overlap helper without Flask context."""

    @pytest.fixture(autouse=True)
    def _patch(self, mock_db):
        with patch("app.services.booking_service.mongo") as m:
            m.db = mock_db
            self.db = mock_db
            yield

    def test_no_conflict_when_no_bookings(self):
        from app.services.booking_service import _check_overlap
        eid = _equip_id()
        assert _check_overlap(eid, _future(2), _future(4)) is None

    def test_exact_overlap_detected(self):
        from app.services.booking_service import _check_overlap
        eid = _equip_id()
        _insert_booking(self.db, eid, 2, 4, status="approved")
        assert _check_overlap(eid, _future(2), _future(4)) is not None

    def test_partial_overlap_start_inside(self):
        from app.services.booking_service import _check_overlap
        eid = _equip_id()
        _insert_booking(self.db, eid, 1, 3, status="approved")
        assert _check_overlap(eid, _future(2), _future(4)) is not None

    def test_partial_overlap_end_inside(self):
        from app.services.booking_service import _check_overlap
        eid = _equip_id()
        _insert_booking(self.db, eid, 3, 5, status="approved")
        assert _check_overlap(eid, _future(2), _future(4)) is not None

    def test_new_contains_existing(self):
        from app.services.booking_service import _check_overlap
        eid = _equip_id()
        _insert_booking(self.db, eid, 3, 4, status="approved")
        assert _check_overlap(eid, _future(2), _future(5)) is not None

    def test_adjacent_slots_no_conflict(self):
        """[a,b) and [b,c) must NOT conflict."""
        from app.services.booking_service import _check_overlap
        eid = _equip_id()
        _insert_booking(self.db, eid, 2, 4, status="approved")
        assert _check_overlap(eid, _future(4), _future(6)) is None

    def test_cancelled_not_a_conflict(self):
        from app.services.booking_service import _check_overlap
        eid = _equip_id()
        _insert_booking(self.db, eid, 2, 4, status="cancelled")
        assert _check_overlap(eid, _future(2), _future(4)) is None

    def test_rejected_not_a_conflict(self):
        from app.services.booking_service import _check_overlap
        eid = _equip_id()
        _insert_booking(self.db, eid, 2, 4, status="rejected")
        assert _check_overlap(eid, _future(2), _future(4)) is None

    def test_pending_IS_a_conflict(self):
        from app.services.booking_service import _check_overlap
        eid = _equip_id()
        _insert_booking(self.db, eid, 2, 4, status="pending")
        assert _check_overlap(eid, _future(2), _future(4)) is not None

    def test_different_equipment_no_conflict(self):
        from app.services.booking_service import _check_overlap
        eid1 = _equip_id()
        eid2 = _equip_id()
        _insert_booking(self.db, eid1, 2, 4, status="approved")
        assert _check_overlap(eid2, _future(2), _future(4)) is None

    def test_exclude_id_skips_own_booking(self):
        from app.services.booking_service import _check_overlap
        eid = _equip_id()
        booking = _insert_booking(self.db, eid, 2, 4, status="approved")
        assert _check_overlap(eid, _future(2), _future(4), exclude_id=booking["_id"]) is None


# ── Lock contention tests ──────────────────────────────────────────────────────

class TestEquipmentLock:
    """Tests for the per-equipment advisory lock context manager."""

    @pytest.fixture(autouse=True)
    def _patch(self, mock_db, app):
        with patch("app.services.booking_service.mongo") as m:
            m.db = mock_db
            self.db = mock_db
            self.app = app
            yield

    def test_lock_acquired_and_released(self):
        from app.services.booking_service import _equipment_lock
        eid = str(ObjectId())
        with self.app.app_context():
            with _equipment_lock(eid):
                lock = self.db.booking_locks.find_one({"equipment_id": ObjectId(eid)})
                assert lock is not None
            # Released after context exit
            assert self.db.booking_locks.find_one({"equipment_id": ObjectId(eid)}) is None

    def test_lock_contention_raises_conflict_error(self):
        from app.services.booking_service import _equipment_lock, ConflictError
        eid = str(ObjectId())
        # Pre-insert a live lock
        self.db.booking_locks.insert_one({
            "equipment_id": ObjectId(eid),
            "token": "existing-token",
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=20),
            "created_at": datetime.now(timezone.utc),
        })
        with self.app.app_context():
            with pytest.raises(ConflictError, match="retry"):
                with _equipment_lock(eid):
                    pass

    def test_lock_released_on_exception(self):
        """Lock must be released even when the guarded code raises."""
        from app.services.booking_service import _equipment_lock
        eid = str(ObjectId())
        with self.app.app_context():
            with pytest.raises(ValueError):
                with _equipment_lock(eid):
                    raise ValueError("simulated error")
            # Lock must still be released
            assert self.db.booking_locks.find_one({"equipment_id": ObjectId(eid)}) is None


# ── Service-level booking validation tests ────────────────────────────────────

class TestBookingServiceValidation:
    """Tests for create_booking input validation and conflict prevention."""

    @pytest.fixture(autouse=True)
    def _patch(self, mock_db, app):
        with patch("app.services.booking_service.mongo") as m:
            m.db = mock_db
            self.db = mock_db
            self.app = app
            yield

    def _call_create(self, equipment_id, start, end, purpose="Research"):
        from app.services.booking_service import create_booking
        return create_booking(
            student_id=str(ObjectId()),
            equipment_id=str(equipment_id),
            start_time=start,
            end_time=end,
            purpose=purpose,
        )

    def test_equipment_not_found_raises(self):
        from app.services.booking_service import NotFoundError
        with self.app.app_context():
            with pytest.raises(NotFoundError, match="Equipment not found"):
                self._call_create(ObjectId(), _future(2), _future(4))

    def test_conflict_raises(self):
        from app.services.booking_service import ConflictError
        eid = _insert_equipment(self.db)
        _insert_booking(self.db, eid, 2, 4, status="approved")
        with self.app.app_context():
            with pytest.raises(ConflictError):
                self._call_create(eid, _future(2), _future(4))

    def test_past_start_raises(self):
        from app.services.booking_service import BookingError
        eid = _insert_equipment(self.db)
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        with self.app.app_context():
            with pytest.raises(BookingError, match="future"):
                self._call_create(eid, past, _future(2))

    def test_end_before_start_raises(self):
        from app.services.booking_service import BookingError
        eid = _insert_equipment(self.db)
        with self.app.app_context():
            with pytest.raises(BookingError, match="end_time must be after"):
                self._call_create(eid, _future(4), _future(2))

    def test_duration_exceeds_24h_raises(self):
        from app.services.booking_service import BookingError
        eid = _insert_equipment(self.db)
        with self.app.app_context():
            with pytest.raises(BookingError, match="24 hours"):
                self._call_create(eid, _future(2), _future(30))

    def test_successful_booking_inserted(self):
        eid = _insert_equipment(self.db)
        with self.app.app_context():
            doc = self._call_create(eid, _future(2), _future(4))
        assert doc["status"] == "pending"
        assert doc["equipment_id"] == eid
        assert self.db.bookings.find_one({"_id": doc["_id"]}) is not None

    def test_non_overlapping_bookings_both_succeed(self):
        """Two bookings on the same equipment at different times must both succeed."""
        eid = _insert_equipment(self.db)
        with self.app.app_context():
            doc1 = self._call_create(eid, _future(2), _future(4))
            doc2 = self._call_create(eid, _future(5), _future(7))
        assert doc1["_id"] != doc2["_id"]
        assert self.db.bookings.count_documents({"equipment_id": eid}) == 2
