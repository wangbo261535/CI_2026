import getpass
import os

from model_config import (
    DEFAULT_CLAIM_EXTRACT_MODEL,
    DEFAULT_CLAIM_JUDGE_MODEL,
    DEFAULT_EMBEDDING_MODEL,
)


def _prompt_model(label: str, default: str) -> str:
    s = input(f"{label}（回车默认 {default}）: ").strip()
    return s or default


def _prompt_key(env_name: str, label: str) -> None:
    raw = getpass.getpass(f"{label} API Key（必填）: ").strip()
    if not raw:
        raise ValueError(f"{label} API Key 不能为空。")
    os.environ[env_name] = raw


def setup_pipeline_runtime_interactive() -> tuple[str, str, str]:
    """三轮模型配置 + Tavily Key（若未设置环境变量则提示输入）。"""
    print("--- [1/4] Claim 提取 ---")
    cm = _prompt_model("Claim 提取模型", DEFAULT_CLAIM_EXTRACT_MODEL)
    _prompt_key("CLAIM_EXTRACT_API_KEY", "Claim 提取")
    os.environ["CLAIM_EXTRACT_MODEL"] = cm

    print("\n--- [2/4] Judge ---")
    jm = _prompt_model("Judge 模型", DEFAULT_CLAIM_JUDGE_MODEL)
    _prompt_key("JUDGE_API_KEY", "Judge")
    os.environ["CLAIM_JUDGE_MODEL"] = jm

    print("\n--- [3/4] Embedding ---")
    em = _prompt_model("Embedding 模型", DEFAULT_EMBEDDING_MODEL)
    _prompt_key("EMBEDDING_API_KEY", "Embedding")
    os.environ["EMBEDDING_MODEL"] = em

    print("\n--- [4/4] Tavily 搜索 ---")
    if not (os.environ.get("TAVILY_API_KEY") or "").strip():
        _prompt_key("TAVILY_API_KEY", "Tavily")
    else:
        print("已设置 TAVILY_API_KEY，跳过输入。")

    return cm, jm, em


def setup_ingest_runtime_interactive() -> str:
    """Embedding 模型 + Key 各一问。"""
    print("--- 向量库写入 ---")
    em = _prompt_model("Embedding 模型", DEFAULT_EMBEDDING_MODEL)
    _prompt_key("EMBEDDING_API_KEY", "Embedding")
    os.environ["EMBEDDING_MODEL"] = em
    return em
