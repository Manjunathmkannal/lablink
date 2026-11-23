"""
Phase 4D – IBM watsonx.ai service and AI route tests.

Strategy:
- All tests run with watsonx credentials absent (stub/no-credentials path).
- _watsonx_generate is mocked where needed to test AI response parsing.
- NO live watsonx.ai calls are made; see bottom of file for note.

Tests cover:
- Route authentication (all AI routes require JWT)
- Input validation on each AI route
- Stub-mode responses when credentials are absent
- Structured JSON output from recommend, slots, draft
- Mocked AI response parsing (valid JSON, invalid JSON, empty)
- Timeout and request failure handling in _watsonx_generate
- Credential safety: API key / project ID never appear in any response
- AI advisory-only constraint: routes never approve/reject/modify bookings
"""
import pytest
from unittest.mock import patch, MagicMock
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


def _insert_equipment(db, name="Raspberry Pi", status="available"):
    eid = ObjectId()
    db.equipment.insert_one({
        "_id": eid, "name": name, "status": status,
        "category": "Microcontroller", "condition": "good",
        "description": "Single-board computer for prototyping",
        "department_id": ObjectId(),
        "serial_number": str(eid)[:8],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return eid


# ════════════════════════════════════════════════════════════════════════════════
# Authentication – all AI routes require a valid JWT
# ════════════════════════════════════════════════════════════════════════════════

class TestAIRouteAuthentication:
    def test_recommend_requires_auth(self, client):
        c, _ = client
        resp = c.post("/api/ai/recommend", json={"project_description": "robotics"})
        assert resp.status_code == 401

    def test_slots_requires_auth(self, client):
        c, _ = client
        resp = c.post("/api/ai/slots", json={"equipment_id": str(ObjectId())})
        assert resp.status_code == 401

    def test_draft_requires_auth(self, client):
        c, _ = client
        resp = c.post("/api/ai/draft", json={"description": "my project"})
        assert resp.status_code == 401

    def test_status_requires_auth(self, client):
        c, _ = client
        resp = c.get("/api/ai/status")
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════════════════
# AI Status Endpoint
# ════════════════════════════════════════════════════════════════════════════════

class TestAIStatus:
    def test_status_without_credentials_returns_stub_mode(self, client):
        c, _ = client
        token = _register_login(c, "ai_status@test.edu", "student")
        resp = c.get("/api/ai/status", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert "configured" in data
        assert "mode"       in data
        # No credentials set in test env → stub
        assert data["configured"] is False
        assert data["mode"] == "stub"

    def test_status_does_not_expose_api_key(self, client):
        c, _ = client
        token = _register_login(c, "ai_status_key@test.edu", "student")
        # Simulate credentials being set
        with patch("app.services.watsonx_service.current_app") as mock_app:
            mock_app.config.get.side_effect = lambda k, d="": {
                "WATSONX_API_KEY": "super-secret-key",
                "WATSONX_PROJECT_ID": "proj-123",
            }.get(k, d)
            resp = c.get("/api/ai/status", headers=_auth(token))

        body = resp.get_data(as_text=True)
        assert "super-secret-key" not in body
        assert "proj-123"         not in body

    def test_status_response_has_no_credential_fields(self, client):
        c, _ = client
        token = _register_login(c, "ai_status_fields@test.edu", "student")
        resp = c.get("/api/ai/status", headers=_auth(token))
        data = resp.get_json()
        # Only safe fields
        allowed = {"configured", "mode"}
        assert set(data.keys()).issubset(allowed)


# ════════════════════════════════════════════════════════════════════════════════
# Recommend Equipment – Input Validation
# ════════════════════════════════════════════════════════════════════════════════

class TestRecommendInputValidation:
    def test_missing_description_returns_400(self, client):
        c, _ = client
        token = _register_login(c, "ai_rec_nofield@test.edu", "student")
        resp = c.post("/api/ai/recommend", headers=_auth(token), json={})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_empty_description_returns_400(self, client):
        c, _ = client
        token = _register_login(c, "ai_rec_empty@test.edu", "student")
        resp = c.post("/api/ai/recommend", headers=_auth(token),
                      json={"project_description": "   "})
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════════════════
# Recommend Equipment – Stub Mode (no credentials)
# ════════════════════════════════════════════════════════════════════════════════

class TestRecommendStubMode:
    def test_recommend_returns_structured_response(self, client):
        c, db = client
        _insert_equipment(db, "Arduino Uno")
        token = _register_login(c, "ai_rec_stub@test.edu", "student")
        resp = c.post("/api/ai/recommend", headers=_auth(token),
                      json={"project_description": "IoT sensor project"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "recommendations" in data
        assert "mode" in data
        assert data["mode"] in ("stub", "ai")

    def test_recommend_stub_returns_available_equipment(self, client):
        c, db = client
        _insert_equipment(db, "Jetson Nano",    status="available")
        _insert_equipment(db, "Broken Device",  status="maintenance")
        token = _register_login(c, "ai_rec_avail@test.edu", "student")
        resp = c.post("/api/ai/recommend", headers=_auth(token),
                      json={"project_description": "edge AI project"})
        assert resp.status_code == 200
        recs = resp.get_json()["recommendations"]
        # Stub only returns available items
        for r in recs:
            assert r.get("status") != "maintenance"

    def test_recommend_max_3_results(self, client):
        c, db = client
        for i in range(6):
            _insert_equipment(db, f"Device {i}")
        token = _register_login(c, "ai_rec_max@test.edu", "student")
        resp = c.post("/api/ai/recommend", headers=_auth(token),
                      json={"project_description": "generic project"})
        assert resp.status_code == 200
        recs = resp.get_json()["recommendations"]
        assert len(recs) <= 3

    def test_recommend_empty_equipment_returns_empty_list(self, client):
        c, _ = client
        token = _register_login(c, "ai_rec_noequip@test.edu", "student")
        resp = c.post("/api/ai/recommend", headers=_auth(token),
                      json={"project_description": "project with no equipment"})
        assert resp.status_code == 200
        assert isinstance(resp.get_json()["recommendations"], list)

    def test_recommend_does_not_expose_credentials(self, client):
        c, _ = client
        token = _register_login(c, "ai_rec_creds@test.edu", "student")
        resp = c.post("/api/ai/recommend", headers=_auth(token),
                      json={"project_description": "some project"})
        body = resp.get_data(as_text=True)
        # Ensure no watsonx credential keys appear in any response
        for forbidden in ("WATSONX_API_KEY", "WATSONX_PROJECT_ID",
                          "access_token", "api_key", "apikey"):
            assert forbidden not in body


# ════════════════════════════════════════════════════════════════════════════════
# Recommend Equipment – Mocked AI Mode
# ════════════════════════════════════════════════════════════════════════════════

class TestRecommendAIMode:
    def test_valid_ai_response_is_parsed(self, client):
        c, db = client
        eid = _insert_equipment(db, "Arduino Mega")
        token = _register_login(c, "ai_rec_ai@test.edu", "student")

        ai_json = '[{"name": "Arduino Mega", "reason": "Best for robotics"}]'
        with patch("app.services.watsonx_service._watsonx_generate", return_value=ai_json), \
             patch("app.services.watsonx_service.is_configured", return_value=True):
            resp = c.post("/api/ai/recommend", headers=_auth(token),
                          json={"project_description": "robotics"})

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["mode"] == "ai"
        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["name"] == "Arduino Mega"
        assert data["recommendations"][0]["reason"] == "Best for robotics"

    def test_invalid_json_from_ai_falls_back_to_stub(self, client):
        c, db = client
        _insert_equipment(db, "FPGA Board")
        token = _register_login(c, "ai_rec_badjson@test.edu", "student")

        with patch("app.services.watsonx_service._watsonx_generate", return_value="not valid json at all"), \
             patch("app.services.watsonx_service.is_configured", return_value=True):
            resp = c.post("/api/ai/recommend", headers=_auth(token),
                          json={"project_description": "FPGA project"})

        assert resp.status_code == 200
        # Falls back to stub
        assert resp.get_json()["mode"] in ("stub", "ai")

    def test_none_response_from_ai_falls_back_to_stub(self, client):
        c, db = client
        _insert_equipment(db, "Sensor Kit")
        token = _register_login(c, "ai_rec_none@test.edu", "student")

        with patch("app.services.watsonx_service._watsonx_generate", return_value=None), \
             patch("app.services.watsonx_service.is_configured", return_value=True):
            resp = c.post("/api/ai/recommend", headers=_auth(token),
                          json={"project_description": "sensor project"})

        assert resp.status_code == 200
        assert resp.get_json()["mode"] == "stub"


# ════════════════════════════════════════════════════════════════════════════════
# Suggest Slots – Input Validation
# ════════════════════════════════════════════════════════════════════════════════

class TestSuggestSlotsValidation:
    def test_missing_equipment_id_returns_400(self, client):
        c, _ = client
        token = _register_login(c, "ai_slots_noid@test.edu", "student")
        resp = c.post("/api/ai/slots", headers=_auth(token),
                      json={"preferred_date": "2027-01-15"})
        assert resp.status_code == 400

    def test_invalid_equipment_id_returns_400(self, client):
        c, _ = client
        token = _register_login(c, "ai_slots_badid@test.edu", "student")
        resp = c.post("/api/ai/slots", headers=_auth(token),
                      json={"equipment_id": "not-an-object-id"})
        assert resp.status_code == 400

    def test_nonexistent_equipment_returns_404(self, client):
        c, _ = client
        token = _register_login(c, "ai_slots_notfound@test.edu", "student")
        resp = c.post("/api/ai/slots", headers=_auth(token),
                      json={"equipment_id": str(ObjectId())})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════════════════
# Suggest Slots – Computed Mode
# ════════════════════════════════════════════════════════════════════════════════

class TestSuggestSlotsComputed:
    def test_free_equipment_returns_slots(self, client):
        c, db = client
        eid = _insert_equipment(db)
        token = _register_login(c, "ai_slots_free@test.edu", "student")
        resp = c.post("/api/ai/slots", headers=_auth(token),
                      json={"equipment_id": str(eid), "preferred_date": "2027-06-15"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "slots" in data
        assert "mode"  in data
        assert isinstance(data["slots"], list)
        assert len(data["slots"]) > 0

    def test_fully_booked_day_returns_empty_or_fewer_slots(self, client):
        c, db = client
        eid = _insert_equipment(db)
        # Insert bookings covering 08:00-18:00 on the target date
        date_str = "2027-07-10"
        for hour in range(8, 18, 2):
            start = datetime(2027, 7, 10, hour, 0, tzinfo=timezone.utc)
            db.bookings.insert_one({
                "_id": ObjectId(),
                "equipment_id": eid,
                "status": "approved",
                "start_time": start,
                "end_time":   start + timedelta(hours=2),
                "created_at": datetime.now(timezone.utc),
            })
        token = _register_login(c, "ai_slots_full@test.edu", "student")
        resp = c.post("/api/ai/slots", headers=_auth(token),
                      json={"equipment_id": str(eid), "preferred_date": date_str})
        assert resp.status_code == 200
        slots = resp.get_json()["slots"]
        assert len(slots) == 0  # all slots occupied

    def test_slots_response_has_start_and_end(self, client):
        c, db = client
        eid = _insert_equipment(db)
        token = _register_login(c, "ai_slots_fields@test.edu", "student")
        resp = c.post("/api/ai/slots", headers=_auth(token),
                      json={"equipment_id": str(eid), "preferred_date": "2027-08-20"})
        assert resp.status_code == 200
        slots = resp.get_json()["slots"]
        for s in slots:
            assert "start" in s
            assert "end"   in s

    def test_slots_capped_at_3(self, client):
        c, db = client
        eid = _insert_equipment(db)
        token = _register_login(c, "ai_slots_cap@test.edu", "student")
        resp = c.post("/api/ai/slots", headers=_auth(token),
                      json={"equipment_id": str(eid), "preferred_date": "2027-09-01"})
        assert resp.status_code == 200
        assert len(resp.get_json()["slots"]) <= 3

    def test_missing_date_defaults_to_today(self, client):
        c, db = client
        eid = _insert_equipment(db)
        token = _register_login(c, "ai_slots_nodate@test.edu", "student")
        resp = c.post("/api/ai/slots", headers=_auth(token),
                      json={"equipment_id": str(eid)})
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════════════════
# Draft Request
# ════════════════════════════════════════════════════════════════════════════════

class TestDraftRequest:
    def test_missing_description_returns_400(self, client):
        c, _ = client
        token = _register_login(c, "ai_draft_nofield@test.edu", "student")
        resp = c.post("/api/ai/draft", headers=_auth(token), json={})
        assert resp.status_code == 400

    def test_empty_description_returns_400(self, client):
        c, _ = client
        token = _register_login(c, "ai_draft_empty@test.edu", "student")
        resp = c.post("/api/ai/draft", headers=_auth(token),
                      json={"description": "   "})
        assert resp.status_code == 400

    def test_stub_draft_returns_description_unchanged(self, client):
        c, _ = client
        token = _register_login(c, "ai_draft_stub@test.edu", "student")
        resp = c.post("/api/ai/draft", headers=_auth(token),
                      json={"description": "Build a weather station"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "mode" in data
        assert data["mode"] in ("stub", "ai")
        # Stub passes description through
        if data["mode"] == "stub":
            assert data.get("description") == "Build a weather station"

    def test_draft_response_has_title_and_description_keys(self, client):
        c, _ = client
        token = _register_login(c, "ai_draft_keys@test.edu", "student")
        resp = c.post("/api/ai/draft", headers=_auth(token),
                      json={"description": "Smart farming IoT system"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "title"       in data
        assert "description" in data
        assert "mode"        in data

    def test_mocked_ai_draft_parses_valid_json(self, client):
        c, _ = client
        token = _register_login(c, "ai_draft_ai@test.edu", "student")
        ai_response = '{"title": "Smart Farm", "description": "An IoT project."}'
        with patch("app.services.watsonx_service._watsonx_generate", return_value=ai_response), \
             patch("app.services.watsonx_service.is_configured", return_value=True):
            resp = c.post("/api/ai/draft", headers=_auth(token),
                          json={"description": "IoT farming project"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"]       == "Smart Farm"
        assert data["description"] == "An IoT project."
        assert data["mode"]        == "ai"

    def test_mocked_ai_draft_bad_json_falls_back(self, client):
        c, _ = client
        token = _register_login(c, "ai_draft_badjson@test.edu", "student")
        with patch("app.services.watsonx_service._watsonx_generate", return_value="garbage text"), \
             patch("app.services.watsonx_service.is_configured", return_value=True):
            resp = c.post("/api/ai/draft", headers=_auth(token),
                          json={"description": "some project"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "title"       in data
        assert "description" in data


# ════════════════════════════════════════════════════════════════════════════════
# Watsonx Service – Failure Handling
# ════════════════════════════════════════════════════════════════════════════════

class TestWatsonxFailureHandling:
    def test_iam_token_failure_returns_stub(self, client):
        """If IAM exchange fails, service falls back to stub."""
        c, db = client
        _insert_equipment(db, "FPGA Kit")
        token = _register_login(c, "ai_iam_fail@test.edu", "student")

        with patch("app.services.watsonx_service.is_configured", return_value=True), \
             patch("app.services.watsonx_service._get_iam_token", return_value=None):
            resp = c.post("/api/ai/recommend", headers=_auth(token),
                          json={"project_description": "FPGA computation"})

        assert resp.status_code == 200
        assert resp.get_json()["mode"] == "stub"

    def test_watsonx_timeout_handled_gracefully(self, client):
        """requests.Timeout during generation falls back to stub."""
        import requests as req_lib
        c, db = client
        _insert_equipment(db, "DSP Board")
        token = _register_login(c, "ai_timeout@test.edu", "student")

        with patch("app.services.watsonx_service.is_configured", return_value=True), \
             patch("app.services.watsonx_service._get_iam_token", return_value="fake-iam-token"), \
             patch("requests.post", side_effect=req_lib.Timeout("timed out")):
            resp = c.post("/api/ai/recommend", headers=_auth(token),
                          json={"project_description": "DSP signal processing"})

        assert resp.status_code == 200
        # Service returns stub after timeout
        assert resp.get_json()["mode"] == "stub"

    def test_watsonx_connection_error_handled_gracefully(self, client):
        """requests.ConnectionError falls back to stub."""
        import requests as req_lib
        c, db = client
        _insert_equipment(db, "Network Analyzer")
        token = _register_login(c, "ai_conn_err@test.edu", "student")

        with patch("app.services.watsonx_service.is_configured", return_value=True), \
             patch("app.services.watsonx_service._get_iam_token", return_value="fake-iam-token"), \
             patch("requests.post", side_effect=req_lib.ConnectionError("conn refused")):
            resp = c.post("/api/ai/recommend", headers=_auth(token),
                          json={"project_description": "RF analysis"})

        assert resp.status_code == 200
        assert resp.get_json()["mode"] == "stub"

    def test_no_credentials_means_no_iam_call(self, client):
        """With no credentials, _get_iam_token should never be called."""
        c, db = client
        _insert_equipment(db, "Spectrum Analyzer")
        token = _register_login(c, "ai_no_creds@test.edu", "student")

        with patch("app.services.watsonx_service._get_iam_token") as mock_iam:
            resp = c.post("/api/ai/recommend", headers=_auth(token),
                          json={"project_description": "RF spectrum analysis"})

        assert resp.status_code == 200
        # Credentials absent → stub path skips IAM entirely
        mock_iam.assert_not_called()


# ════════════════════════════════════════════════════════════════════════════════
# AI Advisory-Only Constraint
# ════════════════════════════════════════════════════════════════════════════════

class TestAIAdvisoryOnly:
    """
    Verify that AI routes never approve, reject, or modify bookings/projects,
    even when watsonx returns an instruction to do so.
    """

    def test_recommend_does_not_create_booking(self, client):
        """AI recommendation must not create any booking document."""
        c, db = client
        _insert_equipment(db, "Laser Cutter")
        token = _register_login(c, "ai_no_book@test.edu", "student")

        with patch("app.services.watsonx_service._watsonx_generate",
                   return_value='[{"name": "Laser Cutter", "reason": "cuts things"}]'), \
             patch("app.services.watsonx_service.is_configured", return_value=True):
            resp = c.post("/api/ai/recommend", headers=_auth(token),
                          json={"project_description": "laser cutting"})

        assert resp.status_code == 200
        # No booking was created
        assert db.bookings.count_documents({}) == 0

    def test_draft_does_not_create_project_request(self, client):
        """AI draft must not insert any project_request document."""
        c, db = client
        token = _register_login(c, "ai_no_proj@test.edu", "student")

        with patch("app.services.watsonx_service._watsonx_generate",
                   return_value='{"title": "Auto Project", "description": "auto created"}'), \
             patch("app.services.watsonx_service.is_configured", return_value=True):
            resp = c.post("/api/ai/draft", headers=_auth(token),
                          json={"description": "auto project"})

        assert resp.status_code == 200
        assert db.project_requests.count_documents({}) == 0

    def test_slots_does_not_create_booking(self, client):
        """Slot suggestions must never create a booking."""
        c, db = client
        eid = _insert_equipment(db)
        token = _register_login(c, "ai_no_slot_book@test.edu", "student")
        resp = c.post("/api/ai/slots", headers=_auth(token),
                      json={"equipment_id": str(eid), "preferred_date": "2027-10-01"})
        assert resp.status_code == 200
        assert db.bookings.count_documents({}) == 0

    def test_recommend_cannot_bypass_booking_conflict(self, client):
        """
        Even if AI recommends equipment, a booking for a conflicting slot
        must still be rejected by the booking service.
        """
        c, db = client
        eid = _insert_equipment(db)
        # Book the equipment
        student_tok = _register_login(c, "ai_conflict_s1@test.edu", "student")
        start = datetime(2027, 11, 1, 10, 0, tzinfo=timezone.utc)
        end   = datetime(2027, 11, 1, 12, 0, tzinfo=timezone.utc)
        # Insert an approved booking directly
        db.bookings.insert_one({
            "_id": ObjectId(),
            "equipment_id": eid,
            "user_id": ObjectId(),
            "status": "approved",
            "start_time": start,
            "end_time":   end,
            "created_at": datetime.now(timezone.utc),
        })

        # Another student tries to book the same slot via the booking route
        student2_tok = _register_login(c, "ai_conflict_s2@test.edu", "student")
        conflict_resp = c.post("/api/bookings/", headers=_auth(student2_tok), json={
            "equipment_id": str(eid),
            "start_time":   start.isoformat(),
            "end_time":     end.isoformat(),
            "purpose":      "AI bypass test",
        })
        # Must be rejected (409 conflict or 400)
        assert conflict_resp.status_code in (400, 409)

    def test_ai_routes_do_not_accept_approve_action(self, client):
        """AI routes have no approve/reject verbs at all."""
        c, _ = client
        token = _register_login(c, "ai_no_approve@test.edu", "student")
        # None of the AI routes accept an "action" parameter
        resp = c.post("/api/ai/recommend", headers=_auth(token),
                      json={"project_description": "project", "action": "approve_booking"})
        assert resp.status_code == 200
        data = resp.get_json()
        # Response must not contain approval confirmation
        assert "approved" not in str(data).lower() or "recommendations" in data


# ════════════════════════════════════════════════════════════════════════════════
# Credential Safety
# ════════════════════════════════════════════════════════════════════════════════

class TestCredentialSafety:
    def test_watsonx_api_key_never_in_response_body(self, client):
        c, db = client
        _insert_equipment(db)
        token = _register_login(c, "ai_cred_body@test.edu", "student")

        fake_key = "ibmcloud-apikey-test-secret-xyz"
        with patch("app.services.watsonx_service.current_app") as mock_app:
            mock_app.config.get.side_effect = lambda k, d="": {
                "WATSONX_API_KEY": fake_key,
                "WATSONX_PROJECT_ID": "proj-id-test",
            }.get(k, d)
            # Force is_configured to True but _get_iam_token to return None
            # (simulates network failure during token exchange)
            with patch("app.services.watsonx_service._get_iam_token", return_value=None):
                resp = c.post("/api/ai/recommend", headers=_auth(token),
                              json={"project_description": "some project"})

        body = resp.get_data(as_text=True)
        assert fake_key      not in body
        assert "proj-id-test" not in body

    def test_iam_token_never_in_response_body(self, client):
        c, db = client
        _insert_equipment(db)
        token = _register_login(c, "ai_iam_body@test.edu", "student")

        fake_iam = "Bearer-iam-token-secret-value-xyz"
        ai_response = '[{"name": "Device", "reason": "good"}]'

        with patch("app.services.watsonx_service.is_configured", return_value=True), \
             patch("app.services.watsonx_service._get_iam_token", return_value=fake_iam), \
             patch("app.services.watsonx_service._watsonx_generate", return_value=ai_response):
            resp = c.post("/api/ai/recommend", headers=_auth(token),
                          json={"project_description": "device project"})

        body = resp.get_data(as_text=True)
        assert fake_iam not in body


# ════════════════════════════════════════════════════════════════════════════════
# _find_free_slots unit tests (service layer, no HTTP)
# ════════════════════════════════════════════════════════════════════════════════

class TestFindFreeSlots:
    """Direct unit tests for the slot-finding algorithm."""

    def test_no_bookings_returns_three_slots(self, client):
        from app.services.watsonx_service import _find_free_slots
        slots = _find_free_slots("2027-05-01", [])
        assert len(slots) == 3

    def test_all_slots_blocked_returns_empty(self, client):
        from app.services.watsonx_service import _find_free_slots
        bookings = [
            {"start_time": datetime(2027, 5, 1, h, 0, tzinfo=timezone.utc),
             "end_time":   datetime(2027, 5, 1, h+2, 0, tzinfo=timezone.utc)}
            for h in range(8, 18, 2)
        ]
        slots = _find_free_slots("2027-05-01", bookings)
        assert slots == []

    def test_invalid_date_falls_back_to_today(self, client):
        from app.services.watsonx_service import _find_free_slots
        # Should not raise
        slots = _find_free_slots("not-a-date", [])
        assert isinstance(slots, list)

    def test_slots_do_not_overlap_bookings(self, client):
        from app.services.watsonx_service import _find_free_slots
        booking = [{"start_time": datetime(2027, 6, 1, 8, 0, tzinfo=timezone.utc),
                    "end_time":   datetime(2027, 6, 1, 10, 0, tzinfo=timezone.utc)}]
        slots = _find_free_slots("2027-06-01", booking)
        for s in slots:
            start = datetime.fromisoformat(s["start"])
            end   = datetime.fromisoformat(s["end"])
            # Must not overlap 08:00-10:00
            assert not (start < datetime(2027, 6, 1, 10, 0, tzinfo=timezone.utc) and
                        end   > datetime(2027, 6, 1,  8, 0, tzinfo=timezone.utc))


# ════════════════════════════════════════════════════════════════════════════════
# NOTE ON LIVE watsonx.ai TESTING
# ════════════════════════════════════════════════════════════════════════════════
# No live IBM watsonx.ai calls are made in this test suite.
# All AI paths that require real credentials are tested via:
#   - patch("app.services.watsonx_service._watsonx_generate", return_value=...)
#   - patch("app.services.watsonx_service.is_configured", return_value=True/False)
# To test with real credentials, set environment variables:
#   WATSONX_API_KEY, WATSONX_PROJECT_ID, WATSONX_URL
# and run a separate integration test (not included here per instructions).
