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
| `TAVILY_API_KEY` | Tavily 搜索（**必填**，勿写入代码仓库） |
| `CLAIM_EXTRACT_MODEL` / `CLAIM_JUDGE_MODEL` / `EMBEDDING_MODEL` | 可选，覆盖默认模型 ID（见 `model_config.py`） |
| `FACTCHECK_DB_PATH` | 可选，SQLite 路径；默认项目目录下 `factcheck_results.db` |
| `CHROMA_PERSIST_DIR` | 可选，Chroma 持久化目录；默认项目目录下 `chroma_db` |

交互式脚本会在运行时提示输入各阶段 **API Key**（含 Tavily；若已导出 `TAVILY_API_KEY` 则跳过该步）。

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

## 项目结构（核心文件）

| 文件 | 作用 |
|------|------|
| `test_pipeline.py` | `run_pipeline`、证据过滤与主流程入口 |
| `gemini_for_claim.py` | 模块一：claim / query / 时间 |
| `req_tavily.py` | Tavily 白名单检索 |
| `vector_store.py` | Chroma 集合与查询 |
| `claim_judge.py` | 模块三：判别 prompt 与解析 |
| `result_store.py` | SQLite 表结构与 `persist_pipeline_result` |
| `model_config.py` | 模型名与 Key 读取 |
| `runtime_config.py` | 交互式 Key / 模型配置 |

## 安全说明

- **不要将任何 API Key 提交到 Git**。本仓库中 Tavily 仅通过环境变量 `TAVILY_API_KEY` 配置。
- 批量结果 CSV、本地 `*.db`、Chroma 目录已列入 `.gitignore`，避免误传大数据或敏感内容。

## 许可证

若用于课程或研究，请按所在院系要求补充许可证声明；当前目录未默认附带开源许可证文件。

---

**推送到 GitHub**：在 [github.com/new](https://github.com/new) 创建空仓库后，在本目录执行：

```bash
git init
git add .
git commit -m "Initial commit: Singapore-focused fact-check pipeline"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

若使用 SSH，将 `origin` URL 改为 `git@github.com:<用户名>/<仓库名>.git`。
