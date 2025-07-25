from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from datetime import datetime
from models import Sources, SourceTypeOptions, GitRemoteOptions
from sqlalchemy.orm import declarative_base
import os

# Set up the PostgreSQL database engine (update with your connection details)
DATABASE_URL = "postgresql://root:root@localhost:5444/bud"
# DATABASE_URL = os.environ["db_uri"]
engine = create_engine(DATABASE_URL)

# Create a session
Session = sessionmaker(bind=engine)
session = Session()

Base = declarative_base()


# Function to seed the database with Sources
def seed_sources():
    # Sample data to seed
    sources_data = [
        {
            "name": "chatbot-arena-leaderboard",
            "url": "https://huggingface.co/spaces/lmsys/chatbot-arena-leaderboard",
            "source_type": SourceTypeOptions.git,
            "git_remote_type": GitRemoteOptions.huggingface,
            "source_file_pattern_start": "leaderboard_table_",
            "source_file_pattern_end": ".csv",
            "source_file_pattern": "leaderboard_table_*.csv",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    ]

    # Insert each source record
    for data in sources_data:
        source = Sources(**data)
        session.add(source)

    # Commit the session
    session.commit()
    print("Sources seeded successfully!")


# Main function to run the seeder
if __name__ == "__main__":
    # Ensure tables exist before seeding
    Base.metadata.create_all(engine)

    # Seed the sources
    seed_sources()
