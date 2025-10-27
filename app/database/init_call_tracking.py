"""
Initialize database tables for call tracking and agent system
Run this script to create all necessary tables
"""
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.database.postgresql_session import engine
from app.models.call_session import Base, CallSession, TranscriptionSegment, AgentAction, Suggestion
from app.models.query_logs import QueryLogs


def init_database():
    """Create all tables in the database"""
    try:
        print("Creating database tables...")
        Base.metadata.create_all(engine)
        print("✅ Successfully created tables:")
        print("   - call_sessions")
        print("   - transcription_segments")
        print("   - agent_actions")
        print("   - suggestions")
        print("   - query_logs (already exists)")
        print("\nDatabase is ready for use!")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        raise


if __name__ == "__main__":
    init_database()
