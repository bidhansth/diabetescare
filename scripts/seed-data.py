#!/usr/bin/env python3
import os
import sys
import random
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import (
    create_user, create_entry, create_medication, create_resource,
    get_resources, get_user_by_email, update_user_role,
    create_topic, get_topics,
)
from app.auth import hash_password

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "Demo@123"
DEMO_NAME = "Demo User"

ADMIN_EMAIL = "admin@diabetescare.com"
ADMIN_PASSWORD = "Admin@123"
ADMIN_NAME = "Admin"


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def main():
    existing_demo = get_user_by_email(DEMO_EMAIL)
    existing_admin = get_user_by_email(ADMIN_EMAIL)
    patched = False

    if existing_demo:
        if not existing_demo.get("role"):
            update_user_role(existing_demo["PK"].replace("USER#", ""), "user")
            print(f"  Patched role for: {DEMO_EMAIL}")
            patched = True
        existing_demo = get_user_by_email(DEMO_EMAIL)

    if existing_admin:
        if not existing_admin.get("role"):
            update_user_role(existing_admin["PK"].replace("USER#", ""), "admin")
            print(f"  Patched role for: {ADMIN_EMAIL}")
            patched = True
        existing_admin = get_user_by_email(ADMIN_EMAIL)

    if existing_demo and existing_admin and not patched:
        print("Seed data already exists \u2014 skipping")
        return

    print("Seeding demo data...")

    user_id = None
    if not existing_demo:
        user_id = str(uuid.uuid4())
        password_hash = hash_password(DEMO_PASSWORD)
        create_user(user_id, DEMO_EMAIL, DEMO_NAME, password_hash, role="user")
        print(f"  Created user: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    else:
        user_id = existing_demo["PK"].replace("USER#", "")
        print(f"  User already exists: {DEMO_EMAIL}")

    admin_id = None
    if not existing_admin:
        admin_id = str(uuid.uuid4())
        password_hash = hash_password(ADMIN_PASSWORD)
        create_user(admin_id, ADMIN_EMAIL, ADMIN_NAME, password_hash, role="admin")
        print(f"  Created admin: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    else:
        admin_id = existing_admin["PK"].replace("USER#", "")
        print(f"  Admin already exists: {ADMIN_EMAIL}")

    if not existing_demo:
        meds = [
            ("Metformin", "500mg"),
            ("Insulin Lispro", "10U"),
            ("Atorvastatin", "20mg"),
        ]
        med_ids = []
        for name, dosage in meds:
            med = create_medication(user_id, name, dosage)
            med_ids.append(med["medicationId"])
            print(f"  Created medication: {name} {dosage}")

        now = datetime.now(timezone.utc)
        glucose_count = 0
        meal_count = 0
        med_entry_count = 0
        exercise_count = 0
        meal_names = [
            "Oatmeal with berries",
            "Grilled chicken salad",
            "Pasta with vegetables",
            "Salmon with rice",
            "Turkey sandwich",
            "Vegetable stir-fry",
            "Scrambled eggs with toast",
            "Bean and rice bowl",
        ]
        exercise_names = [
            "Morning walk - 30 min",
            "Cycling - 20 min",
            "Yoga - 45 min",
            "Swimming - 30 min",
            "Jogging - 20 min",
            "Strength training - 30 min",
        ]

        for days_ago in range(30, -1, -1):
            day = now - timedelta(days=days_ago)

            slots = [
                (7, 0, "Fasting", 105, 15, 0.9),
                (9, 0, "After breakfast", 140, 25, 0.7),
                (12, 0, "Before lunch", 110, 20, 0.6),
                (14, 0, "After lunch", 150, 30, 0.7),
                (18, 0, "Evening", 120, 25, 0.6),
                (22, 0, "Bedtime", 110, 20, 0.8),
            ]
            for hour, minute_offset, note, mean, std, probability in slots:
                if random.random() >= probability:
                    continue
                minute = minute_offset + random.choice([0, 30])
                ts = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                value = clamp(round(random.gauss(mean, std), 1), 40, 350)
                create_entry(
                    user_id, "glucose", value, "mg/dL",
                    notes=note, timestamp=ts.isoformat(),
                )
                glucose_count += 1

            if days_ago % 7 == 0:
                ts = day.replace(hour=3, minute=random.randint(0, 59), second=0, microsecond=0)
                value = clamp(round(random.uniform(50, 65), 1), 40, 350)
                create_entry(
                    user_id, "glucose", value, "mg/dL",
                    notes="Night hypoglycemia", timestamp=ts.isoformat(),
                )
                glucose_count += 1

            if days_ago % 10 == 0:
                ts = day.replace(hour=13, minute=random.randint(0, 59), second=0, microsecond=0)
                value = clamp(round(random.uniform(200, 260), 1), 40, 350)
                create_entry(
                    user_id, "glucose", value, "mg/dL",
                    notes="Post-meal spike", timestamp=ts.isoformat(),
                )
                glucose_count += 1

            if random.random() < 0.5:
                ts = day.replace(
                    hour=random.choice([8, 12, 19]),
                    minute=random.randint(0, 59), second=0, microsecond=0,
                )
                create_entry(
                    user_id, "meal", random.randint(300, 700), "cal",
                    notes=random.choice(meal_names), timestamp=ts.isoformat(),
                )
                meal_count += 1

            if random.random() < 0.4:
                ts = day.replace(
                    hour=random.choice([8, 20]),
                    minute=random.randint(0, 59), second=0, microsecond=0,
                )
                create_entry(
                    user_id, "medication", random.randint(5, 15), "U",
                    medicationId=random.choice(med_ids),
                    medicationName="Insulin Lispro",
                    notes="Insulin dose", timestamp=ts.isoformat(),
                )
                med_entry_count += 1

            if random.random() < 0.35:
                ts = day.replace(
                    hour=random.choice([7, 17]),
                    minute=random.randint(0, 59), second=0, microsecond=0,
                )
                create_entry(
                    user_id, "exercise", random.randint(100, 400), "cal",
                    notes=random.choice(exercise_names), timestamp=ts.isoformat(),
                )
                exercise_count += 1

        print(f"  Created {glucose_count} glucose entries")
        print(f"  Created {meal_count} meal entries")
        print(f"  Created {med_entry_count} medication entries")
        print(f"  Created {exercise_count} exercise entries")

    sample_resources = [
        ("Blood Sugar Level Chart", "pdf", "resources/sample/blood-sugar-chart.pdf"),
        ("Diabetes Diet Guidelines", "pdf", "resources/sample/diet-guidelines.pdf"),
        ("Insulin Injection Guide", "image", "resources/sample/insulin-guide.png"),
        ("Exercise Routine Video", "video", "resources/sample/exercise-routine.mp4"),
    ]

    existing_resources = get_resources()
    if not existing_resources:
        now = datetime.now(timezone.utc).isoformat()
        for res_name, res_type, res_key in sample_resources:
            rid = str(uuid.uuid4())
            create_resource(
                resource_id=rid,
                name=res_name,
                file_type=res_type,
                file_key=res_key,
                file_size=0,
                content_type="application/octet-stream",
                uploaded_by=f"USER#{admin_id}",
                description=f"Sample {res_type} resource for demonstration",
            )
            print(f"  Created resource: {res_name}")
    else:
        print("  Resources already exist")

    sample_topics = [
        "Nutrition & Diet",
        "Medication & Treatment",
        "Exercise & Fitness",
        "Blood Sugar Management",
        "General Discussion",
    ]

    existing_topics = get_topics()
    if not existing_topics:
        for topic_name in sample_topics:
            create_topic(topic_name)
            print(f"  Created topic: {topic_name}")
    else:
        print("  Topics already exist")

    print("Seed complete!")


if __name__ == "__main__":
    main()
