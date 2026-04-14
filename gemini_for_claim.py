import re
import json
from dataclasses import dataclass, asdict
from datetime import date
from typing import Any, List, Optional, Tuple
from google import genai

from model_config import get_claim_extract_api_key, get_claim_extract_model


def _get_client() -> genai.Client:
    return genai.Client(api_key=get_claim_extract_api_key())


# ── extract json from model output ────────────────────────────────────────────
def extract_json(text: str) -> Any:
    """Parse JSON from model output, handling fences or extra surrounding text."""
    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r"```json\s*(\{.*?\}|\[.*?\])\s*```", text, re.S)
    if m:
        return json.loads(m.group(1))

    m = re.search(r"(\[.*\])", text, re.S)
    if m:
        return json.loads(m.group(1))

    m = re.search(r"(\{.*\})", text, re.S)
    if m:
        return json.loads(m.group(1))

    raise ValueError("Could not parse JSON from model output:\n" + text)


# ── Data Model ───────────────────────────────────────────────────────────────
@dataclass
class ClaimSearchTask:
    """一条 claim 对应的完整搜索任务，可直接传给 tavily_search。"""

    raw_text: str
    claim: str
    query: str
    today_date: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


# ── Core Logic ───────────────────────────────────────────────────────────────
def build_search_tasks(
    raw_text: str, model_name: Optional[str] = None
) -> Tuple[List[ClaimSearchTask], str, str]:
    """
    一次模型调用完成：claim 提取 + 英文 query 生成 + 时间区间解析。
    返回 (ClaimSearchTask 列表, 模块一 prompt 全文, 模块一模型原始输出全文)。

    model_name: 覆盖用模型 id；默认读环境变量 CLAIM_EXTRACT_MODEL（见 model_config）。
    """
    today_str = date.today().isoformat()

    prompt = f"""
You are a fact-checking assistant. Given a piece of text and today's date:
1. Extract each verifiable factual claim.
2. Generate a short search-engine-friendly ENGLISH query for it.

Claim rules:
- Each claim must be about ONE distinct event or fact. If the text mentions TWO separate topics, they MUST be TWO separate claims.
- Only merge when facts describe the SAME event (e.g., "X dropped to 0.87" + "0.87 is a historic low" → one claim).
- Do NOT include opinions, emotions, insults, or advice.
- Preserve uncertainty markers (e.g., "reportedly", "rumored", "may", "heard that").

Query rules:
- Expand abbreviations (e.g., CPF → Central Provident Fund).
- Include key entities if implied (country/city/organization).
- Do NOT include filler words like "rumors", "issues", "policy changes".

Time rules:
- If a time reference exists, resolve it to start_date and end_date (YYYY-MM-DD) using today's date: {today_str}.
  "yesterday"      → start_date = day before today, end_date = today
  "this week"      → start_date = Monday of this week, end_date = Sunday of this week
  "last week"      → start_date = Monday of last week, end_date = Sunday of last week
  specific date    → start_date = that date - 3 days, end_date = that date + 3 days
- If no time reference, set both to null.

Output MUST be valid JSON ONLY (no markdown, no extra text).

JSON format (array with one or more objects):
[
  {{
    "claim": "...",
    "query": "...",
    "start_date": "YYYY-MM-DD or null",
    "end_date": "YYYY-MM-DD or null"
  }},
  {{
    "claim": "...",
    "query": "...",
    "start_date": "YYYY-MM-DD or null",
    "end_date": "YYYY-MM-DD or null"
  }}
]

Today's date: 
{today_str}
Text:
{raw_text}
""".strip()

    model = (model_name or "").strip() or get_claim_extract_model()
    client = _get_client()
    resp = client.models.generate_content(model=model, contents=prompt)
    module1_response_text = getattr(resp, "text", None) or ""
    data = extract_json(module1_response_text)

    tasks: List[ClaimSearchTask] = []
    for item in data:
        claim = (item.get("claim") or "").strip()
        query = (item.get("query") or "").strip()
        if not claim or not query:
            continue
        tasks.append(
            ClaimSearchTask(
                raw_text=raw_text,
                claim=claim,
                query=query,
                today_date=today_str,
                start_date=item.get("start_date"),
                end_date=item.get("end_date"),
            )
        )
    return tasks, prompt, module1_response_text


# ── Test Entry Point ──────────────────────────────────────────────────────────────
def main():
    raw_text = "Heard that Singapore will have a lockdown yesterday, and CPF withdrawals are not possible. "
    tasks, _, _ = build_search_tasks(raw_text)
    for t in tasks:
        print(json.dumps(asdict(t), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
