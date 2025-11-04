# 部署指南（交付给同事）

面向部署同学的一站式指引，覆盖环境准备、配置、启动方式、反向代理、验收与排障。默认场景：单台 Linux 服务器（Ubuntu 22.04），Nginx 反向代理，systemd 管理进程，PostgreSQL + Redis 本机或内网服务。

如有不同（K8s/Docker、外部DB/Redis、无域名等），按文末“差异化部署说明”调整。

—

## 1. 总览
- 后端：FastAPI + Celery + SQLAlchemy（端口 `8000`），路由前缀 `/api/v1`。
- 前端：Vite + React 构建静态资源（默认端口 `5173` 仅开发期使用，生产用 Nginx 托管 `dist/`）。
- 依赖：PostgreSQL 15、Redis 7。
- 一键本地开发：`./start_all.sh`（仅开发联调；生产请用 Nginx + systemd）。

关键路径：
- 后端入口 `backend/app/main.py`，健康检查 `GET /healthz`（不带 `/api` 前缀）。
- 业务路由挂载在 `/api/v1`，前端以 `VITE_API_BASE_URL` 拼接 `/v1/...` 进行访问。

—

## 2. 先决条件
- OS：Ubuntu 22.04（或兼容 Linux）。
- Python：3.11。
- Node.js：v18 或 v20 LTS，附 npm。
- 数据库：PostgreSQL 15（可用连接串）。
- Redis：7.x（可用连接串）。
- 端口/域名：准备后端域名（如 `app.example.com`）或服务器IP，开放 80/443（Nginx），8000（内网即可）。
- 证书：生产环境建议启用 HTTPS（Let’s Encrypt）。

—

## 3. 代码获取与目录
```
repo/
├─ backend/            # FastAPI + Celery
├─ frontend/           # Vite + React（构建后静态资源）
└─ start_all.sh        # 一键开发启动脚本（开发期使用）
```

—

## 4. 数据库与 Redis 准备
1) PostgreSQL 创建数据库与用户（示例）：
```
sudo -u postgres psql
CREATE DATABASE agent_eval;
CREATE USER agent_user WITH PASSWORD 'StrongPassword123!';
GRANT ALL PRIVILEGES ON DATABASE agent_eval TO agent_user;
```
2) Redis 7 启动并确保可连接。

—

## 5. 后端部署（FastAPI + Celery）

5.1 安装依赖与虚拟环境
```
cd backend
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

5.2 环境变量
```
cp .env.example .env
```
按需修改 `.env`（默认键见 `backend/.env.example`）：
- `DATABASE_URL=postgresql+psycopg2://agent_user:StrongPassword123!@127.0.0.1:5432/agent_eval`
- `REDIS_URL=redis://127.0.0.1:6379/0`
- `RUNS_PER_ITEM`、`TIMEOUT_SECONDS`、`EVALUATION_CONCURRENCY` 等按容量微调
- 如需智谱模型：`ZHIPU_API_KEY`、`ZHIPU_MODEL_ID` 等
- 上传目录：`UPLOADS_DIR=storage/uploads`（默认）

5.3 数据库迁移
```
alembic upgrade head
```

5.4 前台试运行（可用于烟测）
```
uvicorn app.main:app --host 0.0.0.0 --port 8000
celery -A app.celery_app worker --loglevel=info -Q evaluation
```

5.5 生产进程托管（systemd）
创建 `uvicorn.service`：
```
[Unit]
Description=Uvicorn API Service
After=network.target

[Service]
WorkingDirectory=/path/to/repo/backend
Environment="PYTHONPATH=/path/to/repo/backend"
ExecStart=/path/to/repo/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
User=www-data
Group=www-data

[Install]
WantedBy=multi-user.target
```

创建 `celery.service`：
```
[Unit]
Description=Celery Worker
After=network.target redis.service

[Service]
WorkingDirectory=/path/to/repo/backend
Environment="PYTHONPATH=/path/to/repo/backend"
ExecStart=/path/to/repo/backend/.venv/bin/celery -A app.celery_app worker --loglevel=info -Q evaluation --logfile=/path/to/repo/backend/logs/celery.log
Restart=always
User=www-data
Group=www-data

[Install]
WantedBy=multi-user.target
```

生效并启动：
```
sudo cp uvicorn.service /etc/systemd/system/
sudo cp celery.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable uvicorn celery
sudo systemctl start uvicorn celery
sudo systemctl status uvicorn celery
```

—

## 6. 前端部署（Vite 构建产物）

6.1 配置 API 地址
生产环境将前端的 `VITE_API_BASE_URL` 指向后端反向代理前缀（推荐 `/api`）：
```
cd frontend
cp .env.example .env.production
# 将 VITE_API_BASE_URL 设置为 /api 或 https://your-domain/api
```

6.2 构建
```
npm ci || npm install
npm run build
```
产物在 `frontend/dist/`，用 Nginx 托管。

—

## 7. Nginx 配置（前端静态 + 后端反代）

示例（根目录托管前端，`/api/` 反代后端 8000）：
```
server {
    listen 80;
    server_name app.example.com;  # 替换为真实域名或使用 _

    # 前端静态文件
    root /path/to/repo/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # 健康检查直通后端 /healthz（避免被前端路由拦截）
    location = /healthz {
        proxy_pass http://127.0.0.1:8000/healthz;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 后端 API 反向代理
    location /api/ {
        # 将 /api/* 透传给后端，同名路径（例如 /api/v1/*、/api/healthz）
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }

    # 上传文件大小（按需调大）
    client_max_body_size 10m;
}
```
启用 HTTPS 可结合 certbot/自有证书。

—

## 8. 验收与自检

8.1 健康检查
- 访问 `http://app.example.com/healthz`，期望返回 `{ "status": "ok" }`

8.2 前端连通
- 打开首页，创建任务：填写任务名、Agent API URL（或使用 zhipu 通道）、上传数据集 → 任务列表应出现新任务
- 列表轮询应呈现进度，完成后可进入结果页，支持导出 CSV

8.3 日志检查
- 后端日志：`backend/logs/celery.log`（Celery 执行与第三方调用）
- Nginx 访问/错误日志：`/var/log/nginx/` 下对应文件

—

## 9. 常见问题（Troubleshooting）
- 无法连接数据库：检查 `DATABASE_URL`、安全组/防火墙、数据库白名单、迁移是否执行。
- 任务卡住/不消费：确认 `celery.service` 正常、`REDIS_URL` 可用、队列名包含 `evaluation`。
- 前端 404 刷新：确保 Nginx 使用 `try_files ... /index.html;`（前端路由）。
- 跨域报错：生产应走同域 `/api/` 反代；若直连 IP/端口，需在后端开放 CORS（当前已允许 `*`）。
- 导入文件受限：适配 `client_max_body_size`，同时后端限制 `MAX_DATASET_FILE_SIZE_MB` 默认为 5MB。
- 代理导致 Celery 报 `socksio`：生产不应为 worker 设置全局代理；或参照根脚本 `start_all.sh` 的代理屏蔽逻辑。

—

## 10. 运行与维护
- 启停服务：`sudo systemctl start|stop|restart uvicorn celery`
- 查看状态：`sudo systemctl status uvicorn celery`
- 打包升级：更新代码 → 进入 `backend` 重新 `pip install -e .`（如依赖变更）→ `alembic upgrade head` → 重启服务

—

## 11. 差异化部署说明（按需调整）
- 无域名/仅内网：Nginx `server_name _;`，以 `http://<server-ip>` 访问。
- 数据库/Redis 托管：替换 `DATABASE_URL`/`REDIS_URL` 为云服务地址。
- 单机快速验证：可用 `./start_all.sh` 一键拉起（开发模式），确认功能后再切换到 Nginx + systemd。
- 性能调优：提高 `EVALUATION_CONCURRENCY`、按 CPU 数设定 Celery 并发；必要时将 DB/Redis 独立实例化。

—

## 12. 交付清单（打包给部署同事）
- 本文件：`DEPLOYMENT.md`
- 配置模板：`backend/.env.example` 与示例 `.env`（不含密钥，敏感值线下传递）
- 构建说明：`frontend/README.md`、`backend/README.md`
- Nginx 与 systemd 示例：可按本文件拷贝到服务器并修改路径
- 一份可用的测试数据集（CSV/Excel），用于验收

—

## 13. 参考文件
- 根启动脚本：`start_all.sh`
- 后端说明：`backend/README.md`
- 前端说明：`frontend/README.md`
- 后端入口与健康检查：`backend/app/main.py`
