# 新加坡语境新闻事实核查流水线（CI）

面向**短文本 / 传闻类新闻**的多阶段流水线：用大模型抽取可核查的 claim 与检索 query，在**新加坡白名单域名**内做网络检索，并结合本地**向量知识库**证据，逐条判别真伪，最后聚合为新闻级结论。支持将完整 prompt、模型原始输出与证据写入 **SQLite** 或导出 **CSV**，便于审计与复现。

## 流水线概览

| 阶段 | 说明 |
|------|------|
| **模块一** | Gemini：从原文提取 claim、生成英文 Tavily 查询、解析时间区间 |
| **模块二** | **Tavily**：白名单域名内检索（结果经 score 阈值过滤）；**Chroma + Gemini Embedding**：按 claim 语义检索并展开 chunk |
| **模块三** | Gemini：综合两路证据，输出 `Supported` / `Refuted` / `Not Enough Evidence` 及理由与引用 |
| **聚合** | 多条 claim 时：含 Refuted → 新闻为 Refuted；否则含 NEE → NEE；否则 Supported |

终端打印的 JSON 会省略过长的 `module1_prompt`、`module1_response_text`、`module3_prompt`、`module3_response_text`；**落库与批量 CSV 保留全文**。

## 环境要求

- Python **3.10+**（开发环境曾用 3.13）
- 有效 API：**Google Gemini**（claim 提取、判别、向量嵌入）、**Tavily**（搜索）

## 安装

```bash
cd NTU/CI   # 或你克隆后的项目根目录
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 环境变量

| 变量 | 用途 |
|------|------|
| `CLAIM_EXTRACT_API_KEY` | 模块一 Gemini |
| `JUDGE_API_KEY` | 模块三 Gemini |
| `EMBEDDING_API_KEY` | 向量嵌入（与向量库读写） |
| `TAVILY_API_KEY` | Tavily 搜索 |
| `CLAIM_EXTRACT_MODEL` / `CLAIM_JUDGE_MODEL` / `EMBEDDING_MODEL` | 可选，覆盖默认模型 ID（见 `model_config.py`） |
| `FACTCHECK_DB_PATH` | 可选，SQLite 路径；默认项目目录下 `factcheck_results.db` |
| `CHROMA_PERSIST_DIR` | 可选，Chroma 持久化目录；默认项目目录下 `chroma_db` |

交互式脚本会在运行时提示输入各阶段 **API Key**

示例（一次性导出）：

```bash
export TAVILY_API_KEY="你的密钥"
export CLAIM_EXTRACT_API_KEY="..."
export JUDGE_API_KEY="..."
export EMBEDDING_API_KEY="..."
```

## 常用命令

### 单条联调（交互输入 Key + 可选命令行原文）

```bash
python test_pipeline.py
python test_pipeline.py "听说新加坡昨天要封城了"
```

运行结束会将结果写入 SQLite（若 `persist_pipeline_result` 已启用，见 `test_pipeline.py` 的 `main`）。

### 批量：输入 CSV → 输出 CSV

1. 准备输入文件，至少一列 **`raw_text`**（可参考仓库内 `batch_input_raw_texts.csv` 格式）。
2. 在 `batch_run_pipeline_to_csv.py` 顶部按需修改 `INPUT_CSV_PATH` / `OUTPUT_CSV_PATH`（默认已指向本目录下文件名）。
3. 执行：

```bash
python batch_run_pipeline_to_csv.py
```

输出列包含：新闻与 claim 维度字段、证据 JSON、`module1_prompt`、`module1_response_text`、`module3_prompt`、`module3_response_text` 等。

### 向量库：从 CSV 写入 Chroma

CSV 列：`source_id,title,content,source_type,url,published_at`（`source_id` 与 `content` 必填）。默认读取同目录 `sample_vector_docs.csv`。

```bash
python ingest_vector_data.py
```

## 项目结构（文件一览）

下表列出本目录下与流水线相关的主要文件。

| 文件 | 阶段 | 说明 |
|------|------|------|
| `gemini_for_claim.py` | **模块一** | `build_search_tasks`：一次 Gemini 调用抽取 claim、英文 query、时间区间；返回 prompt 与模型原始输出。 |
| `req_tavily.py` | **模块二** | `tavily_search`：新加坡白名单域名内 Tavily 检索；`TAVILY_API_KEY` 从环境变量读取。 |
| `vector_store.py` | **模块二** | `ChromaEvidenceStore`：持久化 Chroma 集合、Gemini Embedding 写入与查询、`search_and_expand` 按 claim 召回并展开 chunk。 |
| `ingest_vector_data.py` | **模块二（离线）** | 从 CSV 批量写入向量库（与在线流水线共用同一套 `vector_store`）；非每条新闻必经，用于构建/更新知识库。 |
| `test_pipeline.py` | **编排 + 入口** | `run_pipeline`：调用模块一 → 模块二两路检索 → 模块三判别 → `aggregate_news_label`；内含 Tavily/向量证据的 score、distance 过滤；`print_results`、`main` 联调与 SQLite 写入。 |
| `batch_run_pipeline_to_csv.py` | **编排 + 入口** | 批量读入 `raw_text` CSV，调用 `run_pipeline`，展平为多行写入结果 CSV。 |
| `claim_judge.py` | **模块三** | `build_judge_prompt`、`judge_claim`：构造判别 prompt、调用 Gemini、解析 JSON 标签/理由/引用；返回 `module3_prompt` 与 `module3_response_text`。 |
| `result_store.py` | **持久化** | SQLite：`news_run` / `claim_result` 表、`init_db` 迁移、`persist_pipeline_result`（含各模块 prompt 与模型原文、证据 JSON）。 |
| `model_config.py` | **配置** | 各阶段默认模型 ID 与环境变量读取（`CLAIM_EXTRACT_*`、`JUDGE_*`、`EMBEDDING_*`），供模块一/二/三共用。 |
| `runtime_config.py` | **配置** | `setup_pipeline_runtime_interactive` / `setup_ingest_runtime_interactive`：终端交互输入 Key 与模型名（含 Tavily）。 |
| `requirements.txt` | **依赖** | Python 包：`google-genai`、`tavily-python`、`chromadb` 等。 |
| `README.md` | **文档** | 本说明。 |
| `batch_input_raw_texts.csv` | **数据样例** | 批量流水线输入示例（至少含 `raw_text` 列）。 |
| `sample_vector_docs.csv` | **数据样例** | `ingest_vector_data.py` 默认示例，字段见上文「向量库」小节。 |


## 许可证

若用于课程或研究，请按所在院系要求补充许可证声明；当前目录未默认附带开源许可证文件。

---
