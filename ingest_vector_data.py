"""
将历史虚假新闻/政策文档写入 Chroma 向量数据库。

输入文件格式（CSV）字段：
source_id,title,content,source_type,url,published_at
source_id、content字段必填
"""

import csv
import os
from typing import List

from runtime_config import setup_ingest_runtime_interactive
from vector_store import ChromaEvidenceStore, SourceDocument

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 直接改这里即可（默认与本仓库同目录）
CSV_FILE_PATH = os.path.join(_BASE_DIR, "sample_vector_docs.csv")
COLLECTION_NAME = "sg_factcheck_knowledge_base"
CHUNK_WORDS = 300
OVERLAP_WORDS = 50
def load_docs_from_csv(path: str) -> List[SourceDocument]:
    docs: List[SourceDocument] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=2):
            source_id = (row.get("source_id") or "").strip()
            title = (row.get("title") or "").strip()
            content = (row.get("content") or "").strip()
            if not source_id or not content:
                raise ValueError(f"Invalid CSV row at line {idx}: source_id/content is required.")
            docs.append(
                SourceDocument(
                    source_id=source_id,
                    title=title or source_id,
                    content=content,
                    source_type=(row.get("source_type") or "policy_or_factcheck").strip(),
                    url=(row.get("url") or "").strip(),
                    published_at=(row.get("published_at") or "").strip(),
                )
            )
    return docs


def main():
    model_name = setup_ingest_runtime_interactive()

    docs = load_docs_from_csv(CSV_FILE_PATH)
    store = ChromaEvidenceStore(collection_name=COLLECTION_NAME)
    total_chunks = store.upsert_documents(
        docs,
        chunk_words=CHUNK_WORDS,
        overlap_words=OVERLAP_WORDS,
    )

    print(f"CSV file           : {CSV_FILE_PATH}")
    print(f"Ingested source docs: {len(docs)}")
    print(f"Upserted chunks    : {total_chunks}")
    print(f"Collection         : {COLLECTION_NAME}")
    print(f"Embedding model    : {model_name}")


if __name__ == "__main__":
    main()
