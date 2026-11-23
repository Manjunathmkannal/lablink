"""
Flask entry point.

Production mode: also serves the built React SPA from ../frontend/dist/.
  - Static assets  → served directly by Flask's static file handler.
  - Any non-/api/* path → returns index.html so client-side routing works.
  - /api/* routes   → handled by blueprints as normal; SPA fallback is skipped.

Development mode: React dev server (npm run dev) handles the frontend;
  the Vite proxy forwards /api/* calls to this Flask server on port 5000.
"""
from dotenv import load_dotenv
load_dotenv()
import os
from flask import send_from_directory
from app import create_app

# Resolve the path to the React production build
_HERE = os.path.dirname(os.path.abspath(__file__))
_FRONTEND_DIST = os.path.join(_HERE, "..", "frontend", "dist")

app = create_app()


# ── SPA fallback ──────────────────────────────────────────────────────────────
# Only register when the dist folder exists (i.e. after `npm run build`).
# Skipped automatically in pure-API / dev mode.

if os.path.isdir(_FRONTEND_DIST):

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path):
        """
        Serve built React assets for every non-/api route.
        /api/* routes are matched by their blueprints first and never reach here.
        """
        # Serve existing static files directly (JS, CSS, images, icons …)
        full = os.path.join(_FRONTEND_DIST, path)
        if path and os.path.isfile(full):
            return send_from_directory(_FRONTEND_DIST, path)
        # Everything else → index.html (React Router handles the route)
        return send_from_directory(_FRONTEND_DIST, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
