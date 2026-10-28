import os
import sys
import pytest

# Ensure backend directory is in python path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.services.ingestion import DataIngestionService
from app.repositories.mongo_repository import repository

@pytest.fixture(scope="session", autouse=True)
def setup_test_data():
    """Initializes repository with test data."""
    DataIngestionService.ingest_all()
    yield
