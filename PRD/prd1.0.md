好的，我们已经完成了所有细节的讨论和确认。现在，我将根据我们最终达成的所有共识，为您生成完整的PRD文档。

---
# 产品需求文档：智能体输出稳定性评测工具 - V1.0 (MVP)

## 1. 综述 (Overview)
### 1.1 项目背景与核心问题
本项目旨在解决A团队（智能体优化方）与B团队（智能体审核方）之间的协作效率问题。当前，对智能体输出稳定性的校验流程依赖手动、重复的测试，沟通成本高，反馈周期长。本工具致力于提供一个自动化的评测平台，A团队可以自助发起评测，B团队可以快速查看结构化的评测结果，从而加速智能体的迭代优化周期。

### 1.2 核心业务流程 / 用户旅程地图
1.  **阶段一：创建评测任务** - 用户配置待测智能体信息，并上传包含问题与标准答案的数据集以发起评测。
2.  **阶段二：执行与监控任务** - 系统后台自动执行评测，用户可在列表页查看任务的实时状态与进度。
3.  **阶段三：查看评测结果** - 任务完成后，用户可以查看每个问题对应的5次调用原始输出。
4.  **阶段四：导出评测报告** - 用户可将详细的评测结果导出为CSV文件，用于离线分析与分发。

### 1.3 技术栈与架构总览 (Tech Stack & Architecture)

#### 后端技术栈 (Backend)
*   **后端框架**: 基于 FastAPI (Python 3.11)，使用 Pydantic 校验入参与出参，Uvicorn 作为应用服务器。
*   **持久化层**: PostgreSQL 15 作为主事务数据库；采用 SQLAlchemy 2.0 + Alembic 维护数据模型与迁移。
*   **异步执行**: Celery 5 + Redis 7 实现任务队列与并发调度，支持多 worker 线性扩展；统一通过 `EVALUATION_CONCURRENCY` 和 `RATE_LIMIT_PER_AGENT` 环境变量控制速率。
*   **文件存储**: 测试数据集落地至本地工作目录或对象存储（后续可抽象 Storage 适配器），解析后的结构化问题写入 PostgreSQL。
*   **配置管理**: 所有敏感配置（第三方 API Tokens、数据库/Redis 连接串、默认超时等）通过环境变量注入，支持 `.env` 在本地开发配置。
*   **观测性**: FastAPI 集成标准请求日志；Celery 任务在数据库记录运行指标（调用耗时、错误码）；预留 Prometheus 指标导出与 Sentry 异常上报接入点。
*   **运行模式**: MVP 先以本地虚拟环境 + Docker Compose 运行 PostgreSQL/Redis；默认并发度为 1，每个智能体的速率限制为 `1/s`，后续可通过环境变量扩展；暂不接入统一登录权限体系。

### 1.4 时间与时区策略（全局）
- 对外展示的一切时间均以北京时间（Asia/Shanghai，UTC+08:00）为准，包括前端页面与导出文件。
- 后端存储统一使用带时区的 UTC 时间；接口返回时在服务端转换为北京时间。
- 前端渲染时间：若后端返回带时区时间字符串，按其时区解析后转换到北京时间显示；若不带时区则按 UTC 解析后转换到北京时间。
- 导出 CSV/XLSX 中的“任务创建时间 / 任务完成时间”输出为北京时间的 ISO 8601 字符串（示例：2025-10-27T08:50:00+08:00）。

#### 前端技术栈 (Frontend)
*   **框架**: Vite 5 + React 18 + TypeScript 5
*   **UI组件库**: Ant Design 5.x
*   **路由管理**: React Router v6
*   **API调用**: Axios（支持请求拦截、响应拦截、错误统一处理）
*   **状态管理**: React Hooks（useState、useEffect）+ Context API
*   **开发工具**: MSW (Mock Service Worker) 用于开发阶段API Mock
*   **构建产物**: 静态HTML/JS/CSS，可部署到Nginx或对象存储（如OSS、S3）
*   **代码规范**: ESLint + Prettier

### 1.5 前端路由设计 (Frontend Routes)
| 路由路径 | 页面名称 | 说明 |
|---------|---------|------|
| `/` | 创建任务页 | 首页/默认页，用户进入即可发起评测 |
| `/tasks` | 任务列表页 | 查看所有评测任务及状态 |
| `/tasks/:taskId/results` | 结果详情页 | 查看指定任务的评测结果（支持分页） |

### 1.6 前端交互与错误提示规范 (Frontend UX Guidelines)

#### 状态显示映射
| 后端状态 | 前端显示文案 | Ant Design Tag颜色 |
|---------|------------|------------------|
| PENDING | 等待中 | default (灰色) |
| RUNNING | 运行中 | processing (蓝色) |
| SUCCEEDED | 已完成 | success (绿色) |
| FAILED | 失败 | error (红色) |

#### 错误提示文案标准

**创建任务页 (/)：**
- 任务名称未填：`请输入任务名称`
- 任务名称过长：`任务名称不能超过64个字符`
- API URL未填：`请输入智能体API URL`
- API URL格式错误：`请输入有效的HTTP或HTTPS地址`
- 未选择文件：`请上传测试数据集文件`
- 文件大小超限：`文件大小不能超过5MB，请压缩后重试`
- 文件格式不支持：`仅支持CSV或Excel格式文件`
- 后端返回错误：直接显示后端返回的 `message` 字段

**任务列表页 (/tasks)：**
- 加载失败：`加载任务列表失败，请刷新重试`
- 网络错误：`网络连接失败，请检查网络后重试`

**结果详情页 (/tasks/:taskId/results)：**
- 任务未完成（HTTP 409）：`任务尚未完成，请稍后查看`
- 加载失败：`加载评测结果失败，请刷新重试`
- 导出失败：`导出CSV失败，请重试`

## 2. 用户故事详述 (User Stories)

### 阶段一：创建评测任务

---

#### **US-01: 作为评测任务发起人，我希望能够配置待评测的智能体信息并上传测试数据集，以便于快速、准确地发起一次智能体稳定性评测任务。**
*   **价值陈述 (Value Statement)**:
    *   **作为** 评测任务发起人
    *   **我希望** 在一个简单的页面上提交智能体的API信息和测试数据
    *   **以便于** 用标准化的方式启动一次自动化评测。
*   **业务规则与逻辑 (Business Logic)**:
    1.  **前置条件**: V1.0 以单用户本地部署为主，无需登录流程。
    2.  **操作流程 (Happy Path)**:
        1. 用户进入“创建新的评测任务”页面。
        2. 在“任务名称”输入框中，为本次评测命名。
        3. 在“智能体 API URL”输入框中，粘贴待测智能体的完整POST请求地址。
        4. 点击“选择文件”上传一个CSV或Excel文件作为测试数据集。该文件必须包含`question`和`standard_answer`两列。
        5. 所有必填项完成后，“创建任务”按钮激活。
        6. 点击“创建任务”后，系统接收信息，创建一个新的评测任务，并将页面跳转至“我的评测任务”列表页。
    3.  **异常处理 (Error Handling)**:
        *   若用户未填写任务名称、API URL或未上传文件，点击提交时，在相应位置提示“此项为必填项”，任务创建失败。
        *   若上传的文件格式不正确（如非CSV/Excel，或内部缺少`question`、`standard_answer`列），系统应提示“文件格式不正确”，任务创建失败。
        *   后台的`API Key`将通过环境变量配置，不在前端暴露。
        *   后台调用智能体API时默认使用流式模式（`stream: true`），并在必要时支持降级为非流式。
*   **验收标准 (Acceptance Criteria)**:
    *   **场景1: 成功创建任务**
        *   **GIVEN** 我填写了任务名称、API URL，并上传了一个格式正确的CSV文件。
        *   **WHEN** 我点击“创建任务”按钮。
        *   **THEN** 页面应该跳转到“我的评测任务”页面，并能看到我刚刚创建的任务，其状态为“等待中”。
    *   **场景2: 输入信息不完整**
        *   **GIVEN** 我只填写了任务名称，但没有填写API URL或没有上传文件。
        *   **WHEN** 我尝试点击“创建任务”按钮。
        *   **THEN** 按钮应处于不可点击状态，或点击后在未填写的项目旁边出现红色错误提示。
    *   **场景3: 上传文件格式错误**
        *   **GIVEN** 我填写了所有文本信息，但上传了一个缺少`question`列的Excel文件。
        *   **WHEN** 我点击“创建任务”按钮。
        *   **THEN** 系统应提示错误“文件格式不正确，请确保包含'question'和'standard_answer'列”，任务创建失败。
---
*   **技术实现概要 (Technical Implementation Brief)**:
    *   **前端 / 客户端 (Frontend / Client)**:
        *   **表单字段**：
            - 任务名称（必填，最大64字符，实时验证）
            - 智能体 API URL（必填，HTTP/HTTPS格式验证）
            - 测试数据集文件上传（必填，支持 .csv、.xls、.xlsx）
            - 注：V1.0 不提供 `agent_api_headers` 和 `agent_model` 输入框（后续版本可扩展）
        *   **前端验证规则**：
            - 文件大小 ≤ 5MB（超出时阻止上传并提示：`文件大小不能超过5MB，请压缩后重试`）
            - 文件格式限制：仅接受 .csv、.xls、.xlsx 扩展名（不符合时提示：`仅支持CSV或Excel格式文件`）
            - 表单必填项校验（所有字段填写后才能激活"创建任务"按钮）
            - API URL格式验证（需以 http:// 或 https:// 开头）
        *   **后端验证规则**（前端调用API后由后端执行）：
            - 文件列验证（必须包含 `question` 和 `standard_answer` 列）
            - 行数范围 1-1000
            - 编码格式 UTF-8
            - 重复 `question_id` 检测
        *   **交互流程**：
            1. 用户填写表单字段
            2. 选择文件后前端立即验证大小和扩展名
            3. 所有必填项完成后，"创建任务"按钮变为可点击状态
            4. 点击"创建任务"按钮，调用 `POST /api/v1/evaluation-tasks`（Content-Type: multipart/form-data）
            5. 显示加载状态（按钮显示"创建中..."），禁用按钮防止重复提交
            6. **成功响应**：跳转到 `/tasks` 任务列表页，并通过 Toast/Message 显示成功提示"任务创建成功"
            7. **失败响应**：在表单下方显示红色错误提示（使用 Ant Design Alert 组件），保留已填写内容，按钮恢复可点击状态
        *   **文件上传组件状态**（使用 Ant Design Upload 组件）：
            - 待选择：显示"点击或拖拽文件到此区域上传"
            - 已选择：显示文件名、文件大小、移除按钮
            - 验证失败：显示红色错误图标和错误信息（如"文件过大"）
            - 上传中：显示进度条和"上传中..."文案（提交表单时）
            - 上传成功：跳转至列表页
        *   **API调用示例**：
            ```typescript
            const formData = new FormData();
            formData.append('task_name', taskName);
            formData.append('agent_api_url', apiUrl);
            formData.append('dataset_file', file);

            axios.post('/api/v1/evaluation-tasks', formData, {
              headers: { 'Content-Type': 'multipart/form-data' }
            });
            ```
    *   **页面布局线框图 (ASCII Wireframe)**:
        ```text
        +--------------------------------------------------------------------------+
        | 创建新的评测任务                                                         |
        +==========================================================================+
        |                                                                          |
        |  * 任务名称:                                                             |
        |    +------------------------------------------------------------------+  |
        |    | A团队XX模型V1.2稳定性测试                                        |  |
        |    +------------------------------------------------------------------+  |
        |                                                                          |
        |  * 智能体 API URL:                                                       |
        |    +------------------------------------------------------------------+  |
        |    | http://20.17.39.169:11105/aicoapi/gateway/v2/...                 |  |
        |    +------------------------------------------------------------------+  |
        |                                                                          |
        |  * 测试数据集 (CSV/Excel):                                               |
        |    +------------------------------------------------------------------+  |
        |    | [ 选择文件 ]  questions_v3.csv                                   |  |
        |    | (文件要求: 必须包含 'question' 和 'standard_answer' 两列)         |  |
        |    +------------------------------------------------------------------+  |
        |                                                                          |
        |  +----------------------------------------------------------------------+  |
        |  |                                                        [ 创建任务 ]  |  |
        |  +----------------------------------------------------------------------+  |
        |                                                                          |
        +--------------------------------------------------------------------------+
        ```
    *   **后端 (Backend)**:
        *   提供 `POST /api/v1/evaluation-tasks` 接口（`multipart/form-data`）。请求字段：
            *   `task_name` (`string`，1~64字符)。
            *   `agent_api_url` (`string`，HTTP/HTTPS POST 端点，需通过域名白名单校验，可在环境变量 `AGENT_API_ALLOWLIST` 中配置）。
            *   `agent_api_headers` (`string`，可选，JSON 字符串形式的自定义请求头，例如 `{"Authorization": "Bearer <token>"}`)。
            *   `agent_model` (`string`，可选，记录被测模型代号或版本)。
            *   `dataset_file` (`file`，必填，CSV/Excel，≤5MB，行数 1~1000)。
        *   数据集文件格式要求：
            *   必须包含列 `question`、`standard_answer`；推荐额外提供 `question_id`（可自定义字符串 ID），可选列 `system_prompt`、`user_context` 用于额外上下文。
            *   若缺少 `question_id` 列，则为每一行生成稳定的 UUID，并在导出时回显。
            *   自动去除空行、去除列名前后空白、检测重复 `question_id`（重复将返回 422），并验证 UTF-8 编码。
        *   FastAPI 在内存中读取文件，落地至 `/var/app/uploads/<task-id>/dataset.*`，随后使用 Pandas/OpenPyXL 解析为结构化数据，写入 PostgreSQL：
            *   `evaluation_tasks` 表存储任务主记录（`id`、`task_name`、`agent_api_url`、`agent_api_headers`、`agent_model`、`status`、`total_items`、`created_by`、`created_at`、`updated_at`、并发/限速配置等）。
            *   `evaluation_items` 表存储问题行（`id`、`task_id`、`question_id`、`question`、`standard_answer`、`system_prompt`、`user_context`）。
        *   成功创建后写入一条 Celery 任务 `run_evaluation_task`，payload 包含：
            *   `task_id`、`runs_per_item`（默认 5，可通过 `RUNS_PER_ITEM` 环境变量配置）、`timeout_seconds`（默认 30，可自定义）、`max_retries`（默认 1，仅对网络错误生效）、`use_stream`（默认 `true`）。
            *   任务在 Redis 队列 `evaluation` 中排队，遵循 `EVALUATION_CONCURRENCY` 与 `RATE_LIMIT_PER_AGENT` 环境配置的速率限制。
        *   成功响应：
            ```json
            {
              "task_id": "6f0d3c1e-3f68-4b5a-9f5c-5e4d2f7d2f11",
              "status": "PENDING"
            }
            ```
            失败响应统一格式：
            ```json
            {
              "code": "DATASET_SCHEMA_INVALID",
              "message": "文件缺少 question 或 standard_answer 列"
            }
            ```

### 阶段二：执行与监控任务

---

#### **US-02: 作为评测任务发起人，我希望能够查看我所创建任务的执行状态和进度，以便于了解任务是否正常运行。**
*   **价值陈述 (Value Statement)**:
    *   **作为** 评测任务发起人
    *   **我希望** 查看一个包含所有任务的列表
    *   **以便于** 监控任务的执行情况。
*   **业务规则与逻辑 (Business Logic)**:
    1.  **任务状态**: 任务生命周期包括：`等待中`、`运行中`、`已完成`、`失败`（指任务创建或初始化失败等系统级错误）。
    2.  **进度展示**: 当任务`运行中`时，需实时计算并展示 `(已处理问题数 / 总问题数)`。
    3.  **数据更新**: 页面数据通过用户**手动刷新**浏览器来更新。
    4.  **交互逻辑**: 只有当任务状态为`已完成`时，“查看”按钮才可点击，并跳转到结果详情页。其他状态下按钮置灰。
    5.  **超时机制**: 单次调用智能体API的超时时间应支持通过环境变量配置（如默认30秒）。超时记为一次调用失败，并记录错误信息为 `TIMEOUT_ERROR`。
    6.  **任务失败定义**: 任务只有在无法启动（如数据库异常）等系统级问题时才标记为`失败`。即使所有问题项都调用超时，任务本身也应流转至`已完成`状态。
*   **验收标准 (Acceptance Criteria)**:
    *   **场景1: 成功加载任务列表**
        *   **GIVEN** 我之前已创建过任务。
        *   **WHEN** 我访问“我的评测任务”页面。
        *   **THEN** 我能看到一个表格，正确显示每个任务的【状态】、【任务名称】、【创建时间】、【进度】和【操作】按钮。
    *   **场景2: 手动刷新更新进度**
        *   **GIVEN** 页面上一个“运行中”任务进度为 `50 / 100`。
        *   **WHEN** 后台处理了更多问题后，我手动刷新页面。
        *   **THEN** 该任务的进度应相应更新，最终状态变为“已完成”，进度为 `100 / 100`。
    *   **场景3: 操作按钮的可用性**
        *   **GIVEN** 页面上有处于“等待中”、“运行中”和“已完成”状态的多个任务。
        *   **WHEN** 我查看这个列表。
        *   **THEN** 只有“已完成”任务的“[查 看]”按钮是可点击的，其余状态的按钮均为灰色不可点击。
---
*   **技术实现概要 (Technical Implementation Brief)**:
    *   **前端 / 客户端 (Frontend / Client)**:
        *   **页面功能**：
            - 页面标题："我的评测任务"
            - 右上角"创建新任务"按钮（跳转到 `/` 首页）
            - 右上角"刷新"图标按钮（点击重新调用 `GET /api/v1/evaluation-tasks` 刷新数据）
            - 任务表格（使用 Ant Design Table 组件）
            - 底部分页组件（Ant Design Pagination）
        *   **表格列配置**：
            | 列名 | 宽度 | 数据源字段 | 说明 |
            |------|------|-----------|------|
            | 状态 | 100px | status | 使用 Ant Design Tag 显示，颜色映射见1.6节 |
            | 任务名称 | 自适应 | task_name | 左对齐，支持超长截断 |
            | 创建时间 | 180px | created_at | 北京时间，格式化为 YYYY-MM-DD HH:mm |
            | 进度 | 120px | progress | 显示格式：`processed/total`，如 `75/150` |
            | 操作 | 100px | - | "查看"按钮 |
        *   **状态显示**：
            - 使用 Ant Design `<Tag>` 组件显示状态
            - 状态文案和颜色映射见 1.6 节"状态显示映射"表
            - 示例：`<Tag color="processing">运行中</Tag>`
        *   **进度展示逻辑**：
            - 格式：`已处理数 / 总数`（例如：`75/150`）
            - PENDING 状态显示：`0/总数`（任务尚未开始）
            - RUNNING 状态显示：动态更新的实际进度（如 `75/150`）
            - SUCCEEDED 状态显示：`总数/总数`（如 `100/100`）
            - **FAILED 状态显示：实际的 `processed/total` 值**（如 `50/150`，表示处理到第50个问题时因系统级异常失败）
                - 使用**红色文字**显示进度数字，以区别于正常状态
                - 或使用格式：`50/150 (已停止)` 更明确地表达失败状态
                - 后端保证在 FAILED 状态下仍返回真实的 `progress.processed` 值，便于排查问题
        *   **操作按钮逻辑**：
            - 仅 `status === 'SUCCEEDED'` 时"查看"按钮可点击
            - 其他状态（PENDING/RUNNING/FAILED）按钮置灰（`disabled={true}`）
            - 点击"查看"按钮跳转到 `/tasks/:taskId/results`
        *   **空状态展示**（使用 Ant Design Empty 组件）：
            - 当任务列表为空时，表格中间显示空状态
            - 图标：Ant Design Empty 默认图标
            - 提示文案："还没有评测任务"
            - 提供一个主操作按钮："创建第一个任务"（跳转到 `/`）
        *   **刷新机制**：
            - 用户可手动刷新浏览器页面更新数据
            - 点击右上角"刷新"按钮（使用 Ant Design `<ReloadOutlined>` 图标）重新请求 API
            - 刷新时显示表格 loading 状态（`<Table loading={isLoading}>`）
            - V1.0 不实现自动轮询（后续可扩展）
        *   **分页配置**：
            - 默认每页显示 20 条
            - 使用 Ant Design Pagination 组件
            - 页码变化时调用 `GET /api/v1/evaluation-tasks?page={page}&page_size=20`
            - URL参数同步（使用 React Router 的 `useSearchParams`）
        *   **错误处理**：
            - API调用失败时，显示 Ant Design Message 错误提示："加载任务列表失败，请刷新重试"
            - 网络错误时提示："网络连接失败，请检查网络后重试"
        *   **API调用示例**：
            ```typescript
            const fetchTasks = async (page: number = 1) => {
              const response = await axios.get('/api/v1/evaluation-tasks', {
                params: { page, page_size: 20 }
              });
              return response.data; // { items: [...], pagination: {...} }
            };
            ```
    *   **页面布局线框图 (ASCII Wireframe)**:
        ```text
        +------------------------------------------------------------------------------------+
        | 我的评测任务                                                                       |
        |                                                                    [+ 创建新任务]  |
        +------------------------------------------------------------------------------------+
        |                                                                                    |
        | +----------+-----------------------------+---------------------+---------+---------+ |
        | | 状态     | 任务名称                    | 创建时间            | 进度    | 操作    | |
        | +----------+-----------------------------+---------------------+---------+---------+ |
        | | 已完成   | A模型V1.2稳定性测试         | 2025-10-26 10:30    | 100/100 | [查 看] | |
        | | 运行中   | B模型最终验收测试           | 2025-10-26 10:25    | 75/150  | (查看)  | |
        | | 失败     | C模型初始化失败             | 2025-10-26 10:20    | 0/50    | (查看)  | |
        | | 等待中   | A模型V1.3回归测试           | 2025-10-26 10:15    | 0/200   | (查看)  | |
        | +----------+-----------------------------+---------------------+---------+---------+ |
        |                                                                                    |
        |                                                     << 上一页 | [ 1 ] | 下一页 >>  |
        |                                                                                    |
        +------------------------------------------------------------------------------------+
        ```
    *   **后端 (Backend)**:
        *   提供 `GET /api/v1/evaluation-tasks` 接口（支持分页与过滤）：
            *   查询参数：`page`（默认1）、`page_size`（默认20，最大100）、`status`（可选，多选）、`query`（任务名称模糊搜索）。
            *   返回当前实例内的所有任务（单用户部署场景），数据按 `created_at DESC` 排序；后续可扩展为多用户共享。
            *   响应体示例：
            ```json
            {
              "items": [
                {
                  "task_id": "uuid",
                  "task_name": "A模型V1.2稳定性测试",
                  "status": "RUNNING",
                  "progress": {"processed": 75, "total": 150},
                  "created_at": "2025-10-26T10:25:00Z",
                  "updated_at": "2025-10-26T10:32:10Z"
                }
              ],
              "pagination": {"page": 1, "page_size": 20, "total": 3}
            }
            ```
        *   状态流转：
            *   `PENDING`（创建完成，等待工作器抢占）→ `RUNNING`（Celery worker 开始执行）→ `SUCCEEDED`（全部问题处理完成）或 `FAILED`（系统级错误提前终止）。
            *   若所有调用均超时或返回错误，仍视为 `SUCCEEDED`，并在明细中记录各运行的 `error_code`。
        *   Celery 工作器实现：
            *   Worker 并发度由 `EVALUATION_CONCURRENCY` 控制（默认 1），单模型速率由 `RATE_LIMIT_PER_AGENT`（默认 `1/s`）限制，避免打爆目标服务。
            *   每个任务按 `evaluation_items` 顺序处理。对每个问题执行 `runs_per_item` 次调用，默认 5 次；对每次调用写入 `evaluation_runs` 表（`id`、`item_id`、`run_index`、`status`、`response_body`、`latency_ms`、`error_code`、`error_message`、`created_at`）。
            *   请求体默认结构：
                ```json
                {
                  "question": "<question>",
                  "standard_answer": "<standard_answer>",
                  "system_prompt": "<system_prompt|null>",
                  "user_context": "<user_context|null>",
                  "stream": true
                }
                ```
                允许后续通过任务级配置扩展字段（如 `extra_payload`）。
            *   Worker 使用 `httpx` 同步客户端发起 POST 调用，超时时间 `timeout_seconds`（默认 30）。超时抛出 `TIMEOUT`，HTTP 非 2xx 记录 `HTTP_<status>`，响应解析失败记录 `PARSE_ERROR`。
            *   针对流式响应，逐行解析 `event` 字段，累计 `llm_chunk`/`reasoning_chunk` 内容，记录最终 `node_finished` 的 `output`/`content`；若设置 `stream=false`，则直接读取一次性 JSON 响应。
            *   为兼容部分智能体返回中未转义的换行/制表符，解析 JSON 时需启用宽松模式（如 `json.loads(..., strict=False)`），否则会被误判为 `PARSE_ERROR`。
            *   对 `TIMEOUT` 和网络异常执行一次指数退避重试（最大 1 次）。仍失败时将错误写入 `evaluation_runs`，继续处理下一次运行。
            *   每处理完一个问题即更新 `evaluation_tasks.progress_processed` 字段，并写 `updated_at`，供列表页刷新展示。

### 阶段三：查看评测结果

---

#### **US-03: 作为评测审核人，我希望能在一个页面上查看每个问题对应的5次原始输出，以便于进行人工评估。**
*   **价值陈述 (Value Statement)**:
    *   **作为** 评测审核人
    *   **我希望** 看到并列展示的所有原始输出结果
    *   **以便于** 直观地对智能体的稳定性进行人工判断。
*   **业务规则与逻辑 (Business Logic)**:
    1.  **页面结构**: 页面顶部展示任务的基本信息（任务名称）。下方是一个详细的结果列表。
    2.  **数据展示**: 列表的每一项代表一个问题，需要清晰地展示【问题】、【标准答案】，以及并排的【运行1输出】、【运行2输出】...【运行5输出】。
    3.  **无自动判定**: V1.0版本不包含任何自动“通过/不通过”的判定逻辑，也不计算“准确率”。
*   **验收标准 (Acceptance Criteria)**:
    *   **场景1: 成功加载结果页面**
        *   **GIVEN** 我在一个状态为“已完成”的任务项上点击“[查 看]”按钮。
        *   **WHEN** 页面加载完成。
        *   **THEN** 我能看到页面标题为评测任务的名称，下方有一个表格，列出了该任务包含的所有问题。
    *   **场景2: 结果数据准确性**
        *   **GIVEN** 某个问题的5次API调用返回了不同的结果。
        *   **WHEN** 我在结果页查看该问题。
        *   **THEN** 页面应准确无误地展示该问题的`question`、`standard_answer`，以及5次API调用返回的完整、原始的输出内容。如果某次调用失败，则对应位置应显示错误信息（如`TIMEOUT_ERROR`）。
---
*   **技术实现概要 (Technical Implementation Brief)**:
    *   **前端 / 客户端 (Frontend / Client)**:
        *   **页面布局**：
            - 顶部区域：
                - 左侧：页面标题 "评测报告: [任务名称]"
                - 右侧："导出CSV"按钮 + "返回列表"按钮
            - 主体区域：结果列表（使用 Ant Design Card 或自定义列表组件）
            - 底部区域：分页组件（Ant Design Pagination）
        *   **结果项展示**（每个问题一个卡片/区块，**不显示 question_id**）：
            - **问题文本**（加粗显示，字体略大）
            - **标准答案**（常规字体，灰色文字）
            - **5次运行结果**（垂直排列或网格布局）：
                - 每次运行显示：
                    - 运行序号（如 `#1`、`#2`...`#5`）
                    - 输出内容（支持超长文本折叠，见下文）
                    - 运行状态（成功/失败，使用 Tag 标签）
                    - 耗时（单位：ms，如 `812ms`）
                    - 错误码（仅失败时显示，如 `TIMEOUT`）
        *   **超长文本处理**：
            - 每次运行的输出内容默认显示前 **200 个字符**
            - 超出部分用省略号 `...` 表示
            - 提供"展开/收起"文字按钮：
                - 点击"展开"后显示完整内容
                - 点击"收起"后折叠回200字符
            - 使用 React 状态管理每个输出的展开/收起状态
        *   **错误状态显示**：
            - 若某次运行失败（`status: 'FAILED'` 或 `status: 'TIMEOUT'`）：
                - 输出内容区域显示红色文字：错误码（如 `TIMEOUT_ERROR`）
                - 显示错误图标（Ant Design `<CloseCircleOutlined>` 红色图标）
                - 显示错误信息（如 `error_message: "Agent request timed out after 30s"`）
                - 仍然显示耗时（如 `30000ms`）
            - 使用 Ant Design `<Alert>` 或自定义错误样式
        *   **分页配置**：
            - 默认每页显示 **20 个问题**
            - 使用 Ant Design Pagination 组件
            - 页码变化时调用 `GET /api/v1/evaluation-tasks/{taskId}/results?page={page}&page_size=20`
            - URL参数同步（使用 React Router 的 `useSearchParams`）
            - 示例：`/tasks/abc123/results?page=2`
        *   **导出CSV功能**：
            - 点击"导出CSV"按钮后：
                1. 按钮显示加载状态（`<Button loading={true}>正在生成CSV...</Button>`）
                2. 调用 `GET /api/v1/evaluation-tasks/{taskId}/export`
                3. 后端返回文件流，前端触发浏览器下载
                4. 下载完成后恢复按钮状态
            - 错误处理：若导出失败，显示 Message 错误提示："导出CSV失败，请重试"
        *   **加载状态**：
            - 首次进入页面时，显示 Ant Design Spin 全屏加载动画
            - 分页切换时，显示局部 loading（Card 或 List 的 loading 属性）
        *   **错误处理**：
            - 若任务未完成（HTTP 409），显示提示："任务尚未完成，请稍后查看"，并提供"返回列表"按钮
            - 若加载失败（HTTP 500/网络错误），显示："加载评测结果失败，请刷新重试"
            - 使用 Ant Design Result 组件展示错误页面
        *   **API调用示例**：
            ```typescript
            // 获取结果列表
            const fetchResults = async (taskId: string, page: number = 1) => {
              const response = await axios.get(`/api/v1/evaluation-tasks/${taskId}/results`, {
                params: { page, page_size: 20 }
              });
              return response.data; // { task: {...}, items: [...], pagination: {...} }
            };

            // 导出CSV
            const exportCSV = async (taskId: string) => {
              const response = await axios.get(`/api/v1/evaluation-tasks/${taskId}/export`, {
                responseType: 'blob'
              });
              // 触发浏览器下载
              const url = window.URL.createObjectURL(new Blob([response.data]));
              const link = document.createElement('a');
              link.href = url;
              link.setAttribute('download', `${taskName}_评测报告.csv`);
              document.body.appendChild(link);
              link.click();
              link.remove();
            };
            ```
        *   **UI组件选型**：
            - 结果列表：Ant Design `<Card>` 或 `<List>` 组件
            - 状态标签：Ant Design `<Tag>` 组件
            - 展开/收起：Ant Design `<Typography.Paragraph ellipsis={{ rows: 3, expandable: true }}>`（或自定义实现）
            - 分页：Ant Design `<Pagination>`
            - 加载：Ant Design `<Spin>` 和 `<Skeleton>`
            - 错误页：Ant Design `<Result>`
    *   **页面布局线框图 (ASCII Wireframe)**:
        ```text
        +------------------------------------------------------------------------------------+
        | 评测报告: [A模型V1.2稳定性测试]                                                    |
        +====================================================================================+
        |                                                                    [导出CSV]       |
        +------------------------------------------------------------------------------------+
        |                                                                                    |
        |  +-------------------------------------------------------------------------------+  |
        |  | 问题: "中国的首都是哪里？"                                                    |  |
        |  | 标准答案: "北京"                                                              |  |
        |  |-------------------------------------------------------------------------------|  |
        |  | #1 输出: "北京是中国的首都。"                                                |  |
        |  | #2 输出: "中华人民共和国的首都是北京。"                                      |  |
        |  | #3 输出: "北京"                                                             |  |
        |  | #4 输出: TIMEOUT_ERROR                                                        |  |
        |  | #5 输出: "北京，也被称为..."                                                  |  |
        |  +-------------------------------------------------------------------------------+  |
        |                                                                                    |
        |  +-------------------------------------------------------------------------------+  |
        |  | 问题: "上海的别称是什么？"                                                    |  |
        |  | 标准答案: "申城、魔都"                                                        |  |
        |  | ... (5次输出)                                                                 |  |
        |  +-------------------------------------------------------------------------------+  |
        |                                                                                    |
        +------------------------------------------------------------------------------------+
        ```
    *   **后端 (Backend)**:
        *   提供 `GET /api/v1/evaluation-tasks/{task_id}/results` 接口：
            *   当前版本为单用户部署，无鉴权限制；若任务未完成返回 409 `TASK_NOT_FINISHED`。
            *   支持查询参数 `page`、`page_size`（默认 1/20）以及 `question_id` 精确过滤，避免一次性加载过大结果集。
            *   响应结构：
            ```json
            {
              "task": {
                "task_id": "uuid",
                "task_name": "A模型V1.2稳定性测试",
                "status": "SUCCEEDED",
                "runs_per_item": 5,
                "timeout_seconds": 30
              },
              "items": [
                {
                  "question_id": "Q0001",
                  "question": "中国的首都是哪里？",
                  "standard_answer": "北京",
                  "system_prompt": null,
                  "user_context": null,
                  "runs": [
                    {
                      "run_index": 1,
                      "status": "SUCCEEDED",
                      "response_body": "北京是中国的首都。",
                      "latency_ms": 812,
                      "error_code": null,
                      "error_message": null,
                      "created_at": "2025-10-26T10:31:12Z"
                    },
                    {
                      "run_index": 4,
                      "status": "FAILED",
                      "response_body": null,
                      "latency_ms": 30000,
                      "error_code": "TIMEOUT",
                      "error_message": "Agent request timed out after 30s",
                      "created_at": "2025-10-26T10:32:45Z"
                    }
                  ]
                }
              ],
              "pagination": {"page": 1, "page_size": 20, "total": 120}
            }
            ```
            *   `status` 字段取值：`SUCCEEDED`（正常返回）、`FAILED`（HTTP 错误/解析异常）、`TIMEOUT`、`RETRYING`（处理中）。
            *   结果按 `question_id ASC`、`run_index ASC` 排序，方便对比。

### 阶段四：生成并导出报告

---

#### **US-04: 作为评测审核人，我希望能下载一份包含所有原始输出的评测报告，以便于离线归档或发送给A团队。**
*   **价值陈述 (Value Statement)**:
    *   **作为** 评测审核人
    *   **我希望** 下载一份CSV格式的详细报告
    *   **以便于** 将评测结果方便地交付给其他人。
*   **业务规则与逻辑 (Business Logic)**:
    1.  **导出触发**: 用户在结果详情页点击“导出CSV”按钮来触发下载。
    2.  **文件命名**: 导出的文件名默认为 `[任务名称]_评测报告.csv`。
    3.  **文件内容**: CSV文件需包含所有问题的详细运行数据，列定义如下。
*   **验收标准 (Acceptance Criteria)**:
    *   **场景1: 成功导出报告**
        *   **GIVEN** 我正在查看评测报告页面。
        *   **WHEN** 我点击“[导出CSV]”按钮。
        *   **THEN** 浏览器应开始下载一个以任务名称命名的CSV文件。
    *   **场景2: 导出内容完整准确**
        *   **GIVEN** 我已下载并用Excel打开报告文件。
        *   **WHEN** 我检查文件内容。
        *   **THEN** 文件的列和数据应与我们定义的数据契约一致，并包含报告中的所有问题。
---
*   **技术实现概要 (Technical Implementation Brief)**:
    *   **前端 / 客户端 (Frontend / Client)**:
        *   **按钮位置**：在结果详情页（`/tasks/:taskId/results`）的顶部右侧，与"返回列表"按钮并列
        *   **交互流程**：
            1. 用户点击"导出CSV"按钮
            2. 前端调用 `GET /api/v1/evaluation-tasks/{taskId}/export`，设置 `responseType: 'blob'`
            3. 按钮显示加载状态：`<Button loading={true} icon={<DownloadOutlined />}>正在生成CSV...</Button>`
            4. 后端返回文件流（Content-Type: text/csv）
            5. 前端使用 Blob API 触发浏览器下载，文件名为 `${taskName}_评测报告.csv`
            6. 下载成功后，按钮恢复初始状态，显示成功提示："导出成功"（Ant Design Message.success）
            7. 下载失败时，按钮恢复初始状态，显示错误提示："导出CSV失败，请重试"（Ant Design Message.error）
        *   **错误处理**：
            - HTTP 404：任务不存在，提示"任务不存在"
            - HTTP 409：任务未完成，提示"任务尚未完成，无法导出"
            - HTTP 500：服务器错误，提示"导出CSV失败，请重试"
            - 网络错误：提示"网络连接失败，请检查网络后重试"
        *   **API调用实现**（已在 US-03 中详细说明）：
            ```typescript
            const exportCSV = async (taskId: string, taskName: string) => {
              try {
                setExporting(true);
                const response = await axios.get(`/api/v1/evaluation-tasks/${taskId}/export`, {
                  responseType: 'blob'
                });

                // 创建下载链接
                const url = window.URL.createObjectURL(new Blob([response.data]));
                const link = document.createElement('a');
                link.href = url;
                link.setAttribute('download', `${taskName}_评测报告.csv`);
                document.body.appendChild(link);
                link.click();
                link.remove();
                window.URL.revokeObjectURL(url);

                message.success('导出成功');
              } catch (error) {
                if (error.response?.status === 409) {
                  message.error('任务尚未完成，无法导出');
                } else {
                  message.error('导出CSV失败，请重试');
                }
              } finally {
                setExporting(false);
              }
            };
            ```
        *   **注意事项**：
            - 导出的是**全部数据**，不受前端分页限制（即使用户只看了第1页，导出的CSV包含所有问题）
            - 文件名中的任务名称需要进行文件名安全处理（移除特殊字符如 `/`、`\`、`:`等）
            - 大文件导出时可能耗时较长，需要合理设置请求超时时间（建议60秒）
    *   **后端 (Backend)**:
        *   提供 `GET /api/v1/evaluation-tasks/{task_id}/export` 接口：
            *   单用户部署，所有任务可直接导出；任务状态须为 `SUCCEEDED`。
            *   支持查询参数 `format`（默认 `csv`，预留 `xlsx` 扩展），`include_errors`（默认 `true`，控制是否输出错误列）。
            *   从 PostgreSQL 以流式游标读取 `evaluation_items` 与 `evaluation_runs`，避免一次性加载至内存。
            *   使用 Python `csv` 标准库或 `pandas.to_csv` 生成 `text/csv` 文件流，设置 `Content-Disposition` 同时包含：`filename="<ASCII安全名>_report.csv"` 与 `filename*=UTF-8''<urlencoded(任务名称)>_report.csv`。
            *   CSV 中同一问题的多次运行会展开为独立列，列名遵循 `run_<index>_output`、`run_<index>_status`、`run_<index>_latency_ms`、`run_<index>_error_code`。
            *   若 `format=xlsx`，则通过 `openpyxl` 按同样结构生成 Excel，并在首行加入信息页（任务名称、模型、运行时间等）。
*   **数据模型 / 接口契约 (Data Contracts & APIs)**:
    *   **导出 CSV 列定义（默认包含，下划线字段为可选）**:
        1.  `question_id`
        2.  `question`
        3.  `standard_answer`
        4.  `_system_prompt`
        5.  `_user_context`
        6.  `run_1_output`
        7.  `run_1_status`
        8.  `run_1_latency_ms`
        9.  `run_1_error_code`
        10. `run_2_output`
        11. `run_2_status`
        12. `run_2_latency_ms`
        13. `run_2_error_code`
        14. `...`（直至 `run_n_*`，`n` 由任务实际运行次数决定）
        15. `_created_at`（任务创建时间，北京时间，ISO 8601）
        16. `_completed_at`（任务完成时间，北京时间，ISO 8601）

---

## 变更记录

日期：2025-10-27

- 全局时间与时区策略：所有对外展示时间统一为北京时间（Asia/Shanghai，UTC+08:00）；后端存储为带时区的 UTC，接口返回转换为北京时间；前端在渲染时按规则解析并转北京时间。
- 导出内容时间：CSV/XLSX 中“任务创建时间/任务完成时间”输出北京时间的 ISO 8601（示例：2025-10-27T08:50:00+08:00）。
- 导出文件名编码：为兼容浏览器以中文文件名下载，HTTP 响应头同时提供 `filename="ASCII安全名"` 与 `filename*=UTF-8''<urlencoded中文文件名>`（RFC 5987）。
