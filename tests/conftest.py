import os

os.environ["OPENAI_API_KEY"] = "sk-test-key"
os.environ["ENVIRONMENT"] = "development"
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test"
