import os
import sys

# Ensure backend directory is in python path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.services.ingestion import DataIngestionService

if __name__ == "__main__":
    print("Executing data ingestion across CSV, XLSX, PDF, and JSON...")
    result = DataIngestionService.ingest_all()
    print("Ingestion Results:")
    print(f"Success: {result['success']}")
    print(f"Imported Files: {result['imported_files']}")
    print(f"Total Records: {result['total_records']}")
    if result["errors"]:
        print(f"Notices / Errors ({len(result['errors'])}):")
        for err in result["errors"]:
            print(f"  - {err}")
