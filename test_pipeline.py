"""
联调测试：gemini_for_claim (Gemini claim 提取 + query 生成)
        → req_tavily       (Tavily 搜索引擎检索)

用法:
    python test_pipeline.py
    python test_pipeline.py "听说新加坡昨天要封城了"
"""

import copy
import sys
import json
from typing import Any, Dict, Optional

from runtime_config import setup_pipeline_runtime_interactive
from claim_judge import aggregate_news_label, judge_claim
from gemini_for_claim import build_search_tasks
from model_config import get_claim_extract_model, get_judge_model
from req_tavily import tavily_search
from result_store import persist_pipeline_result
from vector_store import ChromaEvidenceStore


DEMO_TEXTS = [
    "Heard that Singapore will have a lockdown yesterday, and CPF withdrawals are not possible."
]

TAVILY_SCORE_THRESHOLD = 0.45
VECTOR_DISTANCE_THRESHOLD = 0.35


def _build_event_date(start_date: Optional[str], end_date: Optional[str]) -> str:
    if start_date and end_date:
        return f"{start_date} to {end_date}"
    if start_date and not end_date:
        return f"from {start_date}"
    if end_date and not start_date:
        return f"until {end_date}"
    return "unspecified"


def _filter_tavily_evidence(evidence: list[dict]) -> list[dict]:
    if not evidence:
        return []
    filtered = [e for e in evidence if float(e.get("score", 0.0)) >= TAVILY_SCORE_THRESHOLD]
    if filtered:
        return filtered
    # Fallback: keep top-1 to avoid empty evidence path.
    return [max(evidence, key=lambda x: float(x.get("score", 0.0)))]


def _best_vector_distance(item: dict) -> float:
    distances = [
        m.get("distance")
        for m in item.get("matched_chunks", [])
        if m.get("distance") is not None
    ]
    if not distances:
        return 1e9
    return min(float(d) for d in distances)


def _filter_vector_evidence(evidence: list[dict]) -> list[dict]:
    if not evidence:
        return []
    filtered = [e for e in evidence if _best_vector_distance(e) <= VECTOR_DISTANCE_THRESHOLD]
    if filtered:
        return filtered
    # Fallback: keep top-1 nearest source to avoid empty evidence path.
    return [min(evidence, key=_best_vector_distance)]


# ── run pipeline ──────────────────────────────────────────────────────────────
def run_pipeline(
    raw_text: str,
    model_claim: Optional[str] = None,
    model_judge: Optional[str] = None,
) -> dict:
    # data stream:
    # raw_text -> Gemini claim/query -> Tavily + VectorDB retrieval -> claim-level judge -> news-level aggregation
    mc = model_claim or get_claim_extract_model()
    mj = model_judge or get_judge_model()
    tasks, module1_prompt, module1_response_text = build_search_tasks(raw_text, model_name=mc)
    today_date = tasks[0].today_date if tasks else ""
    vector_store = ChromaEvidenceStore()

    claims = []
    for task in tasks:
        event_date = _build_event_date(task.start_date, task.end_date)
        tavily_evidence_raw = tavily_search(
            query=task.query,
            start_date=task.start_date,
            end_date=task.end_date,
        )
        vector_evidence_raw = vector_store.search_and_expand(query=task.claim, n_results=3)
        tavily_evidence = _filter_tavily_evidence(tavily_evidence_raw)
        vector_evidence = _filter_vector_evidence(vector_evidence_raw)
        verdict = judge_claim(
            claim=task.claim,
            tavily_evidence=tavily_evidence,
            vector_evidence=vector_evidence,
            event_date=event_date,
            today_date=today_date,
            model_name=mj,
        )
        claims.append(
            {
                "claim": task.claim,
                "query": task.query,
                "start_date": task.start_date,
                "end_date": task.end_date,
                "event_date": event_date,
                "tavily_evidence_count": len(tavily_evidence),
                "vector_evidence_count": len(vector_evidence),
                "tavily_evidence": tavily_evidence,
                "vector_evidence": vector_evidence,
                "verdict": verdict,
            }
        )

    news_label = aggregate_news_label(claims) if claims else "Not Enough Evidence"
    return {
        "raw_text": raw_text,
        "today_date": today_date,
        "claim_count": len(claims),
        "news_label": news_label,
        "claims": claims,
        "model_claim_extract": mc,
        "model_judge": mj,
        "module1_prompt": module1_prompt,
        "module1_response_text": module1_response_text,
    }


# ── print results ──────────────────────────────────────────────────────────────
def print_results(result: dict):
    print(f"\n  原始输入 : {result['raw_text']}")
    print(f"  今日日期 : {result['today_date']}")
    print(f"  Claim 数 : {result['claim_count']}")
    print(f"  新闻结论 : {result['news_label']}")

    for i, c in enumerate(result["claims"], 1):
        print(f"\n{'='*70}")
        print(f"  Claim #{i}")
        print(f"{'='*70}")
        print(f"  Claim    : {c['claim']}")
        print(f"  Query    : {c['query']}")
        print(f"  搜索区间 : {c['start_date'] or '无'} ~ {c['end_date'] or '无'}")
        print(f"  Event Date: {c['event_date']}")
        print(f"  Tavily 证据数量 : {c['tavily_evidence_count']}")
        print(f"  Vector 证据数量 : {c['vector_evidence_count']}")
        print(f"  判定标签 : {c['verdict']['label']}")
        print(f"  判定原因 : {c['verdict']['reason']}")
        print(f"  引用证据 : {c['verdict'].get('citations', [])}")

        if c["tavily_evidence"]:
            print("  [Tavily Evidence]")
            for j, e in enumerate(c["tavily_evidence"], 1):
                print(f"\n  --- T{j} ---")
                print(f"  Title   : {e['title']}")
                print(f"  Score   : {e['score']:.4f}")
                print(f"  URL     : {e['url']}")
                print(f"  Content : {e['content'][:200]}...")
        else:
            print("  [Tavily Evidence] (未检索到相关证据)")

        if c["vector_evidence"]:
            print("  [VectorDB Evidence]")
            for j, e in enumerate(c["vector_evidence"], 1):
                distances = [m.get("distance") for m in e.get("matched_chunks", []) if m.get("distance") is not None]
                best_distance = min(distances) if distances else None
                print(f"\n  --- V{j} source_id={e['source_id']} ---")
                print(f"  Title   : {e['title']}")
                if best_distance is not None:
                    print(f"  Distance: {best_distance:.4f}")
                else:
                    print("  Distance: N/A")
                print(f"  URL     : {e['url']}")
                print(f"  Type    : {e['source_type']}")
                print(f"  Matched : {len(e.get('matched_chunks', []))} chunks")
                print(f"  Content : {e['full_text'][:220]}...")
        else:
            print("  [VectorDB Evidence] (未检索到相关证据)")

    print(f"\n{'='*70}")
    print(
        "完整 JSON 输出（不含 module1_prompt / module1_response_text / module3_prompt / "
        "module3_response_text，避免终端过长；落库与 CSV 仍含全文）："
    )
    slim: Dict[str, Any] = copy.deepcopy(result)
    slim.pop("module1_prompt", None)
    slim.pop("module1_response_text", None)
    for c in slim.get("claims", []):
        v = c.get("verdict")
        if isinstance(v, dict):
            v.pop("module3_prompt", None)
            v.pop("module3_response_text", None)
    print(json.dumps(slim, ensure_ascii=False, indent=2))


# ── Test Entry Point ──────────────────────────────────────────────────────────────
def main():
    claim_m, judge_m, emb_m = setup_pipeline_runtime_interactive()
    if len(sys.argv) > 1:
        texts = [" ".join(sys.argv[1:])]
    else:
        user_text = input("请输入要检测的 raw_text（回车使用默认 DEMO）: ").strip()
        texts = [user_text] if user_text else DEMO_TEXTS

    for idx, text in enumerate(texts):
        print(f"\n{'#'*70}")
        print(f"# Test case {idx + 1}: {text[:60]}{'...' if len(text) > 60 else ''}")
        print(f"{'#'*70}")

        result = run_pipeline(text)
        print_results(result)
        news_run_id = persist_pipeline_result(
            result,
            model_claim_extract=result.get("model_claim_extract"),
            model_judge=result.get("model_judge"),
        )
        print(f"\n已写入 SQL 数据库: news_run.id={news_run_id}")
        print(f"Claim extract model: {claim_m}")
        print(f"Judge model          : {judge_m}")
        print(f"Embedding model      : {emb_m}")


if __name__ == "__main__":
    main()
