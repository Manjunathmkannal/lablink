"""
Seed sample departments, laboratories, and lab equipment into MongoDB.
Run from backend folder: python seed.py
"""
from datetime import datetime, timezone
from app import create_app
from app.extensions import mongo

app = create_app()

with app.app_context():
    db = mongo.db

    # 1. Insert Departments
    departments = [
        {"name": "Computer Science & Engineering", "code": "CSE", "created_at": datetime.now(timezone.utc)},
        {"name": "Electronics & Communication", "code": "ECE", "created_at": datetime.now(timezone.utc)},
        {"name": "Mechanical & Robotics", "code": "MECH", "created_at": datetime.now(timezone.utc)},
    ]
    dept_ids = {}
    for dept in departments:
        existing = db.departments.find_one({"name": dept["name"]})
        if existing:
            dept_ids[dept["code"]] = str(existing["_id"])
        else:
            res = db.departments.insert_one(dept)
            dept_ids[dept["code"]] = str(res.inserted_id)

    # 2. Insert Laboratories
    labs = [
        {"name": "AI & High-Performance Computing Lab", "department_id": dept_ids["CSE"], "location": "Block A - Room 302"},
        {"name": "IoT & Embedded Systems Lab", "department_id": dept_ids["ECE"], "location": "Block B - Room 105"},
        {"name": "Robotics & Prototyping Lab", "department_id": dept_ids["MECH"], "location": "Block C - Room 201"},
    ]
    lab_ids = {}
    for lab in labs:
        existing = db.laboratories.find_one({"name": lab["name"]})
        if existing:
            lab_ids[lab["name"]] = str(existing["_id"])
        else:
            res = db.laboratories.insert_one(lab)
            lab_ids[lab["name"]] = str(res.inserted_id)

    # 3. Insert Sample Equipment
    sample_equipment = [
        {
            "name": "NVIDIA Jetson Orin Nano Developer Kit",
            "description": "Edge AI development kit for computer vision, robotics, and deep learning inference.",
            "category": "Computing & AI",
            "department_id": dept_ids["CSE"],
            "lab_id": lab_ids["AI & High-Performance Computing Lab"],
            "status": "available",
            "quantity": 5,
            "available_quantity": 5,
            "tags": ["AI", "GPU", "Edge Computing", "CUDA"],
            "created_at": datetime.now(timezone.utc),
        },
        {
            "name": "Raspberry Pi 5 (8GB) Starter Kit",
            "description": "Single-board computer with power supply, microSD, and cooling case for IoT projects.",
            "category": "Embedded Systems",
            "department_id": dept_ids["ECE"],
            "lab_id": lab_ids["IoT & Embedded Systems Lab"],
            "status": "available",
            "quantity": 10,
            "available_quantity": 10,
            "tags": ["IoT", "Linux", "Raspberry Pi", "Sensors"],
            "created_at": datetime.now(timezone.utc),
        },
        {
            "name": "Rigol DS1054Z Digital Oscilloscope",
            "description": "4-channel 50MHz digital storage oscilloscope for circuit debugging and signal analysis.",
            "category": "Testing & Measurement",
            "department_id": dept_ids["ECE"],
            "lab_id": lab_ids["IoT & Embedded Systems Lab"],
            "status": "available",
            "quantity": 4,
            "available_quantity": 4,
            "tags": ["Oscilloscope", "Electronics", "Signal"],
            "created_at": datetime.now(timezone.utc),
        },
        {
            "name": "Bambu Lab P1S 3D Printer",
            "description": "High-speed enclosed CoreXY 3D printer for rapid mechanical and robotics prototyping.",
            "category": "Fabrication",
            "department_id": dept_ids["MECH"],
            "lab_id": lab_ids["Robotics & Prototyping Lab"],
            "status": "available",
            "quantity": 2,
            "available_quantity": 2,
            "tags": ["3D Printing", "CAD", "Prototyping"],
            "created_at": datetime.now(timezone.utc),
        },
        {
            "name": "Arduino Uno R4 WiFi Sensor Bundle",
            "description": "Microcontroller board with built-in ESP32-S3 WiFi/Bluetooth and 37-in-1 sensor kit.",
            "category": "Microcontrollers",
            "department_id": dept_ids["ECE"],
            "lab_id": lab_ids["IoT & Embedded Systems Lab"],
            "status": "available",
            "quantity": 15,
            "available_quantity": 15,
            "tags": ["Arduino", "IoT", "WiFi", "Microcontroller"],
            "created_at": datetime.now(timezone.utc),
        },
    ]

    inserted = 0
    for item in sample_equipment:
        if not db.equipment.find_one({"name": item["name"]}):
            db.equipment.insert_one(item)
            inserted += 1

    print(f"✅ Seeded {inserted} equipment items successfully!")