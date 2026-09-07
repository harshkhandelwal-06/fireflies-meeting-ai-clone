import os
import multiprocessing
import uvicorn
from app.main import app


def main():
    multiprocessing.freeze_support()
    db_path = os.getenv("FIREFLIES_DB_PATH")
    if db_path:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    host = os.getenv("FIREFLIES_HOST", "127.0.0.1")
    port = int(os.getenv("FIREFLIES_PORT", "8000"))
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
