import os
from typing import Optional
from tavily import TavilyClient

WHITELIST_DOMAINS = [
    # Tier 1: Singapore Government Official Domain
    "gov.sg",
    "police.gov.sg",
    "moh.gov.sg",
    "cpf.gov.sg",
    "mom.gov.sg",
    "moe.gov.sg",
    "mas.gov.sg",
    "mha.gov.sg",
    "mof.gov.sg",
    "population.gov.sg",
    "pofmaoffice.gov.sg",
    # Tier 2: Singapore mainstream media
    "channelnewsasia.com",
    "straitstimes.com",
    "businesstimes.com.sg",
    "sg.news.yahoo.com",
    "todayonline.com",
    "mothership.sg",
    "blackdot.sg",
]

def _tavily_client() -> TavilyClient:
    key = (os.environ.get("TAVILY_API_KEY") or "").strip()
    if not key:
        raise ValueError(
            "缺少环境变量 TAVILY_API_KEY。请勿在代码中硬编码密钥，请在 shell 或 .env 中配置。"
        )
    return TavilyClient(api_key=key)


# ── tavily search ──────────────────────────────────────────────────────────────
def tavily_search(
    query: str,
    search_depth: str = "advanced",  # 搜索深度可配
    max_results: int = 3,
    time_range: Optional[str] = None,  # 时间范围可配
    start_date: Optional[str] = None,  # 起始日期可配
    end_date: Optional[str] = None,  # 结束日期可配
) -> list[dict]:
    """调用 Tavily Search API，在新加坡白名单域名内检索证据。
            query:        由模块 3.2 生成的英文搜索查询。
            search_depth: 搜索深度 ("basic" | "advanced" | "fast" | "ultra-fast")可选，默认 "advanced" 以获取更高相关性。
            time_range:   时间范围筛选 ("day" | "week" | "month" | "year")，可选。
            start_date:   起始日期 (YYYY-MM-DD)，由模块 3.2 时间感知输出，可选。
            end_date:     结束日期 (YYYY-MM-DD)，由模块 3.2 时间感知输出，可选。
            max_results:  返回结果数上限，默认 10 条供后续重排序模块筛选。
        经过格式化的证据列表，每条包含 title, url, content, score, start_date, end_date, time_range。
    """
    params: dict = {
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
        "include_domains": WHITELIST_DOMAINS,
        "country": "singapore",
        "include_answer": False,
        "include_raw_content": False,
    }

    if time_range:
        params["time_range"] = time_range
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date

    response = _tavily_client().search(**params)

    results = []
    for r in response.get("results", []):
        results.append(
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "score": r.get("score", 0.0),
                "start_date": start_date,
                "end_date": end_date,
                "time_range": time_range,
            }
        )

    return results


# ---------------------------------------------------------------------------
# 直接运行时的演示用例
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo_queries = [
        {
            "query": "Singapore lockdown policy 2026",
            "search_depth": "advanced",
            "time_range": "month",
        }
        #        {
        #            "query": "CPF withdrawal policy changes Singapore",
        #            "search_depth": "basic",
        #            "start_date": "2025-01-01",
        #            "end_date": "2026-02-27",
        #        },
    ]

    for q in demo_queries:
        print(f"\n{'='*60}")
        print(f"Query: {q['query']}")
        print(f"{'='*60}")
        evidence = tavily_search(**q)
        for i, e in enumerate(evidence, 1):
            print(f"\n--- Evidence {i} (score: {e['score']:.4f}) ---")
            print(f"Title : {e['title']}")
            print(f"URL   : {e['url']}")
            print(f"Content: {e['content'][:200]}...")
        # tavily 不返回发表时间，需要拼接 start_date/end_date 作为查询上下文
        if not evidence:
            print("No results found.")
