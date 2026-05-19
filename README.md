# invest_assistant

面向 A 股场景的投资助手项目，包含持仓管理、透视盈余、投资助手对话、投研数问、定时任务（Celery Beat）等功能模块；**账户认证**（JWT access + PostgreSQL refresh、`access_token` 版本作废旧令牌）与持仓等受保护接口已接入。

## 功能概览

- **账户认证**：注册 / 登录 / 刷新 / 登出 / 当前用户（`POST|GET /auth/*`）；JWT 内含 `ver` 与库表 `access_token_version` 对齐，**刷新或登出后旧 access 作废**（详见 `docs/api/auth-api.md`）
- **持仓管理**：持仓列表查询、批量新增/删除/修改、股票名称联想、按代码查询价格与股息率（数据来自 `stock_basic_info`）；**接口需登录**（Bearer）
- **透视盈余**：按当前持仓关联估值快照与年报，并提供按市值加权的组合透视指标（`GET /earnings-lens`，见 `docs/api/earnings-lens-api.md`）
- **投资助手**：基于会话的流式对话（SSE）；会话列表按创建时间排序；支持修改会话标题、侧栏删除确认；助手气泡内 Markdown 压缩多余空行
- **投研数问**：自然语言问题转 SQL，返回查询结果与中文总结，并支持会话管理
- **定时任务**：Web 页面配置 cron、选择 Celery 任务名；Beat 从 PostgreSQL 加载调度，Worker 异步执行（含按持仓批量更新 `stock_basic_info`）
- **前后端分离**：后端 FastAPI + SQLAlchemy + Celery，前端 React + Vite；前端在受保护接口 **401** 时 **全屏展示登录**（非顶栏「账户」入口）

## 目录结构

| 路径 | 说明 |
|------|------|
| `api/` | 后端：控制器、服务、模型、AI、Celery 任务、`core/akshare` 数据更新 |
| `web/` | 前端：持仓 / 透视盈余 / 投资助手 / 投研数问 / 定时任务 |
| `scripts/` | 项目级启动脚本（`start-api.sh`、`start-web.sh`） |
| `docs/` | API 与页面说明文档（含 `docs/api/auth-api.md`） |

## 运行环境

- Python 3.11+（建议 3.12）
- Node.js 18+（建议 LTS）
- PostgreSQL
- Redis（启用定时任务 / Celery 时需要，可与业务缓存共用实例、不同 DB）

## 快速启动

### 1) 后端依赖（`api/`）

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
```

### 2) 前端依赖（`web/`）

```bash
cd web
npm install
```

### 3) 配置 `api/.env`

复制并填写密钥与数据库；**认证**须配置 `JWT_SECRET_KEY`（见下表）。若使用定时任务，需配置 Redis 与 Celery，例如：

```env
CELERY_BROKER_URL=redis://:密码@localhost:6379/1
CELERY_BACKEND=redis
CELERY_LOG_TZ=Asia/Shanghai
# 可选：额外加载任务模块（tasks.scheduler、tasks.stock 会自动合并）
CELERY_IMPORTS=tasks.sample
```

### 4) 数据库表（按需执行）

**业务表（持仓等）**：API 启动时会 `create_all` 并种子持仓（表为空时）。

**账户与 refresh 表（登录注册）**：不依赖启动时自动补全列，**PostgreSQL 上请执行一次**（可重复执行，含 `accounts.access_token_version` 升级）：

```bash
cd api
python3 scripts/create_account_tables.py
```

若升级代码后出现 `column accounts.access_token_version does not exist`，重新执行上述脚本即可。

**联调命令**：`api/scripts/test_auth_flow_curl.txt`（curl 全流程，响应 JSON 默认写入 `api/tmp/`）。

**nanobot（投资助手 PG 存储）**：不随启动自动建表，需手动执行：

```bash
cd api
python3 scripts/create_nanobot_tables.py
```

涉及 `nanobot_session`、`nanobot_session_message`、`nanobot_cron_job`、`nanobot_memory_*` 等 7 张表。

**定时任务配置表**：

```bash
cd api
python3 scripts/create_scheduled_tasks_tables.py
```

创建 `scheduled_task`、`scheduled_task_run`。

**股票快照 / 财报表**（透视盈余、AkShare 更新依赖）：

```bash
cd api
python3 scripts/create_stock_basic_info_table.py
python3 scripts/create_stock_financial_report_table.py
```

### 5) 启动后端

仓库根目录：

```bash
./scripts/start-api.sh
```

- 地址：`http://127.0.0.1:8000`
- 健康检查：`GET /health`
- 调试：`DEBUG=1 ./scripts/start-api.sh`（debugpy，默认端口 5678）

### 6) 启动前端

```bash
./scripts/start-web.sh
```

- 地址：`http://localhost:5173`
- 默认 API：`http://localhost:8000/api/v1`
- 后端 CORS 当前允许来源：`http://localhost:5173`、`http://127.0.0.1:5173`（见 `api/main.py`）

### 7) Celery Worker 与 Beat（定时任务）

在 **`api/`** 目录、已激活虚拟环境且已配置 `CELERY_BROKER_URL`：

```bash
# 终端 1：消费队列
celery -A extensions.ext_celery:celery_app worker -l info

# 终端 2：按 DB 中 cron 调度（仅需一个 Beat 进程）
celery -A extensions.ext_celery:celery_app beat -l info
```

常用排查：

```bash
# 查看 Worker 已注册任务
celery -A extensions.ext_celery:celery_app inspect registered

# 手动触发示例任务
celery -A extensions.ext_celery:celery_app call tasks.sample.ping
celery -A extensions.ext_celery:celery_app call tasks.stock.update_position_basic_info
```

本地调试 Worker 可使用 `--pool=solo`；定时链路中 `run_scheduled_task` 会再投递子任务，solo 单进程已通过 `apply` 同步执行子任务避免死锁。

## 前端页面

顶部导航共 **5** 项（无单独「账户」入口；**无权限时自动全屏登录**）：

| 页面 | 说明 |
|------|------|
| 持仓数据 | `positions` 增删改查、联想、价格股息（**需 Bearer**） |
| 透视盈余 | `GET /earnings-lens` |
| 投资助手 | `/bot/*` 会话与流式聊天（`docs/api/bot--api.md`） |
| 投研数问 | `/sql-copilot/*` |
| 定时任务 | `/scheduled-tasks/*`：配置 cron、`task_key`、查看 Beat 调度与执行历史 |

## API 入口

统一前缀默认：`/api/v1`。

| 分组 | 主要路径 |
|------|----------|
| `auth` | `POST /auth/register`、`/auth/login`、`/auth/refresh`、`/auth/logout`、`GET /auth/me`（见 `docs/api/auth-api.md`） |
| `positions` | `GET /positions`、`POST /positions/add|delete|modify`、`GET .../stock-name-suggest`、`GET .../price-dividend`（**整组需登录**） |
| `earnings-lens` | `GET /earnings-lens` |
| `bot` | `/bot/sessions/*`、`POST /bot/chat` |
| `sql-copilot` | `/sql-copilot/chat`、`/sql-copilot/sessions/*` |
| `scheduled-tasks` | `GET /scheduled-tasks`、`POST .../add|modify`、`GET .../task-keys`、`GET .../beat-schedule` |

## Celery 定时任务说明

### 调度链路

1. **Beat** 使用 `DatabaseBeatScheduler`（`core/scheduled_celery.py`），从 `scheduled_task` 表读取已启用任务；每次 tick 刷新 DB 配置（改 cron 后无需重启 Beat，最长约 `maxinterval` 默认 5 分钟内生效）。
2. 到点投递 **`tasks.scheduler.run_scheduled_task`**，参数为 DB 行 `id`。
3. **Worker** 执行后按行的 **`task_key`** 调用具体业务任务（如更新持仓快照）。

### Cron 表达式

5 段格式：**分 时 日 月 周**（与 Linux cron 一致），时区为 `CELERY_LOG_TZ`（默认 `Asia/Shanghai`）。

| 示例 | 含义 |
|------|------|
| `35 8 * * *` | 每天 08:35 |
| `*/8 * * * *` | 每 8 分钟 |
| `* * * * *` | 每分钟（仅建议测试） |

注意：顺序是「分 时」，`20 8` 表示 08:20，不是 20:08。

### 内置业务任务（`api/tasks/`）

| task_key | 说明 |
|----------|------|
| `tasks.sample.ping` | 连通性测试 |
| `tasks.sample.echo` | 回显字符串 |
| `tasks.stock.update_position_basic_info` | 读取 `positions` 持仓代码，调用 AkShare 更新 `stock_basic_info` |
| `tasks.scheduler.run_scheduled_task` | Beat 内部入口，勿在页面配置为业务任务 |

新增任务：在 `api/tasks/` 下用 `@shared_task(name="...")` 声明；页面「任务名」下拉通过 `GET /scheduled-tasks/task-keys` 扫描获得。若需 Worker 加载自定义模块，可设置 `CELERY_IMPORTS`（`tasks.scheduler`、`tasks.stock` 已默认合并）。

### 命令行更新单股 / 持仓快照（AkShare）

```bash
cd api
# 单股基础快照
python -m core.akshare.update_stock_tables 600519 --target basic
# 持仓表内所有代码批量更新（与 Celery 任务逻辑相同）
python -c "from core.akshare.update_stock_tables import update_position_stocks_basic_info; print(update_position_stocks_basic_info())"
```

## Bot 存储说明

投资助手已从 workspace 文件迁移到 PostgreSQL：

- 会话：`nanobot_session` + `nanobot_session_message`
- 定时：`nanobot_cron_job`（与 Celery `scheduled_task` 为两套机制）
- 记忆：`nanobot_memory_*`

当前 `/bot/*` 默认 `user_id=default_user`。

## 环境变量（`api/.env`）

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` / `DASHSCOPE_API_KEY` | LLM 必填 |
| `JWT_SECRET_KEY` | **认证必填**，HS256 签名密钥（勿提交仓库） |
| `JWT_ALGORITHM` | 默认 `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | access JWT 过期分钟数，默认 `60` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | refresh 存储有效天数，默认 `14` |
| `OPENAI_MODEL`、`OPENAI_BASE_URL`、`DASHSCOPE_BASE_URL` | 模型与端点 |
| `API_PREFIX` | 默认 `/api/v1` |
| `DATABASE_URL` 或 `DB_*` | PostgreSQL |
| `CELERY_BROKER_URL` | 设置后启用 Celery；未设置则 API 不初始化 broker |
| `CELERY_RESULT_BACKEND` | 默认同 broker |
| `CELERY_LOG_TZ` | Beat cron 时区，默认 `Asia/Shanghai` |
| `CELERY_IMPORTS` | 逗号分隔任务模块，如 `tasks.sample` |
| `REDIS_*` | 业务 Redis（可选，与 Celery 可同实例不同 DB） |

## 文档索引

- `docs/api/auth-api.md` — 认证（注册 / 登录 / 令牌 / 运维与升级说明）
- `docs/api/positions-api.md` — 持仓（含鉴权说明）
- `docs/api/earnings-lens-api.md` — 透视盈余
- `docs/api/bot--api.md` — 投资助手
- `docs/api/sql-copilot-api.md` — 投研数问
- `docs/web/投研数问.md` — 投研数问前端
- `前端.spec.md`、`后端接口文档.md` — 补充说明

## 远程仓库

`https://github.com/songhaowei666/invest_assistant.git`

```bash
git remote add origin https://github.com/songhaowei666/invest_assistant.git   # 首次
git push -u origin main
```

请勿提交 `api/.env` 等敏感文件（根目录 `.gitignore` 已忽略）。
