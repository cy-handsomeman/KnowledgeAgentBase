# 企业文档知识库系统（KnowledgeAgentBase）

面向企业员工的文档知识管理 Web 应用：按群组管理共享知识库，同时支持个人知识库，并提供基于检索增强生成（RAG）的智能问答，回答会附带真实来源（文档名、页码、片段）。

技术栈：FastAPI + MySQL + SQLAlchemy + Alembic + Chroma + BGE 中文向量模型 + DeepSeek（OpenAI 兼容接口）+ 原生 HTML/CSS/JS。

---

## 一、功能范围

- **企业知识库**：按群组组织，群组内角色分 `member`（查看/搜索）、`editor`（+文档增删改）、`admin`（+成员管理）。
- **个人知识库**：仅所有者可见。
- **文档管理**：在线创建/编辑 Markdown、上传 PDF/TXT（≤10MB）、自动解析、分块、向量化；PDF 支持页内预览与下载。
- **智能问答**：多轮会话（历史随会话保存，追问可理解上下文）、检索增强生成、Markdown 渲染、可点击的 `[n]` 引用角标与来源片段展开。
- **管理能力**：新建群组/知识库、管理员添加成员/改角色/移除成员、个人知识库自助创建。
- **权限控制**：全部在后端校验，前端按钮显隐只影响体验。

---

## 二、环境要求

| 组件 | 版本要求 | 说明 |
| --- | --- | --- |
| Windows | 10/11 | 本项目在 Windows + PowerShell 下开发 |
| Python | 3.12 | 使用 `py` 启动器 |
| MySQL Server | 8.0+ | 需要本机服务，Navicat 只是客户端 |
| Git | 任意较新版本 | 版本管理 |

---

## 三、从零启动步骤

### 1. 打开项目目录

```powershell
Set-Location 'D:\1mywork\AgentSpace'
Get-Location
```

预期输出 `D:\1mywork\AgentSpace`。

用 VS Code 打开：

```powershell
code .
```

或 VS Code → 文件 → 打开文件夹 → 选择该目录。

### 2. 创建并激活虚拟环境

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

如果提示“禁止运行脚本”：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

激活成功后提示符前会出现 `(.venv)`。

在 VS Code 中按 `Ctrl+Shift+P` → `Python: Select Interpreter` → 选择：

```text
D:\1mywork\AgentSpace\.venv\Scripts\python.exe
```

### 3. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

首次安装会下载 PyTorch、Chroma、PyMuPDF 等较大依赖，请耐心等待。

### 4. 创建数据库

用 Navicat 连接本机 MySQL（主机 `127.0.0.1`，端口 `3306`），新建查询执行：

```sql
CREATE DATABASE enterprise_kb
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

也可以在 PowerShell 里用 Python 创建（把账号密码换成自己的）：

```powershell
python -c "import pymysql; c=pymysql.connect(host='127.0.0.1',port=3306,user='root',password='你的密码'); cur=c.cursor(); cur.execute('CREATE DATABASE IF NOT EXISTS enterprise_kb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'); c.commit(); c.close(); print('ok')"
```

### 5. 配置 `.env`

复制模板：

```powershell
Copy-Item .env.example .env
```

打开 `.env` 填写：

```text
DATABASE_URL=mysql+pymysql://root:你的密码@127.0.0.1:3306/enterprise_kb
UPLOAD_DIR=D:/1mywork/AgentSpace/storage/uploads
CHROMA_DIR=D:/1mywork/AgentSpace/storage/chroma
LLM_API_KEY=你的 DeepSeek API Key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
JWT_SECRET_KEY=用 python -c "import secrets; print(secrets.token_hex(32))" 生成
JWT_EXPIRE_MINUTES=120
```

说明：

- `.env` 已被 `.gitignore` 忽略，**不会上传 GitHub**；
- `LLM_API_KEY` 未填写时，检索功能正常，点击“生成回答”会提示未配置 Key；
- 首次使用向量模型会从 HuggingFace 下载约 100MB 权重，之后走本机缓存。

### 6. 执行数据库迁移

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

验证：

```powershell
.\.venv\Scripts\python.exe -m alembic current
```

应显示当前版本号（`81740e486989`）。

以后修改了模型文件，新增迁移：

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "说明本次变更"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### 7. 准备演示数据（可选但推荐）

```powershell
.\.venv\Scripts\python.exe scripts\seed_demo.py
```

脚本可重复执行，会创建：

| 账号 | 密码 | 群组与角色 |
| --- | --- | --- |
| `alice` | `Passw0rd!` | 研发部（管理员） |
| `bob` | `Passw0rd!` | 研发部（成员）、人力资源部（管理员） |

以及研发部知识库、人力资源部知识库、alice 的个人知识库。

### 8. 启动服务

```powershell
.\.venv\Scripts\python.exe -m fastapi dev backend/app/main.py --port 8000 --reload-dir backend
```

看到以下输出即成功：

```text
Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

> `--reload-dir backend` 只监听后端代码，避免 `.venv` 里文件变动导致频繁重启。

### 9. 打开前端

浏览器访问：

```text
http://127.0.0.1:8000/
```

用 `alice / Passw0rd!` 或 `bob / Passw0rd!` 登录。

接口文档（Swagger）：

```text
http://127.0.0.1:8000/docs
```

### 10. 运行测试

测试连接必须通过 `TEST_DATABASE_URL` 显式配置，且必须是本机 MySQL、数据库名以 `_test` 结尾。测试开始和结束都会清空该测试库的表，请使用独立且可删除的测试数据库。

```powershell
$env:TEST_DATABASE_URL = "mysql+pymysql://测试用户名:测试密码@127.0.0.1:3306/enterprise_kb_test"
.\.venv\Scripts\python.exe -m pytest -q
```

未设置安全的 `TEST_DATABASE_URL` 时测试会拒绝启动。测试库、上传目录和 Chroma 目录均应与开发数据隔离；首次运行会在指定 MySQL 实例中创建测试数据库。

---

## 四、目录结构

```text
D:\1mywork\AgentSpace
├── backend\app\
│   ├── api\            # 接口层：认证、群组、知识库、文档、检索、问答
│   ├── core\           # 配置读取、密码哈希与 JWT
│   ├── db\             # 引擎/会话、ORM 基类
│   ├── models\         # 8 张表的 SQLAlchemy 模型
│   ├── schemas\        # Pydantic 请求/响应模型
│   ├── services\       # 权限、解析、分块、索引、向量、检索、LLM、RAG
│   └── main.py         # 应用入口
├── frontend\           # 原生 HTML/CSS/JS（由 FastAPI 托管）
├── migrations\         # Alembic 迁移脚本
├── scripts\
│   ├── seed_demo.py     # 演示数据
│   └── evaluate_rag.py  # 固定问题集问答评测
├── storage\            # uploads/ 与 chroma/（均被 Git 忽略）
├── tests\              # pytest
├── alembic.ini
├── requirements.txt
└── .env.example
```

---

## 五、主要接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录，返回 JWT |
| GET | `/api/auth/me` | 当前用户 |
| GET | `/api/groups` | 我加入的群组与角色 |
| POST | `/api/groups` | 新建群组（自动成为管理员并创建默认知识库） |
| GET | `/api/groups/{id}/members` | 群组成员列表 |
| POST/PATCH/DELETE | `/api/groups/{id}/members` | 添加 / 修改角色 / 移除成员（管理员） |
| GET | `/api/users?username=` | 按用户名前缀搜索用户（添加成员用） |
| GET/POST | `/api/knowledge-bases` | 我的知识库 / 新建知识库 |
| GET/PATCH/DELETE | `/api/knowledge-bases/{id}` | 详情 / 改名 / 删除（仅空库） |
| GET/POST | `/api/knowledge-bases/{id}/documents` | 文档列表 / 新建在线文档 |
| POST | `/api/knowledge-bases/{id}/documents/upload` | 上传 PDF/TXT |
| GET/PUT/DELETE | `/api/documents/{id}` | 文档详情 / 保存 / 删除 |
| GET | `/api/documents/{id}/download` | 下载或预览原始文件（`?inline=true`） |
| POST | `/api/documents/{id}/reindex` | 重建片段与向量 |
| POST | `/api/knowledge-bases/{id}/search` | 检索片段（不生成回答） |
| POST | `/api/knowledge-bases/{id}/ask` | RAG 问答（生成回答 + 来源，支持 `session_id` 多轮） |
| POST | `/api/knowledge-bases/{id}/agent` | 受控 Agent（只读检索工具，最多 3 次调用，返回执行步骤） |
| GET | `/api/chat/sessions` | 我的会话列表 |
| GET | `/api/chat/sessions/{id}/messages` | 会话消息 |
| DELETE | `/api/chat/sessions/{id}` | 删除会话 |

除注册/登录外，所有接口都需要请求头：

```text
Authorization: Bearer <access_token>
```

---

## 六、常见错误排查

| 现象 | 原因与处理 |
| --- | --- |
| `无法连接到远程服务器` | 服务没启动。确认终端里 `Uvicorn running`，或先执行 `netstat -ano \| findstr :8000` 检查端口。 |
| 端口被占用 / 代码改了不生效 | 可能有残留的旧进程。用 `Get-CimInstance Win32_Process -Filter "Name='python.exe'"` 查看，结束占用 8000 端口的进程后重启。 |
| `ModuleNotFoundError` | 虚拟环境未激活或依赖未安装。确认提示符有 `(.venv)`，再 `pip install -r requirements.txt`。 |
| 数据库连接失败 | 检查 MySQL 服务是否启动、账号密码是否正确、`enterprise_kb` 是否已创建。 |
| `Unknown database 'enterprise_kb'` | 还没建库，执行第三步的 SQL。 |
| `Table 'xxx' doesn't exist` | 未执行迁移：`alembic upgrade head`。 |
| `alembic check` 报差异 | 有人手工改过表结构。新建迁移对齐，不要直接改正式库。 |
| 上传返回 400 | 只允许 `.pdf` / `.txt`。 |
| 上传返回 413 | 文件超过 10MB。 |
| 接口返回 429 | 触发了内置限流（登录/注册/问答/用户搜索），等待响应头 `Retry-After` 的秒数后重试。 |
| 上传后状态 `FAILED` | 文件损坏、扫描版 PDF 无文本层，或 TXT 编码无法识别；查看 `error_message`。 |
| 点击“生成回答”提示未配置 Key | 在 `.env` 填写 `LLM_API_KEY` 后重启服务。 |
| 大模型返回 401/402 | Key 无效或余额不足，检查 DeepSeek 控制台。 |
| 首次索引很慢 / 模型下载失败 | 需要下载 BGE 权重。网络受限时先设置镜像：`$env:HF_ENDPOINT="https://hf-mirror.com"` 再启动。 |
| 页面 404 但接口正常 | 静态文件挂载后需要完整重启一次服务。 |
| 测试拒绝启动 | 先设置 `TEST_DATABASE_URL`，确认它是本机 MySQL 且数据库名以 `_test` 结尾；测试会清理该库所有模型表。 |

---

## 七、安全说明

1. `.env` 保存数据库密码、JWT 密钥和大模型 Key，**永不提交**；
2. 密码只存 bcrypt 哈希（`$2b$12$...`），接口响应模型不包含 `password_hash`；
3. JWT 有效期默认 120 分钟，服务端不保存令牌，退出登录由前端删除本地令牌；
4. 所有权限判断集中在 `services/permissions.py`，接口不能绕过；
5. 上传文件名由服务端用 UUID 重新生成，防止路径穿越；删除文件时限制在上传目录内；
6. 检索结果返回前会用 MySQL 当前权限二次校验，成员被移除后旧向量不会泄露内容；
7. 内置进程内限流：注册 5 次/小时/IP、登录 10 次/分钟/IP、问答 20 次/分钟/用户、用户搜索 30 次/分钟/用户，超限返回 429。可用 `RATE_LIMIT_ENABLED=false` 关闭（测试环境已关闭）；
8. Agent 接口只允许调用服务端注册的只读知识库检索工具，每次调用重新检查当前用户权限，最多 3 次工具调用。单次模型请求最多 60 秒，整个 Agent 流程最多 150 秒。检索超过 20 秒会在执行结束后判定超时；由于本地检索同步运行，该检查不能强制中断底层模型计算。模型 HTTP 请求可由客户端超时终止。
9. **定位说明**：本项目是单机、受控的本地演示环境，没有多实例共享限流、审计日志、密钥轮换、传输加密等生产能力，请勿直接暴露到公网。

---

## 八、问答质量评测

严格引用校验（`services/rag.py`）要求模型输出有效 `[n]` 编号，否则判定为无依据。改动 Prompt 或校验规则前，先用固定问题集测量，避免凭感觉调整。

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_rag.py
```

脚本会重建独立的「RAG评测组」知识库并写入 5 篇制度文档，执行 20 道固定问题（10 可答 + 5 半答 + 5 不可答），统计：

- 可答题拒答率、关键词命中率；
- 有依据但缺编号的次数、引用越界次数；
- 不可答题被误答的次数、模型 JSON 解析失败次数、平均耗时。

明细写入 `storage/eval/rag_eval_*.json`，记录模型、生成时间、问题数、单题耗时和检索预期关键词命中代理指标。该指标不等同于人工相关性判断或通用召回率。脚本仅清理由专用评测用户 `rag_eval_bot` 创建的同名评测组及该用户数据；运行前确认 `.env` 指向可写的本地评测环境，调用模型会产生 API 费用。当前基线（deepseek-chat，20 题）：可答题 15/15 保留回答，不可答题 5/5 正确拒答，缺编号与越界均为 0。

### Agent 工具调用演示

新增接口 `POST /api/knowledge-bases/{id}/agent`，请求体为 `{"question":"差旅住宿标准是什么？","session_id":null}`。Agent 先通过只读工具 `search_knowledge_base` 检索，服务端校验工具名/参数并重新检查知识库权限，再复用现有检索逻辑；最多 3 次工具调用，最终答案复用 RAG 引用编号校验。响应包含 `steps`、`model_call_count` 和 `elapsed_seconds`。这是受控演示流程，不是生产级 Agent Runtime。

Agent 固定问题集评测使用单独的本机数据库，必须显式设置数据库名以 `_eval` 结尾的 `AGENT_EVAL_DATABASE_URL`。评测会创建缺失表、重建专用评测用户/知识库、调用真实模型并在结束后清理专用评测范围；请确认目标库可删除且已配置模型 API。报告写入 `storage/eval/agent_eval_*.json`，包含任务完成率、工具选择、调用次数、拒答、引用、权限探测、耗时及模型调用数。模型费用未从供应商账单读取，故不报告费用金额。

```powershell
$env:AGENT_EVAL_DATABASE_URL = "mysql+pymysql://评测用户名:评测密码@127.0.0.1:3306/enterprise_kb_eval"
.\.venv\Scripts\python.exe scripts\evaluate_agent.py
```
