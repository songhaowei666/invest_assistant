# invest_assistant

面向 A 股场景的投资助手项目，包含持仓管理、透视盈余、投资助手对话、投研数问（自然语言转 SQL）等功能模块。

## 功能概览

- 持仓管理：持仓列表查询、批量新增/删除/修改、股票名称联想、按代码查询价格与股息率（数据来自 `stock_basic_info`）
- 透视盈余：按当前持仓关联估值快照与年报，并提供按市值加权的组合透视指标（独立接口 `GET /earnings-lens`，见 `docs/api/earnings-lens-api.md`）
- 投资助手：基于会话的流式对话（SSE）
- 投研数问：自然语言问题转 SQL，返回查询结果与中文总结，并支持会话管理
- 前后端分离：后端 FastAPI + SQLAlchemy，前端 React + Vite

## 目录结构

- `api/`：后端服务代码（控制器、服务、模型、AI 流程、脚本）
- `web/`：前端页面与交互（持仓数据/透视盈余/投资助手/投研数问）
- `scripts/`：项目级启动脚本（`start-api.sh`、`start-web.sh`）
- `docs/`：API 文档、规格文档、页面说明

## 运行环境

- Python 3.11+（建议 3.12）
- Node.js 18+（建议 LTS）
- PostgreSQL（默认配置为 PostgreSQL 连接）

## 快速启动

### 1) 后端依赖安装（`api/`）

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
```

### 2) 前端依赖安装（`web/`）

```bash
cd web
npm install
```

### 3) 启动后端

在仓库根目录执行：

```bash
./scripts/start-api.sh
```

后端默认地址：`http://127.0.0.1:8000`  
健康检查：`GET /health`

### 3.1) 手动创建 nanobot PG 表（新增）

`nanobot_main` 的会话、定时任务、记忆存储已迁移到 PostgreSQL。  
这些新表**不走启动自动建表**，请手动执行：

```bash
cd api
python3 scripts/create_nanobot_tables.py
```

脚本会创建（或确认存在）以下 7 张表，并刷新 PostgreSQL `COMMENT ON`：

- `nanobot_session`
- `nanobot_session_message`
- `nanobot_cron_job`
- `nanobot_memory_file`
- `nanobot_memory_md`
- `nanobot_memory_history`
- `nanobot_memory_cursor`

### 4) 启动前端

在仓库根目录执行：

```bash
./scripts/start-web.sh
```

前端默认地址：`http://localhost:5173`

## 环境变量说明（`api/.env`）

后端通过 `api/configs/config.py` 读取配置，核心变量如下：

- `OPENAI_API_KEY`：必填
- `DASHSCOPE_API_KEY`：必填
- `OPENAI_MODEL`：默认 `gpt-4o-mini`
- `OPENAI_BASE_URL`：默认 `https://api.openai.com/v1`
- `DASHSCOPE_BASE_URL`：默认 `https://api.dashscope.aliyuncs.com/compatible-mode/v1`
- `API_PREFIX`：默认 `/api/v1`
- `DATABASE_URL`：可选，设置后优先使用
- `DB_TYPE`、`DB_USERNAME`、`DB_PASSWORD`、`DB_HOST`、`DB_PORT`、`DB_DATABASE`：未设置 `DATABASE_URL` 时用于拼接 PostgreSQL 连接串

说明：当前配置未设置 `DATABASE_URL` 时仅支持 `postgresql` 类型。

## 前端页面说明

`web` 顶部导航包含 4 个页面：

- `持仓数据`：对应 `positions` 下列表与增删改等接口
- `透视盈余`：对应 `GET /earnings-lens`；展示每行快照与年报摘要，以及 `mcWeighted` 市值加权组合指标（缺失市值按 0、无样本时加权为 0）
- `投资助手`：对应 `/bot/*` 会话与流式聊天接口
- `投研数问`：对应 `/sql-copilot/*` 会话与问答接口

前端默认请求后端地址为：`http://localhost:8000/api/v1`。

## API 入口

后端统一前缀默认：`/api/v1`。主要接口分组：

- `positions`：`GET /positions`、`POST /positions/add`、`POST /positions/delete`、`POST /positions/modify`、`GET /positions/stock-name-suggest`、`GET /positions/price-dividend`
- `earnings-lens`：`GET /earnings-lens`（独立控制器，详见 `docs/api/earnings-lens-api.md`）
- `bot`：`/bot/sessions/list`、`/bot/sessions/history`、`/bot/sessions/delete`、`/bot/chat`
- `sql-copilot`：`/sql-copilot/chat`、`/sql-copilot/query-scope`、`/sql-copilot/sessions/*`

## Bot 存储说明（重要更新）

当前 `bot` 对话链路已从 workspace 文件存储切换为 PostgreSQL：

- 会话：原 `api/.nanobot/sessions/*.jsonl` → `nanobot_session` + `nanobot_session_message`
- 定时任务：原 `api/.nanobot/cron/jobs.json` → `nanobot_cron_job`
- 记忆：原 `SOUL.md`/`USER.md`/`memory/MEMORY.md`/`memory/history.jsonl` → `nanobot_memory_*` 系列表

隔离策略：

- 底层存储按 `user_id` 做隔离
- 当前 `/bot/*` 入口默认使用 `default_user`（后续可平滑切换到真实登录态用户）

## 文档索引

- `docs/api/positions-api.md`：持仓接口文档
- `docs/api/earnings-lens-api.md`：透视盈余接口文档
- `docs/api/bot--api.md`：投资助手（Bot）接口文档
- `docs/api/sql-copilot-api.md`：投研数问接口文档
- `docs/web/投研数问.md`：投研数问前端页面说明
- `前端.spec.md`：前端需求说明
- `后端接口文档.md`：后端接口补充文档

## 提交到 GitHub 远程仓库

远程仓库地址：  
`https://github.com/songhaowei666/invest_assistant.git`

在仓库根目录执行：

```bash
cd /home/song/github_clone/invest_assistant
git status
git add .
git commit -m "初始化项目代码"
```

### 配置远程地址

若本地未配置 `origin`：

```bash
git remote add origin https://github.com/songhaowei666/invest_assistant.git
```

若 `origin` 已存在，更新地址：

```bash
git remote set-url origin https://github.com/songhaowei666/invest_assistant.git
```

### 首次推送

```bash
git branch -M main
git push -u origin main
```

### 常见问题

- 认证失败：请使用 GitHub Token（不是账号密码）
- 敏感文件（如 `.env`）被暂存：先确认根目录 `.gitignore` 已生效，再重新执行 `git add .`
