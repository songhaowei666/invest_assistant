# invest_assistant

攒股收息相关的投资助手项目：服务端为 FastAPI（持仓、AI 修改提案等），前端为 React + Vite。

## 目录结构

- `api/`：Python 服务（FastAPI、SQLAlchemy、SQLite 默认）；路由在 `api/controllers/`（按版本分子目录，如 `v1/`）
- `web/`：React 前端（Vite 开发服务器默认 `http://localhost:5173`）

## 环境要求

- Python 3.10+（建议 3.11）
- Node.js 18+（建议 LTS）

## 服务端（api）

### 依赖安装

在 `api` 目录下建议使用虚拟环境：

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
```

### 环境变量（可选）

在 `api/.env` 中可配置，例如：

- `OPENAI_API_KEY`：调用大模型时使用
- `DATABASE_URL`：默认 `sqlite:///./invest_assistant.db`
- `API_PREFIX`：默认 `/api/v1`

### 启动

从仓库根目录执行：

```bash
./scripts/start-api.sh
```

或手动：

```bash
cd api
source .venv/bin/activate   # 若已创建虚拟环境
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

启动后接口根路径为 `http://127.0.0.1:8000`，健康检查：`GET http://127.0.0.1:8000/health`。

## 前端（web）

### 依赖安装

```bash
cd web
npm install
```

### 启动

从仓库根目录执行：

```bash
./scripts/start-web.sh
```

或手动：

```bash
cd web
npm run dev
```

默认开发地址：`http://localhost:5173`（与服务端 CORS 配置一致）。

## 同时开发

先启动服务端，再启动 Web；两个终端分别运行 `./scripts/start-api.sh` 与 `./scripts/start-web.sh` 即可。

## 其他文档

- `前端.spec.md`：前端原型需求说明
- `后端接口文档.md`：HTTP 接口说明（若存在）
