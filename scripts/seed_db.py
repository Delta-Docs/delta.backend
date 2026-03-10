import sys
import os
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User
from app.core import security

def seed_db():
    db: Session = SessionLocal()
    try:
        # Check if test user exists
        user = db.query(User).filter(User.email == "test@example.com").first()
        if not user:
            print("Creating test user: test@example.com")
            user = User(
                email="test@example.com",
                full_name="Test User",
                password_hash=security.get_hash("testpassword123"),
            )
            db.add(user)
            db.commit()
            print("Test user created successfully.")
        else:
            print("Test user already exists.")
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # Add app directory to sys.path to allow imports
    sys.path.append(os.getcwd())
    seed_db()
