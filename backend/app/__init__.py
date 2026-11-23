"""
LabLink Flask application factory.
"""
from flask import Flask
from .config import get_config
from .extensions import mongo, bcrypt, cors


def create_app(config_override=None) -> Flask:
    app = Flask(__name__)

    # Load configuration
    cfg = get_config()
    app.config.from_object(cfg)

    if config_override:
        app.config.update(config_override)

    # Initialize extensions
    mongo.init_app(app)
    bcrypt.init_app(app)

    # Allow both localhost and 127.0.0.1 across Flask (5000) and Vite (5173)
    configured_origin = app.config.get("CORS_ORIGIN", "http://localhost:5173")
    if isinstance(configured_origin, str):
        configured_origins = [o.strip() for o in configured_origin.split(",") if o.strip()]
    else:
        configured_origins = list(configured_origin)

    allowed_origins = list(
        set(
            configured_origins
            + [
                "http://localhost:5000",
                "http://127.0.0.1:5000",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]
        )
    )

    cors.init_app(
        app,
        resources={r"/api/*": {"origins": allowed_origins}},
        supports_credentials=True,
    )

    # Ensure MongoDB indexes (skip during tests)
    if not app.config.get("TESTING", False):
        with app.app_context():
            _ensure_indexes()

    # Register blueprints
    from .routes.auth import auth_bp
    from .routes.equipment import equipment_bp
    from .routes.bookings import bookings_bp
    from .routes.projects import projects_bp
    from .routes.faculty import faculty_bp
    from .routes.admin import admin_bp
    from .routes.lab_assistant import lab_bp
    from .routes.notifications import notifications_bp
    from .routes.ai import ai_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(equipment_bp, url_prefix="/api/equipment")
    app.register_blueprint(bookings_bp, url_prefix="/api/bookings")
    app.register_blueprint(projects_bp, url_prefix="/api/projects")
    app.register_blueprint(faculty_bp, url_prefix="/api/faculty")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(lab_bp, url_prefix="/api/lab")
    app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
    app.register_blueprint(ai_bp, url_prefix="/api/ai")

    return app


def _ensure_indexes():
    """Create MongoDB indexes safely during application startup."""

    db = mongo.db

    # Catch missing database name / invalid initialization early
    if db is None:
        raise RuntimeError(
            "MongoDB database is not initialized. "
            "Check MONGO_URI in backend/.env and ensure it contains "
            "a database name, for example '/lablink'."
        )

    # Users
    db.users.create_index("email", unique=True)
    db.users.create_index("role")

    # Equipment
    db.equipment.create_index("department_id")
    db.equipment.create_index("lab_id")
    db.equipment.create_index("status")
    db.equipment.create_index(
        [
            ("name", "text"),
            ("description", "text"),
            ("tags", "text"),
        ]
    )

    # Bookings
    db.bookings.create_index(
        [
            ("equipment_id", 1),
            ("start_time", 1),
            ("end_time", 1),
        ]
    )
    db.bookings.create_index(
        [
            ("equipment_id", 1),
            ("status", 1),
        ]
    )
    db.bookings.create_index("student_id")
    db.bookings.create_index("status")
    db.bookings.create_index("faculty_id")

    # Notifications
    db.notifications.create_index(
        [
            ("user_id", 1),
            ("is_read", 1),
        ]
    )

    # Refresh tokens (TTL)
    db.refresh_tokens.create_index(
        "expires_at",
        expireAfterSeconds=0,
    )
    db.refresh_tokens.create_index("user_id")

    # Project requests
    db.project_requests.create_index("student_id")
    db.project_requests.create_index("status")
    db.project_requests.create_index(
        [("created_at", -1)]
    )

    # Maintenance records
    db.maintenance_records.create_index("equipment_id")
    db.maintenance_records.create_index("status")

    # Departments
    db.departments.create_index("name", unique=True)

    # Laboratories
    db.laboratories.create_index("department_id")

    # Booking locks (TTL)
    db.booking_locks.create_index(
        "expires_at",
        expireAfterSeconds=0,
    )
    db.booking_locks.create_index(
        "equipment_id",
        unique=True,
    )

    print("✅ MongoDB indexes initialized successfully.")