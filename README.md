# 🔬 LabLink — University Lab Resource & Equipment Management System

A full-stack web application designed to streamline university laboratory equipment management, student bookings, faculty approval workflows, lab handovers, and AI-assisted resource recommendations.

---

## 🚀 Tech Stack

- **Frontend:** React, Vite, Tailwind CSS
- **Backend:** Python, Flask, Flask-PyMongo, Flask-Bcrypt, Flask-CORS, JWT Authentication
- **Database:** MongoDB Atlas
- **Deployment:** Render (`render.yaml`)

---

## ✨ Key Features

- **Role-Based Access Control (RBAC):** Dedicated dashboards and workflows for **Students**, **Faculty**, **Lab Assistants**, and **Admins**.
- **Equipment Catalog & Availability:** Browse and filter lab equipment by department, category, and real-time availability status.
- **Conflict-Free Booking Engine:** Prevents double-bookings with time-slot validation, TTL booking locks, and full booking history tracking.
- **Project Requests & Faculty Approvals:** Students can submit multi-equipment project requests for faculty review and approval.
- **Lab Handover Management:** Lab assistants can track check-outs, returns, and equipment maintenance records.
- **AI Assistant & Smart Suggestions:** Built-in AI assistant to help students discover the right equipment for their projects.

---

## 📁 Project Structure

```text
lablink/
├── backend/
│   ├── app/
│   │   ├── routes/          # Auth, Equipment, Bookings, Projects, Faculty, Admin, Lab, AI
│   │   ├── services/        # Business logic & helpers
│   │   ├── utils/           # JWT, pagination, JSON & validation utilities
│   │   ├── __init__.py      # Flask app factory & MongoDB index setup
│   │   ├── config.py        # Environment configurations
│   │   └── extensions.py    # PyMongo, Bcrypt, CORS extensions
│   ├── requirements.txt
│   ├── run.py               # Application entry point
│   └── seed_data.py         # Sample database seeding script
├── frontend/
│   ├── src/
│   │   ├── components/      # Reusable UI & layout components
│   │   ├── context/         # AuthContext state management
│   │   └── pages/           # Student, Faculty, Lab Assistant, Admin & Auth pages
│   ├── package.json
│   └── vite.config.js
├── .gitignore
└── render.yaml
git clone [https://github.com/Manjunathmkannal/lablink.git](https://github.com/Manjunathmkannal/lablink.git)
cd lablink
1. Clone the Repository
Bash
git clone [https://github.com/Manjunathmkannal/lablink.git](https://github.com/Manjunathmkannal/lablink.git)
cd lablink
2. Backend Setup (Flask + MongoDB)
Bash
cd backend
pip install -r requirements.txt
Create a .env file inside backend/ based on .env.example:

Code snippet
MONGO_URI="mongodb+srv://<username>:<password>@<cluster>.mongodb.net/lablink?retryWrites=true&w=majority"
JWT_SECRET_KEY="your-super-secret-jwt-key"
CORS_ORIGIN="http://localhost:5173"
(Optional) Seed sample departments, labs, and equipment:

Bash
python seed_data.py
Start the Flask backend server:

Bash
python run.py
The backend will run at http://localhost:5000.

3. Frontend Setup (React + Vite)
Open a new terminal window:

Bash
cd frontend
npm install
npm run dev
The frontend will run at http://localhost:5173.

📄 License
This project is developed for academic and educational purposes.
