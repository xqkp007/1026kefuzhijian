# 智能体输出稳定性评测工具 - 前端

基于 React + TypeScript + Ant Design 的智能体评测平台前端应用。

## 技术栈

- **框架**: Vite 5 + React 18 + TypeScript 5
- **UI 组件库**: Ant Design 5.x
- **路由管理**: React Router v6
- **HTTP 客户端**: Axios
- **Mock API**: MSW (Mock Service Worker)
- **日期处理**: Day.js

## 项目结构

```
src/
├── api/              # API 调用层
│   ├── client.ts     # Axios 配置
│   └── tasks.ts      # 任务相关 API
├── types/            # TypeScript 类型定义
│   └── index.ts      # 数据模型定义
├── pages/            # 页面组件
│   ├── CreateTask/   # 创建任务页
│   ├── TaskList/     # 任务列表页
│   └── TaskResults/  # 结果详情页
├── mocks/            # MSW Mock 配置
│   ├── handlers.ts   # API Mock handlers
│   └── browser.ts    # MSW 浏览器配置
├── App.tsx           # 根组件
├── main.tsx          # 入口文件
└── router.tsx        # 路由配置
```

## 快速开始

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

应用将运行在 http://localhost:5173/

### 构建生产版本

```bash
npm run build
```

构建产物将生成在 `dist/` 目录。

### 预览生产构建

```bash
npm run preview
```

## 功能特性

### 1. 创建评测任务 (`/`)

- 填写任务名称、智能体 API URL
- 上传测试数据集（CSV/Excel）
- 前端验证：文件大小 ≤ 5MB，格式限制
- 成功后跳转到任务列表

### 2. 任务列表 (`/tasks`)

- 显示所有评测任务
- 状态标签：等待中、运行中、已完成、失败
- 进度显示（FAILED 状态用红色显示实际进度）
- 刷新按钮
- 仅已完成任务可查看结果
- 分页支持

### 3. 结果详情 (`/tasks/:taskId/results`)

- 显示每个问题的 5 次运行结果
- 超长文本自动折叠（支持展开）
- 错误状态特殊显示
- 分页支持
- 导出 CSV 功能

## 环境配置

### 开发环境

创建 `.env.development` 文件：

```env
VITE_API_BASE_URL=http://localhost:8000/api
VITE_ENABLE_MSW=false
```

### 生产环境

创建 `.env.production` 文件：

```env
VITE_API_BASE_URL=https://your-backend-domain/api
VITE_ENABLE_MSW=false
```

> `VITE_ENABLE_MSW` 用于切换是否启用 MSW Mock，设为 `false` 时将直接请求真实后端服务。

## 一键启动脚本

仓库根目录提供 `./start_all.sh`，自动依次启动后端（FastAPI + Celery）与前端（Vite Dev Server）。运行前确保：
- 后端已创建 `.venv` 并安装依赖，数据库迁移已执行；
- 前端完成 `npm install`；
- 本地已安装 Redis、PostgreSQL 并运行。

使用方式：

```bash
./start_all.sh
```

按 `Ctrl+C` 会同时停止前后端进程。

## Mock API

开发环境使用 MSW 模拟后端 API。Mock 配置位于 `src/mocks/handlers.ts`。

包含以下模拟接口：
- `POST /api/v1/evaluation-tasks` - 创建任务
- `GET /api/v1/evaluation-tasks` - 获取任务列表
- `GET /api/v1/evaluation-tasks/:taskId/results` - 获取结果
- `GET /api/v1/evaluation-tasks/:taskId/export` - 导出 CSV

## API 接口说明

### 创建任务

```typescript
POST /api/v1/evaluation-tasks
Content-Type: multipart/form-data

{
  task_name: string;
  agent_api_url: string;
  dataset_file: File;
}

Response: {
  task_id: string;
  status: 'PENDING';
}
```

### 获取任务列表

```typescript
GET /api/v1/evaluation-tasks?page=1&page_size=20

Response: {
  items: EvaluationTask[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
  };
}
```

### 获取任务结果

```typescript
GET /api/v1/evaluation-tasks/:taskId/results?page=1&page_size=20

Response: {
  task: TaskDetails;
  items: EvaluationItem[];
  pagination: Pagination;
}
```

### 导出 CSV

```typescript
GET /api/v1/evaluation-tasks/:taskId/export

Response: CSV file (text/csv)
```

## 代码规范

项目使用 ESLint + TypeScript 进行代码检查：

```bash
npm run lint
```

## 浏览器兼容性

支持所有现代浏览器（Chrome、Firefox、Safari、Edge）。

## 许可证

MIT
