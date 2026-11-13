import os
import shutil
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "app"))

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
TEST_CHROMA_DIR = PROJECT_ROOT / "storage" / "chroma_test"
TEST_UPLOAD_DIR = PROJECT_ROOT / "storage" / "uploads_test"

if not TEST_DATABASE_URL:
    raise RuntimeError(
        "拒绝启动测试：请通过 TEST_DATABASE_URL 显式配置专用测试数据库连接"
    )

from sqlalchemy.engine import make_url as _make_url

_test_url = _make_url(TEST_DATABASE_URL)
if (
    _test_url.drivername != "mysql+pymysql"
    or not _test_url.database
    or not _test_url.username
    or not _test_url.database.endswith("_test")
    or _test_url.host not in {"127.0.0.1", "localhost", "::1"}
):
    raise RuntimeError(
        "拒绝启动测试：TEST_DATABASE_URL 必须是本机 MySQL 且数据库名以 _test 结尾"
    )

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["CHROMA_DIR"] = str(TEST_CHROMA_DIR)
os.environ["UPLOAD_DIR"] = str(TEST_UPLOAD_DIR)
os.environ["LLM_API_KEY"] = "replace_me"
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pymysql
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

import models  # noqa: F401
from core.settings import settings
from db.base import Base
from db.session import SessionLocal, engine
from main import app
from models.knowledge_base import KnowledgeBase
from models.knowledge_group import GroupMember, KnowledgeGroup


def _create_test_database() -> None:
    url = make_url(settings.database_url)
    if url.database != _test_url.database or not url.database.endswith("_test"):
        raise RuntimeError("拒绝清理：最终数据库连接未通过测试库名称校验")
    connection = pymysql.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        charset="utf8mb4",
        autocommit=True,
    )
    with connection.cursor() as cursor:
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{url.database}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    connection.close()


@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    _create_test_database()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    shutil.rmtree(TEST_UPLOAD_DIR, ignore_errors=True)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def make_user(client):
    def _make(prefix: str = "user"):
        username = f"{prefix}_{uuid.uuid4().hex[:8]}"
        register = client.post(
            "/api/auth/register",
            json={"username": username, "password": "Passw0rd!"},
        )
        assert register.status_code == 201, register.text
        login = client.post(
            "/api/auth/login",
            json={"username": username, "password": "Passw0rd!"},
        )
        return {
            "id": register.json()["id"],
            "username": username,
            "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
        }

    return _make


@pytest.fixture()
def make_group(db):
    def _make(name: str, owner_id: int):
        group = KnowledgeGroup(name=name, group_type="department", created_by=owner_id)
        db.add(group)
        db.flush()
        db.add(GroupMember(group_id=group.id, user_id=owner_id, role="admin"))
        knowledge_base = KnowledgeBase(
            name=f"{name}知识库",
            scope_type="enterprise_group",
            group_id=group.id,
        )
        db.add(knowledge_base)
        db.commit()
        return group.id, knowledge_base.id

    return _make


@pytest.fixture()
def make_personal_kb(db):
    def _make(owner_id: int):
        knowledge_base = KnowledgeBase(
            name="个人知识库",
            scope_type="personal",
            owner_user_id=owner_id,
        )
        db.add(knowledge_base)
        db.commit()
        return knowledge_base.id

    return _make


@pytest.fixture()
def add_member(db):
    def _add(group_id: int, user_id: int, role: str = "member"):
        db.add(GroupMember(group_id=group_id, user_id=user_id, role=role))
        db.commit()

    return _add
