# invest_assistant

面向 A 股场景的投资助手项目，包含持仓管理、投资助手对话、投研数问（自然语言转 SQL）三大功能模块。

## 功能概览

- 持仓管理：持仓列表查询、批量新增/删除/修改、股票名称联想、按代码查询价格和股息率
- 投资助手：基于会话的流式对话（SSE）
- 投研数问：自然语言问题转 SQL，返回查询结果与中文总结，并支持会话管理
- 前后端分离：后端 FastAPI + SQLAlchemy，前端 React + Vite

## 目录结构

- `api/`：后端服务代码（控制器、服务、模型、AI 流程、脚本）
- `web/`：前端页面与交互（持仓数据/投资助手/投研数问）
- `scripts/`：项目级启动脚本（`start-api.sh`、`start-web.sh`）
- `docs/`：API 文档、规格文档、页面说明

## 运行环境

- Python 3.10+（建议 3.11）
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

`web` 顶部导航包含 3 个页面：

- `持仓数据`：对应持仓管理接口
- `投资助手`：对应 `/bot/*` 会话与流式聊天接口
- `投研数问`：对应 `/sql-copilot/*` 会话与问答接口

前端默认请求后端地址为：`http://localhost:8000/api/v1`。

## API 入口

后端统一前缀默认：`/api/v1`。主要接口分组：

- `positions`：`/positions`、`/positions/add`、`/positions/delete`、`/positions/modify`
- `bot`：`/bot/sessions/list`、`/bot/sessions/history`、`/bot/sessions/delete`、`/bot/chat`
- `sql-copilot`：`/sql-copilot/chat`、`/sql-copilot/query-scope`、`/sql-copilot/sessions/*`

## 文档索引

- `docs/api/positions-api.md`：持仓接口文档
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
