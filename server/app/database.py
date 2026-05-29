from sqlmodel import SQLModel, create_engine, Session

import os

# /data is the persistent volume on HF Spaces; fall back to local data/ dir
_DATA_BASE = "/data" if os.path.isdir("/data") else os.path.join(os.path.dirname(__file__), "..", "data")
DATA_DIR = os.environ.get("DATA_DIR", _DATA_BASE)
os.makedirs(DATA_DIR, exist_ok=True)
sqlite_file_name = os.path.join(DATA_DIR, "database.db")
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

