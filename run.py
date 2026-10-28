import sys
from pathlib import Path
import uvicorn

if __name__ == "__main__":
    backend_dir = Path(__file__).resolve().parent / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    
    print("==================================================================")
    print(" Starting Learning Path Agent Backend Server on http://127.0.0.1:8000")
    print(" API Documentation: http://127.0.0.1:8000/docs")
    print("==================================================================")
    uvicorn.run("app.main:app", app_dir=str(backend_dir), host="127.0.0.1", port=8000, reload=True)
