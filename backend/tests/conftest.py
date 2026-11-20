import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

@pytest.fixture(autouse=True)
def isolated_database():
    from app.main import app
    from app.database.connection import Base,get_db
    from app.database import models  # noqa: F401
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)
    def override_db():
        db=TestingSession()
        try:yield db
        finally:db.close()
    app.dependency_overrides[get_db]=override_db
    yield
    app.dependency_overrides.clear();Base.metadata.drop_all(engine);engine.dispose()
