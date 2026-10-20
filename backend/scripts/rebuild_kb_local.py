"""按当前 embedding 模型重建知识库向量（仅 Markdown + 分诊知识库，跳过超大 PDF）。

用法（在 backend 目录）：
    python scripts/rebuild_kb_local.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import SETTINGS  # noqa: E402
from app.services.chroma_rag_service import get_chroma_service  # noqa: E402
from app.services.kb_ingestor import ingest_file  # noqa: E402


async def run() -> None:
    svc = get_chroma_service()
    if not svc.available:
        print("[ERR] Chroma 不可用")
        return
    if not svc.embed_client.enabled:
        print("[ERR] Embedding 未启用，检查 config.yaml")
        return

    try:
        svc.client.delete_collection(svc.kb_name)
    except Exception:
        pass
    svc.kb_collection = svc.client.get_or_create_collection(
        name=svc.kb_name, metadata={"hnsw:space": "cosine"}
    )
    print(f"[INFO] 已重置 collection: {svc.kb_name}")

    kb_dir = Path(SETTINGS["rag"]["knowledge_dir"])
    triage_dir = Path(SETTINGS["rag"].get("triage_kb_dir") or "")

    files: list[Path] = []
    for p in sorted(kb_dir.rglob("*.md")):
        if "admin_uploads" in p.parts:  # 跳过超大 PDF 目录
            continue
        files.append(p)
    if triage_dir.exists():
        for p in sorted(triage_dir.rglob("*")):
            if p.is_file() and p.suffix.lower() in {".md", ".txt"}:
                files.append(p)

    print(f"[INFO] 发现 {len(files)} 个文件，开始写入 ...")
    total = 0
    for path in files:
        try:
            info = await ingest_file(svc, path)
            total += info["chunks"]
            print(f"  + [{info['type']:>8}] {path.name} -> {info['chunks']} chunks", flush=True)
        except Exception as exc:
            print(f"  ! {path.name} 失败: {exc}", flush=True)

    print(f"\n[OK] 写入 {total} chunks；当前数量：{svc.stats().get('kb_count')}")


if __name__ == "__main__":
    asyncio.run(run())
