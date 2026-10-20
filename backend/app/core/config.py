from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import os
import secrets
import sys

import yaml


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


def _load_dotenv() -> None:
    """加载 backend/.env 与项目根 .env，把凭据注入 os.environ。

    设计要点：
    - 真实系统环境变量优先级最高（已存在则跳过），方便 CI / 容器覆盖；
    - 支持 `export KEY=VALUE`、成对引号、# 注释与空行；
    - 文件缺失不报错，仅静默跳过。
    """
    for env_path in (BACKEND_ROOT / ".env", PROJECT_ROOT / ".env"):
        if not env_path.is_file():
            continue
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()


def resolve_project_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (BACKEND_ROOT / candidate).resolve()


def load_config() -> Dict[str, Any]:
    config_path = BACKEND_ROOT / "config" / "config.yaml"
    if not config_path.exists():
        config_path = BACKEND_ROOT / "config.example.yaml"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    llm = data.setdefault("llm", {})
    llm["api_key"] = os.getenv("MEDIX_API_KEY", llm.get("api_key", ""))
    llm["base_url"] = os.getenv("MEDIX_BASE_URL", llm.get("base_url", ""))
    llm["model_name"] = os.getenv("MEDIX_MODEL_NAME", llm.get("model_name", ""))
    vlm = data.setdefault("vlm", {})
    vlm["api_key"] = os.getenv("MEDIX_VLM_API_KEY", vlm.get("api_key", ""))
    vlm["base_url"] = os.getenv("MEDIX_VLM_BASE_URL", vlm.get("base_url", ""))
    vlm["model_name"] = os.getenv("MEDIX_VLM_MODEL_NAME", vlm.get("model_name", ""))
    if os.getenv("MEDIX_ENABLE_LLM"):
        data.setdefault("features", {})["enable_llm"] = os.getenv("MEDIX_ENABLE_LLM", "").lower() in {"1", "true", "yes", "on"}
    data["rag"]["knowledge_dir"] = str(resolve_project_path(data["rag"]["knowledge_dir"]))
    if data["rag"].get("triage_kb_dir"):
        data["rag"]["triage_kb_dir"] = str(resolve_project_path(data["rag"]["triage_kb_dir"]))
    db = data.setdefault("database", {})
    if "sqlite_path" in db:
        db["sqlite_path"] = str(resolve_project_path(db["sqlite_path"]))
    db["type"] = os.getenv("MEDIX_DB_TYPE", db.get("type", "sqlite"))
    db["postgres_url"] = os.getenv("MEDIX_POSTGRES_URL", db.get("postgres_url", ""))
    emb = data.setdefault("embedding", {})
    emb["api_key"] = os.getenv("MEDIX_EMBEDDING_API_KEY", emb.get("api_key", ""))
    emb["base_url"] = os.getenv("MEDIX_EMBEDDING_BASE_URL", emb.get("base_url", ""))
    emb["model_name"] = os.getenv("MEDIX_EMBEDDING_MODEL_NAME", emb.get("model_name", ""))
    if "chroma" in data:
        data["chroma"]["persist_dir"] = str(resolve_project_path(data["chroma"]["persist_dir"]))
    if "upload" in data:
        data["upload"]["storage_dir"] = str(resolve_project_path(data["upload"]["storage_dir"]))
    auth = data.setdefault("auth", {})
    auth["token_secret"] = os.getenv("MEDIX_TOKEN_SECRET", auth.get("token_secret", ""))
    if not auth.get("token_secret"):
        # 绝不回退到硬编码弱密钥：随机生成，重启后旧 token 失效并显式告警
        auth["token_secret"] = secrets.token_urlsafe(48)
        print(
            "[config] 警告：未配置 MEDIX_TOKEN_SECRET，已生成本次进程的临时签名密钥；"
            "服务重启后所有登录状态将失效。请在 backend/.env 中设置固定值。",
            file=sys.stderr,
        )
    admin = data.setdefault("admin", {})
    admin["username"] = os.getenv("MEDIX_ADMIN_USERNAME", admin.get("username", ""))
    admin["password"] = os.getenv("MEDIX_ADMIN_PASSWORD", admin.get("password", ""))
    return data


SETTINGS = load_config()
