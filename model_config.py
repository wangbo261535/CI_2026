"""
模型 ID 与 API Key，由环境变量提供；交互脚本会写入 CLAIM_EXTRACT_* / CLAIM_JUDGE_* / EMBEDDING_*。

各阶段 Key 只读对应专用变量，互不混用、不回退。

模型名环境变量：CLAIM_EXTRACT_MODEL、CLAIM_JUDGE_MODEL、EMBEDDING_MODEL
"""

import os
from typing import Optional

DEFAULT_CLAIM_EXTRACT_MODEL = "gemini-3-flash-preview"
DEFAULT_CLAIM_JUDGE_MODEL = "gemini-3-flash-preview"
DEFAULT_EMBEDDING_MODEL = "gemini-embedding-2-preview"


def _first_nonempty_env(*keys: str) -> Optional[str]:
    for k in keys:
        v = os.environ.get(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return None


def get_claim_extract_model() -> str:
    return _first_nonempty_env("CLAIM_EXTRACT_MODEL") or DEFAULT_CLAIM_EXTRACT_MODEL


def get_judge_model() -> str:
    return _first_nonempty_env("CLAIM_JUDGE_MODEL") or DEFAULT_CLAIM_JUDGE_MODEL


def get_embedding_model() -> str:
    return _first_nonempty_env("EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL


def get_claim_extract_api_key() -> str:
    k = _first_nonempty_env("CLAIM_EXTRACT_API_KEY")
    if not k:
        raise ValueError("Missing CLAIM_EXTRACT_API_KEY.")
    return k


def get_judge_api_key() -> str:
    k = _first_nonempty_env("JUDGE_API_KEY")
    if not k:
        raise ValueError("Missing JUDGE_API_KEY.")
    return k


def get_embedding_api_key() -> str:
    k = _first_nonempty_env("EMBEDDING_API_KEY")
    if not k:
        raise ValueError("Missing EMBEDDING_API_KEY.")
    return k
