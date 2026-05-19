import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.internhunter.storage.session import engine
from src.internhunter.storage.models import Base


def upgrade():
    print("Verifying database tables...")

    try:
        Base.metadata.create_all(bind=engine)
        print("Table verification complete.")
    except Exception as e:
        print(f"Failed to create tables: {e}")

if __name__ == "__main__":
    upgrade()
