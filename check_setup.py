"""
Quick setup check - verifies environment and configuration
"""
import sys
import os

print("="*70)
print("SYSTEM SETUP CHECK")
print("="*70)

# Check 1: Python version
print(f"\n[1/7] Python version: {sys.version}")
if sys.version_info < (3, 9):
    print("❌ Python 3.9+ required")
else:
    print("✓ Python version OK")

# Check 2: Environment variables
print("\n[2/7] Checking environment variables...")
required_env = ['OPENAI_API_KEY', 'QDRANT_HOST', 'QDRANT_API_KEY', 'DATABASE_URL']
missing_env = []

for env_var in required_env:
    value = os.getenv(env_var)
    if value:
        # Mask sensitive values
        if 'KEY' in env_var or 'URL' in env_var:
            masked = value[:10] + "..." if len(value) > 10 else "***"
            print(f"  ✓ {env_var} = {masked}")
        else:
            print(f"  ✓ {env_var} = {value}")
    else:
        print(f"  ❌ {env_var} = NOT SET")
        missing_env.append(env_var)

if missing_env:
    print(f"\n⚠ Missing environment variables: {', '.join(missing_env)}")
    print("Please check your .env file")

# Check 3: Required packages
print("\n[3/7] Checking required packages...")
required_packages = [
    'flask',
    'flask_sock',
    'sqlalchemy',
    'psycopg2',
    'openai',
    'qdrant_client',
    'pydantic',
]

for package in required_packages:
    try:
        __import__(package.replace('_', '-'))
        print(f"  ✓ {package}")
    except ImportError:
        print(f"  ❌ {package} - NOT INSTALLED")

# Check 4: Database connection
print("\n[4/7] Checking database connection...")
try:
    from dotenv import load_dotenv
    load_dotenv()

    from sqlalchemy import create_engine, text
    DATABASE_URL = os.getenv('DATABASE_URL')

    if DATABASE_URL:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print(f"  ✓ Database connection successful")
    else:
        print(f"  ❌ DATABASE_URL not set")
except Exception as e:
    print(f"  ❌ Database connection failed: {e}")

# Check 5: Qdrant connection
print("\n[5/7] Checking Qdrant connection...")
try:
    from qdrant_client import QdrantClient

    host = os.getenv('QDRANT_HOST')
    api_key = os.getenv('QDRANT_API_KEY')
    https = os.getenv('QDRANT_HTTPS', 'True').lower() == 'true'

    if host and api_key:
        client = QdrantClient(
            url=f"{'https' if https else 'http'}://{host}:6333",
            api_key=api_key,
        )
        collections = client.get_collections()
        print(f"  ✓ Qdrant connection successful")
        print(f"  Collections: {[c.name for c in collections.collections]}")
    else:
        print(f"  ❌ QDRANT_HOST or QDRANT_API_KEY not set")
except Exception as e:
    print(f"  ❌ Qdrant connection failed: {e}")

# Check 6: OpenAI API
print("\n[6/7] Checking OpenAI API...")
try:
    from openai import OpenAI

    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        client = OpenAI(api_key=api_key)
        # Quick test
        print(f"  ✓ OpenAI API key configured")
    else:
        print(f"  ❌ OPENAI_API_KEY not set")
except Exception as e:
    print(f"  ❌ OpenAI check failed: {e}")

# Check 7: Database tables
print("\n[7/7] Checking database tables...")
try:
    from sqlalchemy import create_engine, inspect

    DATABASE_URL = os.getenv('DATABASE_URL')
    if DATABASE_URL:
        engine = create_engine(DATABASE_URL)
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        required_tables = ['call_sessions', 'transcription_segments', 'agent_actions', 'suggestions']
        for table in required_tables:
            if table in tables:
                print(f"  ✓ {table}")
            else:
                print(f"  ❌ {table} - NOT FOUND (run: python app/database/init_call_tracking.py)")

        if not any(t in tables for t in required_tables):
            print("\n⚠ No tables found. Initialize database:")
            print("  python app/database/init_call_tracking.py")
except Exception as e:
    print(f"  ❌ Table check failed: {e}")

print("\n" + "="*70)
print("SETUP CHECK COMPLETE")
print("="*70)

if not missing_env:
    print("\n✅ Basic configuration looks good!")
    print("\nNext steps:")
    print("1. Make sure all packages are installed: pip install -r requirements.txt")
    print("2. Initialize database tables: python app/database/init_call_tracking.py")
    print("3. Run test: python examples/test_realtime_flow.py")
else:
    print("\n⚠ Please fix the issues above before proceeding")
