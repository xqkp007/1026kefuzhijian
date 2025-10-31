# 产品需求文档：智能体输出稳定性评测工具 - V1.2（模型矫正与准确率计算）

> **文档状态**：正式版（Final）
> **创建日期**：2025-10-27
> **基于版本**：V1.1（智谱SDK接入）

---

## 1. 综述 (Overview)

### 1.1 项目背景与核心问题

**V1.0/V1.1 现状**：
- V1.0 已实现核心评测功能：任务创建、执行监控（每问题5次调用）、结果查看、CSV导出。
- V1.1 完成智谱 SDK 接入，支持通过 `zhipu` 前缀识别并调用智谱模型。

**V1.2 核心目标**：
- 当前版本仅记录原始输出，缺乏自动化的正确性判断能力，B团队（审核方）仍需人工逐条检查，效率低下。
- V1.2 引入**模型矫正（Model Correction）**功能，使用智谱 GLM-4.6 模型自动判断每次输出的正确性，并基于"5次全对才算通过"的规则计算任务级别的准确率，从而大幅降低人工审核成本。

### 1.2 核心业务流程 / 用户旅程地图

1.  **阶段一：创建评测任务** - 用户配置待测智能体信息、上传数据集，并**选择是否启用模型矫正**。
2.  **阶段二：执行与监控任务** - 系统执行5次智能体调用；**如启用矫正，则在5次调用完成后，批量调用矫正模型进行判断**；计算准确率。
3.  **阶段三：查看评测结果** - 用户查看每个问题的5次原始输出、**每次输出的矫正结果（✅/❌）**、问题级判定（通过/不通过）、**任务级准确率统计**。
4.  **阶段四：导出评测报告** - 用户导出CSV报告，**顶部包含任务元信息（准确率、通过题数等）**，每个运行结果增加矫正相关列。

### 1.3 V1.2 核心功能特性

#### 1.3.1 任务类型分化
- **类型A**（原有）：纯评测任务 - 只记录5次原始输出，不做自动判断
- **类型B**（新增）：带矫正的评测任务 - 在5次调用完成后，使用矫正模型自动判断每次输出的正确性

#### 1.3.2 矫正逻辑
- **矫正模型**：系统固定使用智谱 GLM-4.6 模型（用户无需配置）
- **矫正输入**：
  - `question`（问题文本）
  - `standard_answer`（标准答案）
  - `agent_output`（智能体的输出）
- **矫正输出**：结构化JSON - `{"is_correct": true/false, "reason": "判断理由"}`
- **矫正触发时机**：每个问题的5次调用全部完成后，批量调用矫正模型5次（每个输出独立矫正）

#### 1.3.3 准确率计算规则
- **问题级别判定**：
  - 5次输出**全部正确** → 该问题标记为"通过"
  - 只要有1次错误 → 该问题标记为"不通过"
- **任务级别准确率** = `通过的问题数 / 总问题数 × 100%`

#### 1.3.4 容错与重试策略
- 矫正模型调用失败时，重试 **3次**（通过环境变量 `CORRECTION_MAX_RETRIES` 配置）
- 仍失败则标记为"矫正失败"，该次运行视为错误；所属问题判定为"不通过"，计入准确率计算

### 1.4 技术栈（继承V1.0/V1.1）

- **后端**：FastAPI + Celery + PostgreSQL + Redis（Python 3.11）
- **前端**：React 18 + TypeScript + Vite + Ant Design 5
- **矫正模型**：智谱 GLM-4.6（通过 `zai-sdk` 调用）

### 1.5 环境变量新增配置

在 `backend/.env` 中新增以下配置项：

```bash
# 矫正功能配置
CORRECTION_MODEL_ID="glm-4.6"                    # 矫正模型ID
CORRECTION_TIMEOUT_SECONDS=30                     # 矫正调用超时时间（秒）
CORRECTION_MAX_RETRIES=3                          # 矫正失败最大重试次数
CORRECTION_TEMPERATURE=0.3                        # 矫正模型温度（建议低温，保证判断一致性）
CORRECTION_MAX_TOKENS=512                         # 矫正模型最大输出token数
```

---

## 2. 用户故事详述 (User Stories)

### 阶段一：创建评测任务

---

#### **US-01（V1.2增强）: 作为评测任务发起人，我希望在创建任务时可以选择是否启用模型矫正，以便于让系统自动判断输出的正确性并计算准确率。**

*   **价值陈述 (Value Statement)**:
    *   **作为** 评测任务发起人
    *   **我希望** 在创建任务时可以选择是否启用模型矫正
    *   **以便于** 让系统自动判断输出的正确性并计算准确率，无需人工逐条检查

*   **业务规则与逻辑 (Business Logic)**:
    1.  **前置条件**: 用户已进入任务创建页面；后端已配置好智谱API密钥（`ZHIPU_API_KEY`）。
    2.  **操作流程 (Happy Path)**:
        1. 用户进入"创建新的评测任务"页面（路径：`/`）。
        2. 填写"任务名称"（必填，最大64字符）。
        3. 填写"智能体 API URL"（必填，HTTP/HTTPS格式）。
        4. 上传"测试数据集"文件（必填，CSV/Excel格式，包含`question`和`standard_answer`列）。
        5. **【V1.2新增】** 在表单底部找到"启用模型矫正"开关（Ant Design Switch组件，默认关闭状态）。
        6. **【V1.2新增】** 用户可选择开启该开关。开关下方显示说明文案："开启后，系统将自动判断输出正确性并计算准确率"。
        7. 所有必填项完成后，"创建任务"按钮激活。
        8. 点击"创建任务"后，系统创建评测任务记录，并将`enable_correction`字段设置为开关状态（true/false）。
        9. 页面跳转至任务列表页（`/tasks`）。
    3.  **异常处理 (Error Handling)**:
        *   矫正功能的开关状态不影响任务创建的表单验证逻辑。
        *   若后端环境变量缺少`ZHIPU_API_KEY`，任务仍可创建成功，但在执行矫正时会记录错误（详见阶段二）。
        *   前端表单验证逻辑与V1.0保持一致（任务名称、API URL、数据集文件的验证规则不变）。
    4.  **性能与容量提示**: 开关状态仅影响任务元数据，不涉及大数据量操作；创建请求响应时间与V1.0一致。

*   **验收标准 (Acceptance Criteria)**:
    *   **场景1: 创建带矫正的任务**
        *   **GIVEN** 我填写了任务名称、API URL、上传了CSV文件，并开启了"启用模型矫正"开关
        *   **WHEN** 我点击"创建任务"按钮
        *   **THEN** 页面应跳转到任务列表页，我能看到刚创建的任务，任务列表页显示"准确率"列（此时显示 `-` 或 `等待中`）
    *   **场景2: 创建普通任务（不带矫正）**
        *   **GIVEN** 我填写了所有必填信息，但保持"启用模型矫正"开关为关闭状态
        *   **WHEN** 我点击"创建任务"按钮
        *   **THEN** 页面跳转到任务列表页，该任务的"准确率"列显示 `-`
    *   **场景3: 开关状态的视觉反馈**
        *   **GIVEN** 我在创建任务页面
        *   **WHEN** 我点击"启用模型矫正"开关
        *   **THEN** 开关应从"关闭"状态切换为"开启"状态，视觉上有明确的颜色/位置变化（Ant Design Switch的默认行为）

---

*   **技术实现概要 (Technical Implementation Brief)**:
    *   **影响范围**: Web前端创建任务页面（`/`）；后端 `POST /api/v1/evaluation-tasks` 接口；数据库 `evaluation_tasks` 表结构。

    *   **前端 / 客户端 (Frontend / Client)**:
        *   **新增表单字段**：
            - 字段名：`enableCorrection`（boolean）
            - UI组件：Ant Design `<Switch>` 组件
            - 默认值：`false`
            - 标签文本："启用模型矫正"
            - 说明文案："开启后，系统将自动判断输出正确性并计算准确率"（灰色小字，放在开关下方）
        *   **表单布局调整**：
            - 将"启用模型矫正"开关放在"测试数据集"上传控件的下方
            - 开关与其他表单项保持一致的左对齐和间距
        *   **API调用调整**：
            - 在原有的 `FormData` 中增加 `enable_correction` 字段（boolean）
            - 示例代码：
            ```typescript
            const formData = new FormData();
            formData.append('task_name', taskName);
            formData.append('agent_api_url', apiUrl);
            formData.append('dataset_file', file);
            formData.append('enable_correction', enableCorrection.toString()); // "true" or "false"

            axios.post('/api/v1/evaluation-tasks', formData, {
              headers: { 'Content-Type': 'multipart/form-data' }
            });
            ```
        *   **状态管理**：
            - 使用 React `useState` 管理开关状态
            - 示例：`const [enableCorrection, setEnableCorrection] = useState(false);`

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
        |  启用模型矫正:  [ O━━━ ]  关闭                                           |
        |  (开启后，系统将自动判断输出正确性并计算准确率)                          |
        |                                                                          |
        |  +----------------------------------------------------------------------+  |
        |  |                                                        [ 创建任务 ]  |  |
        |  +----------------------------------------------------------------------+  |
        |                                                                          |
        +--------------------------------------------------------------------------+
        ```

    *   **后端 (Backend)**:
        *   **接口调整**：`POST /api/v1/evaluation-tasks`
            - 新增可选字段：`enable_correction`（boolean，默认 `false`）
            - 请求示例：
            ```
            Content-Type: multipart/form-data

            task_name: "A模型V1.2稳定性测试"
            agent_api_url: "http://..."
            dataset_file: <binary>
            enable_correction: "true"
            ```
        *   **数据库操作**：
            - 创建任务时，将 `enable_correction` 字段写入 `evaluation_tasks` 表
            - 初始化 `accuracy_rate` 为 `null`，`passed_count` 为 `0`
        *   **响应体调整**：
            - 成功响应增加 `enable_correction` 字段：
            ```json
            {
              "task_id": "6f0d3c1e-3f68-4b5a-9f5c-5e4d2f7d2f11",
              "status": "PENDING",
              "enable_correction": true
            }
            ```

    *   **数据库 / 存储 (Database / Storage)**:
        *   **修改 `evaluation_tasks` 表**（通过 Alembic 迁移脚本）：
            - 新增字段：
                - `enable_correction` (BOOLEAN, NOT NULL, DEFAULT FALSE) - 是否启用矫正
                - `accuracy_rate` (FLOAT, NULLABLE) - 任务准确率（0-100），未完成时为 NULL
                - `passed_count` (INTEGER, DEFAULT 0) - 通过的问题数

*   **数据模型 / 接口契约 (Data Contracts & APIs)**:
    *   **`POST /api/v1/evaluation-tasks` 请求字段新增**：
        - `enable_correction` (boolean, 可选, 默认 `false`) - 是否启用模型矫正
    *   **响应体新增字段**：
        - `enable_correction` (boolean) - 是否启用矫正
    *   **数据库表 `evaluation_tasks` 新增列**：
        | 列名 | 类型 | 约束 | 说明 |
        |------|------|------|------|
        | enable_correction | BOOLEAN | NOT NULL, DEFAULT FALSE | 是否启用模型矫正 |
        | accuracy_rate | FLOAT | NULLABLE | 任务准确率（0-100），任务未完成时为 NULL |
        | passed_count | INTEGER | NOT NULL, DEFAULT 0 | 通过的问题数（5次全对） |

*   **监控与运营 (Observability & Operations)**:
    *   前端埋点：记录用户开启矫正开关的频率（事件名：`correction_enabled`，携带 `task_id`）。
    *   后端日志：任务创建时记录 `enable_correction` 字段值，便于统计矫正功能的采用率。

*   **约束与边界 (Constraints & Boundaries)**:
    *   矫正功能仅支持智谱GLM-4.6模型，不支持用户自定义矫正模型（V1.2范围限制）。
    *   开关状态在任务创建后不可修改（后续版本可扩展"编辑任务"功能）。

*   **非功能性需求 (Non-Functional)**:
    *   表单响应时间：开关切换反馈应在100ms内完成。
    *   数据库迁移：Alembic迁移脚本需支持向下兼容（新增列设置默认值，不影响已有数据）。

*   **开放问题与待确认事项 (Open Questions & Follow-ups)**:
    *   矫正功能是否需要在任务列表页通过标签或图标明确标识？（责任人：产品，答复截止：讨论阶段二前）
    *   是否需要在任务详情页显示"矫正模型"信息（如"使用GLM-4.6进行矫正"）？（责任人：产品，答复截止：讨论阶段三前）

---

### 阶段二：执行与监控任务

---

#### **US-02（V1.2新增）: 作为评测系统，我希望在每个问题的5次调用完成后自动执行矫正逻辑，以便于为用户提供准确率统计。**

*   **价值陈述 (Value Statement)**:
    *   **作为** 评测系统
    *   **我希望** 在每个问题的5次调用完成后，自动调用矫正模型判断正确性
    *   **以便于** 为用户提供准确率统计，减少人工审核工作

*   **业务规则与逻辑 (Business Logic)**:
    1.  **前置条件**: 任务的 `enable_correction` 字段为 `true`；后端已配置 `ZHIPU_API_KEY`；5次智能体调用已全部完成。
    2.  **操作流程 (Happy Path)**:
        1. Celery Worker 完成某个问题的5次智能体调用，将结果写入 `evaluation_runs` 表。
        2. Worker 检测到任务启用了矫正功能（`enable_correction=true`）。
        3. Worker 依次对这5次调用结果执行矫正：
            - 读取 `evaluation_runs` 中该问题的5条记录（`run_index` 1-5）
            - 对每条记录，提取 `response_body`（智能体输出）
            - 从 `evaluation_items` 表读取对应的 `question` 和 `standard_answer`
            - 调用智谱 GLM-4.6 模型，发送矫正 Prompt（见下文）
            - 解析模型返回的 JSON：`{"is_correct": true/false, "reason": "..."}`
            - 将矫正结果写入 `evaluation_runs` 表的对应字段：
                - `correction_result` = `is_correct` 的值
                - `correction_reason` = `reason` 的值
                - `correction_status` = `"SUCCESS"`
                - `correction_retries` = 实际重试次数（0-3）
        4. 完成该问题的5次矫正后，判断该问题是否通过：
            - 如果5次矫正结果全部为 `true`，则 `evaluation_items.is_passed = true`
            - 否则，`evaluation_items.is_passed = false`
        5. 继续处理下一个问题，重复步骤3-4。
        6. **所有问题矫正完成后**，一次性计算任务准确率：
            - `passed_count` = `evaluation_items` 表中 `is_passed=true` 的记录数
            - `accuracy_rate` = `(passed_count / total_items) * 100`（保留1位小数）
            - 更新 `evaluation_tasks` 表的 `passed_count` 和 `accuracy_rate` 字段
        7. 任务状态流转为 `SUCCEEDED`。
    3.  **异常处理 (Error Handling)**:
        *   **矫正API调用失败**（网络超时、HTTP 5xx等）：
            - 立即重试，最多重试 3 次（由 `CORRECTION_MAX_RETRIES` 配置）
            - 每次重试间隔采用指数退避（1s, 2s, 4s）
            - 3次重试后仍失败，记录：
                - `correction_status` = `"FAILED"`
                - `correction_error_message` = 错误详情（如 `"Timeout after 30s"`）
                - `correction_result` = `null`
                - `correction_reason` = `null`
        *   **矫正返回JSON格式错误**（无法解析为 `{is_correct, reason}` 结构）：
            - 记录为矫正失败，`correction_status` = `"FAILED"`
            - `correction_error_message` = `"Invalid JSON format"`
        *   **问题包含矫正失败的运行**：
            - 该问题直接判定为"不通过"
            - `evaluation_items.is_passed` = `false`
            - 在前端显示时标记为"不通过（矫正失败）"
        *   **环境变量缺失 `ZHIPU_API_KEY`**：
            - 任务在执行矫正时抛出配置错误
            - 记录日志：`"ZHIPU_API_KEY not configured, skipping correction"`
            - 所有矫正标记为 `"SKIPPED"`
            - 任务仍流转为 `SUCCEEDED`，准确率按0%计算
    4.  **性能与容量提示**:
        - 矫正调用与智能体调用串行执行（先完成5次智能体调用，再执行5次矫正）
        - 单次矫正平均耗时约 1-3秒（取决于智谱API响应速度）
        - 对于100个问题的任务，矫正总耗时约 500次调用 × 2秒 = 16-17分钟
        - 后续可通过并行化矫正调用优化性能（V1.3考虑）

*   **验收标准 (Acceptance Criteria)**:
    *   **场景1: 成功执行矫正并计算准确率**
        *   **GIVEN** 一个启用了矫正的任务，包含10个问题
        *   **WHEN** 所有50次智能体调用完成后，系统执行矫正逻辑
        *   **THEN** 系统应成功调用矫正模型50次，将结果写入数据库，并计算出准确率（如 `80.0%`），更新 `evaluation_tasks` 表
    *   **场景2: 矫正API超时重试**
        *   **GIVEN** 某次矫正调用因网络波动超时
        *   **WHEN** 系统检测到超时
        *   **THEN** 系统应自动重试最多3次，若最终成功则记录结果，若失败则标记为 `FAILED`
    *   **场景3: 问题级别的通过判定**
        *   **GIVEN** 某问题的5次矫正结果为 `[true, true, true, true, false]`
        *   **WHEN** 系统判断该问题是否通过
        *   **THEN** 该问题应标记为"不通过"（`is_passed=false`）
    *   **场景4: 矫正失败视为不通过**
        *   **GIVEN** 某问题的5次矫正因API故障全部失败
        *   **WHEN** 任务继续执行
        *   **THEN** 该问题在数据库中标记为 `is_passed=false`，任务准确率统计将其视为不通过

---

*   **技术实现概要 (Technical Implementation Brief)**:
    *   **影响范围**: 后端 Celery Worker（`app/services/evaluation_task.py`）；数据库 `evaluation_runs` 和 `evaluation_items` 表。

    *   **后端 (Backend)**:
        *   **矫正Prompt模板**（存储在 `app/prompts/correction_prompt.txt`）：
            ```text
            你是一个严格的答案评判专家。请判断【智能体输出】是否与【标准答案】在语义上一致。

            **评判规则：**
            1. 如果智能体输出的核心信息与标准答案一致或完全包含标准答案，判定为"正确"
            2. 如果智能体输出包含错误信息、遗漏关键信息，或与标准答案矛盾，判定为"错误"
            3. 允许表述方式、语气、长度的合理差异，只关注核心语义是否正确

            **输入信息：**
            - 问题：{question}
            - 标准答案：{standard_answer}
            - 智能体输出：{agent_output}

            **输出要求：**
            必须返回严格的JSON格式，不要有任何额外说明：
            {{
              "is_correct": true,  // 或 false
              "reason": "简短说明判断理由（30字以内）"
            }}
            ```
        *   **矫正服务实现**（新增 `app/services/correction_service.py`）：
            - 函数：`async def correct_output(question: str, standard_answer: str, agent_output: str) -> CorrectionResult`
            - 使用 `zai-sdk` 调用智谱 GLM-4.6
            - 模型参数：
                - `model`: 从环境变量 `CORRECTION_MODEL_ID` 读取（默认 `"glm-4.6"`）
                - `temperature`: 从环境变量 `CORRECTION_TEMPERATURE` 读取（默认 `0.3`）
                - `max_tokens`: 从环境变量 `CORRECTION_MAX_TOKENS` 读取（默认 `512`）
            - 超时控制：从环境变量 `CORRECTION_TIMEOUT_SECONDS` 读取（默认 `30`）
            - 重试逻辑：使用 `tenacity` 库实现指数退避重试
        *   **Celery任务调整**（修改 `app/services/evaluation_task.py`）：
            - 在 `run_evaluation_task` 函数中，每完成一个问题的5次调用后，检查 `enable_correction`
            - 若为 `true`，调用 `correction_service.correct_all_runs(item_id)`
            - 所有问题处理完成后，调用 `calculate_task_accuracy(task_id)`
        *   **准确率计算函数**（新增 `app/services/accuracy_calculator.py`）：
            ```python
            def calculate_task_accuracy(task_id: str) -> float:
                # 查询当前任务的全部问题
                total = count(evaluation_items WHERE task_id=task_id)
                passed = count(evaluation_items WHERE task_id=task_id AND is_passed=true)
                accuracy = (passed / total * 100) if total > 0 else 0.0
                # 更新 evaluation_tasks 表
                UPDATE evaluation_tasks SET accuracy_rate=accuracy, passed_count=passed WHERE id=task_id
                return accuracy
            ```

    *   **数据库 / 存储 (Database / Storage)**:
        *   **修改 `evaluation_runs` 表**（通过 Alembic 迁移脚本）：
            | 列名 | 类型 | 约束 | 说明 |
            |------|------|------|------|
            | correction_result | BOOLEAN | NULLABLE | 矫正结果：true(正确) / false(错误) / null(未矫正或失败) |
            | correction_reason | TEXT | NULLABLE | 矫正原因（来自模型返回的reason字段） |
            | correction_status | VARCHAR(20) | DEFAULT 'PENDING' | 矫正状态：SUCCESS / FAILED / PENDING / SKIPPED |
            | correction_retries | INTEGER | DEFAULT 0 | 重试次数（0-3） |
            | correction_error_message | TEXT | NULLABLE | 矫正失败时的错误信息 |
        *   **修改 `evaluation_items` 表**：
            | 列名 | 类型 | 约束 | 说明 |
            |------|------|------|------|
            | is_passed | BOOLEAN | NULLABLE | 该问题是否通过（5次全对为true，存在错误/矫正失败为false，运行中为null） |

*   **数据模型 / 接口契约 (Data Contracts & APIs)**:
    *   **矫正服务输入**：
        ```python
        class CorrectionInput:
            question: str
            standard_answer: str
            agent_output: str
        ```
    *   **矫正服务输出**：
        ```python
        class CorrectionResult:
            is_correct: bool
            reason: str
            status: str  # "SUCCESS" / "FAILED"
            error_message: Optional[str]
        ```
    *   **准确率计算输出**：
        ```python
        class AccuracyResult:
            accuracy_rate: float  # 0-100
            passed_count: int
            failed_count: int
            failed_due_to_correction_count: int
            total_count: int
        ```

*   **监控与运营 (Observability & Operations)**:
    *   后端日志：记录每次矫正调用的耗时、结果、重试次数（事件名：`correction_executed`）。
    *   Prometheus 指标：
        - `correction_call_latency_ms`（矫正调用耗时）
        - `correction_call_failure_total`（矫正失败次数）
        - `correction_retry_total`（重试总次数）
    *   异常告警：当单个任务的矫正失败率 >20% 时，发送告警通知运维。

*   **约束与边界 (Constraints & Boundaries)**:
    *   矫正调用与智能体调用串行执行，不支持并行（V1.2限制）。
    *   单次矫正超时时间默认30秒，不可超过60秒（受智谱API限制）。
    *   矫正Prompt在V1.2版本写死在代码中，后续可扩展为可配置（V1.3考虑）。

*   **非功能性需求 (Non-Functional)**:
    *   矫正调用平均响应时间应 ≤3秒（P95）。
    *   重试间隔采用指数退避策略，避免频繁请求导致API限流。
    *   所有矫正调用必须记录完整日志（请求参数、响应内容、耗时），便于问题排查。

*   **开放问题与待确认事项 (Open Questions & Follow-ups)**:
    *   矫正Prompt是否需要支持用户自定义？（责任人：产品，答复截止：V1.3规划前）
    *   是否需要在任务详情页显示每个问题的矫正耗时？（责任人：产品，答复截止：讨论阶段三前）

---

#### **US-03（V1.2增强）: 作为评测任务发起人，我希望在任务列表页能看到每个任务的准确率，以便于快速评估任务的整体表现。**

*   **价值陈述 (Value Statement)**:
    *   **作为** 评测任务发起人
    *   **我希望** 在任务列表页能看到每个任务的准确率
    *   **以便于** 快速评估任务的整体表现，无需逐个点击查看详情

*   **业务规则与逻辑 (Business Logic)**:
    1.  **前置条件**: 用户已进入任务列表页（`/tasks`）；任务列表API已返回数据。
    2.  **操作流程 (Happy Path)**:
        1. 用户访问任务列表页（`/tasks`）。
        2. 前端调用 `GET /api/v1/evaluation-tasks` 获取任务列表数据。
        3. 后端返回的每个任务对象包含 `enable_correction` 和 `accuracy_rate` 字段。
        4. 前端在表格中渲染"准确率"列：
            - 若 `enable_correction=false`，显示 `-`
            - 若 `enable_correction=true` 且 `status=PENDING`，显示 `-`
            - 若 `enable_correction=true` 且 `status=RUNNING`，显示 `计算中..`
            - 若 `enable_correction=true` 且 `status=SUCCEEDED`，显示准确率（如 `85.5%`，若全部未通过则显示 `0.0%`）
            - 若 `enable_correction=true` 且 `status=FAILED`，显示 `-`
        5. 用户可点击表格行的"查看"按钮进入详情页。
    3.  **异常处理 (Error Handling)**:
        *   API调用失败时，显示 Ant Design Message 错误提示："加载任务列表失败，请刷新重试"。
        *   网络错误时提示："网络连接失败，请检查网络后重试"。
    4.  **性能与容量提示**: 准确率列不增加额外API调用，数据随任务列表一次性返回。

*   **验收标准 (Acceptance Criteria)**:
    *   **场景1: 带矫正的已完成任务显示准确率**
        *   **GIVEN** 任务列表中有一个启用了矫正且已完成的任务，准确率为 `85.5%`
        *   **WHEN** 我访问任务列表页
        *   **THEN** 该任务的"准确率"列应显示 `85.5%`
    *   **场景2: 不带矫正的任务显示横线**
        *   **GIVEN** 任务列表中有一个未启用矫正的任务
        *   **WHEN** 我访问任务列表页
        *   **THEN** 该任务的"准确率"列应显示 `-`
    *   **场景3: 运行中任务显示计算状态**
        *   **GIVEN** 任务列表中有一个启用了矫正且正在运行的任务
        *   **WHEN** 我访问任务列表页
        *   **THEN** 该任务的"准确率"列应显示 `计算中..`
    *   **场景4: 列宽适配和对齐**
        *   **GIVEN** 任务列表页加载完成
        *   **WHEN** 我查看表格
        *   **THEN** "准确率"列宽度为100px，内容居中对齐，与其他列保持视觉一致

---

*   **技术实现概要 (Technical Implementation Brief)**:
    *   **影响范围**: Web前端任务列表页（`/tasks`）；后端 `GET /api/v1/evaluation-tasks` 接口返回数据调整。

    *   **前端 / 客户端 (Frontend / Client)**:
        *   **表格列配置调整**（修改 `src/pages/TaskList/index.tsx`）：
            ```typescript
            const columns = [
              { title: '状态', dataIndex: 'status', width: 100, ... },
              { title: '任务名称', dataIndex: 'task_name', flex: 1, ... },
              { title: '创建时间', dataIndex: 'created_at', width: 180, ... },
              { title: '完成时间', dataIndex: 'completed_at', width: 180, ... },
              { title: '耗时(分钟)', dataIndex: 'duration_minutes', width: 110, ... },
              { title: '进度', dataIndex: 'progress', width: 100, ... },
              {
                title: '准确率',
                dataIndex: 'accuracy_rate',
                width: 100,
                align: 'center',
                render: (text, record) => {
                  if (!record.enable_correction) return '-';
                  if (record.status === 'PENDING') return '-';
                  if (record.status === 'RUNNING') return '计算中..';
                  if (record.status === 'SUCCEEDED') {
                    return `${record.accuracy_rate.toFixed(1)}%`;
                  }
                  return '-';
                }
              },
              { title: '操作', width: 100, ... }
            ];
            ```
        *   **类型定义更新**（修改 `src/types/task.ts`）：
            ```typescript
            interface EvaluationTask {
              task_id: string;
              task_name: string;
              status: 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED';
              enable_correction: boolean;  // 新增
              accuracy_rate: number; // 新增
              progress: { processed: number; total: number };
              created_at: string;
              completed_at: string | null;
              duration_minutes: number | null;
            }
            ```

    *   **页面布局线框图 (ASCII Wireframe)**:
        ```text
        +---------------------------------------------------------------------------------------------------------------------+
        | 我的评测任务                                                                              [刷新] [+ 创建新任务]      |
        +---------------------------------------------------------------------------------------------------------------------+
        |                                                                                                                     |
        | +--------+-------------+-------------------+-------------------+-----------+--------+----------+---------+         |
        | | 状态   | 任务名称    | 创建时间          | 完成时间          | 耗时(分钟)| 进度   | 准确率   | 操作    |         |
        | +--------+-------------+-------------------+-------------------+-----------+--------+----------+---------+         |
        | | 已完成 | A模型V1.2   | 2025-10-27 10:30  | 2025-10-27 10:35  | 5.2       | 100/100| 85.5%    | [查看]  |         |
        | | 运行中 | B模型最终   | 2025-10-27 10:25  | -                 | -         | 75/150 | 计算中.. | (查看)  |         |
        | | 已完成 | C模型无矫正 | 2025-10-27 10:20  | 2025-10-27 10:21  | 0.8       | 50/50  | -        | [查看]  |         |
        | | 等待中 | D模型回归   | 2025-10-27 10:15  | -                 | -         | 0/200  | -        | (查看)  |         |
        | +--------+-------------+-------------------+-------------------+-----------+--------+----------+---------+         |
        |                                                                                                                     |
        |                                                          << 上一页 | 第 1 页 | 下一页 >>                            |
        |                                                                                                                     |
        +---------------------------------------------------------------------------------------------------------------------+
        ```

    *   **后端 (Backend)**:
        *   **接口调整**：`GET /api/v1/evaluation-tasks`
            - 响应体新增字段：`enable_correction` 和 `accuracy_rate`
            - 示例响应：
            ```json
            {
              "items": [
                {
                  "task_id": "uuid",
                  "task_name": "A模型V1.2稳定性测试",
                  "status": "SUCCEEDED",
                  "enable_correction": true,
                  "accuracy_rate": 85.5,
                  "progress": {"processed": 100, "total": 100},
                  "created_at": "2025-10-27T10:30:00+08:00",
                  "completed_at": "2025-10-27T10:35:00+08:00",
                  "duration_minutes": 5.2
                }
              ],
              "pagination": {"page": 1, "page_size": 20, "total": 4}
            }
            ```

*   **数据模型 / 接口契约 (Data Contracts & APIs)**:
    *   **`GET /api/v1/evaluation-tasks` 响应体新增字段**：
        - `enable_correction` (boolean) - 是否启用矫正
        - `accuracy_rate` (float | null) - 任务准确率（0-100），未完成时为 null

*   **监控与运营 (Observability & Operations)**:
    *   前端埋点：记录用户查看任务列表的频率和停留时长。

*   **约束与边界 (Constraints & Boundaries)**:
    *   准确率保留1位小数（如 `85.5%`），不显示更多精度。
    *   "计算中.."状态仅在 `RUNNING` 时显示，不支持更细粒度的进度提示（如"矫正中 50/100"）。

*   **非功能性需求 (Non-Functional)**:
    *   表格渲染性能：1000条记录下渲染时间应 ≤500ms。
    *   准确率数字格式化应使用 `toFixed(1)` 确保一致性。

*   **开放问题与待确认事项 (Open Questions & Follow-ups)**:
    *   是否需要在准确率列增加筛选功能（如"仅显示准确率<80%的任务"）？（责任人：产品，答复截止：V1.3规划前）

---

### 阶段三：查看评测结果

---

#### **US-04（V1.2增强）: 作为评测审核人，我希望在结果详情页能看到每次输出的矫正结果和准确率统计，以便于快速评估智能体的稳定性表现。**

*   **价值陈述 (Value Statement)**:
    *   **作为** 评测审核人
    *   **我希望** 在结果详情页能看到每次输出的矫正结果（正确/错误）、矫正原因以及任务级准确率统计
    *   **以便于** 快速评估智能体的稳定性表现，无需人工逐条对比标准答案

*   **业务规则与逻辑 (Business Logic)**:
    1.  **前置条件**: 用户在任务列表页点击了"已完成"状态的任务的"查看"按钮；任务已启用矫正功能（`enable_correction=true`）。
    2.  **操作流程 (Happy Path)**:
        1. 用户从任务列表页点击"查看"按钮，进入结果详情页（路径：`/tasks/:taskId/results`）。
        2. 前端调用 `GET /api/v1/evaluation-tasks/:taskId/results?page=1&page_size=20` 获取评测结果数据。
        3. 后端返回数据包含：
            - 任务元信息（任务名称、准确率、通过题数、未通过题数、其中矫正失败的题数）
            - 当前页的问题列表（每个问题包含5次运行结果，每次运行包含矫正结果和原因）
        4. 页面顶部显示任务级统计：
            - 任务准确率（如 `85.5%`）
            - 通过题数与未通过题数（可附加展示"其中矫正失败X题"）
        5. 主体区域按问题展示评测结果：
            - 问题编号、问题文本、标准答案
            - 5次运行结果，每次运行包含：
                - **【模块1：输出内容】**：智能体的原始输出（支持超长文本折叠）+ 耗时
                - **【模块2：矫正结果】**：✅/❌ 图标 + "正确/错误" 文字 + reason 原因说明
            - 问题底部显示该问题的最终判定：
                - 🟢 通过（5次全部正确）
                - 🔴 不通过（存在错误或矫正失败时文案注明原因）
        6. 用户可点击"导出CSV"按钮下载完整报告。
    3.  **异常处理 (Error Handling)**:
        *   若任务未完成（HTTP 409），显示提示："任务尚未完成，请稍后查看"。
        *   若任务未启用矫正，页面回退到V1.0版本的展示方式（不显示矫正结果和准确率统计）。
        *   若加载失败（HTTP 500/网络错误），显示："加载评测结果失败，请刷新重试"。
        *   若某次运行的矫正状态为 `FAILED`，矫正结果模块显示：`⚠️ 矫正失败: [错误信息]`。
    4.  **性能与容量提示**:
        - 支持分页加载，默认每页20个问题，避免一次性加载大量数据。
        - 超长文本默认折叠（显示前200字符），点击"展开"后显示完整内容。

*   **验收标准 (Acceptance Criteria)**:
    *   **场景1: 成功加载带矫正的结果页面**
        *   **GIVEN** 我在任务列表页点击了一个启用矫正且已完成的任务
        *   **WHEN** 结果详情页加载完成
        *   **THEN** 页面顶部应显示任务准确率（如 `85.5%`）和题数分布，主体区域显示每个问题的5次运行结果，每次运行包含"输出内容"和"矫正结果"两个独立模块
    *   **场景2: 矫正结果的展示**
        *   **GIVEN** 某次运行的矫正结果为"正确"，reason为"核心信息与标准答案一致"
        *   **WHEN** 我查看该运行结果
        *   **THEN** 矫正结果模块应显示：`✅ 正确` + `原因: 核心信息与标准答案一致`
    *   **场景3: 问题级判定的展示**
        *   **GIVEN** 某问题的5次矫正结果为 `[true, true, true, true, false]`
        *   **WHEN** 我查看该问题
        *   **THEN** 问题底部应显示：`🔴 本题判定: 不通过 (5次中有1次错误)`
    *   **场景4: 矫正失败的处理**
        *   **GIVEN** 某次运行的矫正状态为 `FAILED`，错误信息为 `"Timeout after 30s"`
        *   **WHEN** 我查看该运行结果
        *   **THEN** 矫正结果模块应显示：`⚠️ 矫正失败: Timeout after 30s`
    *   **场景5: 普通任务（未启用矫正）的兼容性**
        *   **GIVEN** 我查看一个未启用矫正的任务
        *   **WHEN** 结果详情页加载完成
        *   **THEN** 页面应回退到V1.0版本的展示方式，不显示矫正结果和准确率统计

---

*   **技术实现概要 (Technical Implementation Brief)**:
    *   **影响范围**: Web前端结果详情页（`/tasks/:taskId/results`）；后端 `GET /api/v1/evaluation-tasks/:taskId/results` 接口返回数据调整。

    *   **前端 / 客户端 (Frontend / Client)**:
        *   **页面结构调整**（修改 `src/pages/TaskResults/index.tsx`）：
            - **顶部统计区域**：新增组件 `<AccuracyStatistics>`，显示任务准确率和题数分布
            - **问题列表区域**：修改现有的问题卡片组件
                - 每次运行结果拆分为两个子组件：
                    - `<OutputContent>` - 显示智能体输出和耗时
                    - `<CorrectionResult>` - 显示矫正结果和原因
                - 问题底部新增 `<QuestionVerdict>` 组件，显示问题级判定
        *   **组件设计**：
            ```typescript
            // 顶部统计组件
            interface AccuracyStatisticsProps {
              taskName: string;
              accuracyRate: number;
              passedCount: number;
              failedCount: number;
              failedDueToCorrectionCount?: number;
              totalCount: number;
            }

            // 矫正结果组件
            interface CorrectionResultProps {
              status: 'SUCCESS' | 'FAILED';
              isCorrect: boolean | null;
              reason: string | null;
              errorMessage: string | null;
            }

            // 问题判定组件
            interface QuestionVerdictProps {
              isPassed: boolean;
              correctCount: number;
              totalCount: number;
              failedReason?: string; // 可选，展示“矫正失败”“答案错误”等提示
            }
            ```
        *   **条件渲染逻辑**：
            - 若 `task.enable_correction === false`，不显示矫正相关组件
            - 若 `run.correction_status === 'SUCCESS'`，显示正常的矫正结果
            - 若 `run.correction_status === 'FAILED'`，显示矫正失败提示
            - 若 `run.correction_status === 'SKIPPED'`，显示"未启用矫正"
        *   **样式规范**：
            - ✅ 正确：使用绿色图标和文字（Ant Design `<CheckCircleFilled>` 图标，颜色 `#52c41a`）
            - ❌ 错误：使用红色图标和文字（Ant Design `<CloseCircleFilled>` 图标，颜色 `#ff4d4f`）
            - ⚠️ 矫正失败：用于运行级别提示，颜色 `#faad14`
            - 问题判定使用 Ant Design `<Alert>` 组件：
                - 通过：`type="success"` 绿色背景
                - 不通过：`type="error"` 红色背景（包含矫正失败场景）

    *   **页面布局线框图 (ASCII Wireframe)**:
        ```text
        +------------------------------------------------------------------------------------+
        | 评测报告: [A模型V1.2稳定性测试]                                                    |
        | 📊 任务准确率: 85.5% (120题中有102题通过)                                          |
        |    • 通过: 102题 (5次全对)                                                         |
        |    • 未通过: 18题 (包含矫正失败 3 题)                                              |
        +====================================================================================+
        |                                                      [导出CSV]  [返回列表]        |
        +------------------------------------------------------------------------------------+
        |                                                                                    |
        |  +------------------------------------------------------------------------------+  |
        |  | 问题 #1: "中国的首都是哪里？"                                                |  |
        |  | 标准答案: "北京"                                                             |  |
        |  +------------------------------------------------------------------------------+  |
        |  |                                                                              |  |
        |  | 【运行 #1】 812ms                                                            |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  | | 输出内容:                                                                | |  |
        |  | | 北京是中国的首都。                                                       | |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  | | 矫正结果: ✅ 正确                                                        | |  |
        |  | | 原因: 核心信息与标准答案一致                                             | |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  |                                                                              |  |
        |  | 【运行 #2】 756ms                                                            |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  | | 输出内容:                                                                | |  |
        |  | | 中华人民共和国的首都是北京。                                             | |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  | | 矫正结果: ✅ 正确                                                        | |  |
        |  | | 原因: 表述完整，语义正确                                                 | |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  |                                                                              |  |
        |  | 【运行 #3】 654ms                                                            |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  | | 输出内容:                                                                | |  |
        |  | | 北京                                                                     | |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  | | 矫正结果: ✅ 正确                                                        | |  |
        |  | | 原因: 与标准答案完全一致                                                 | |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  |                                                                              |  |
        |  | 【运行 #4】 30000ms                                                          |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  | | 输出内容:                                                                | |  |
        |  | | ❌ TIMEOUT_ERROR: Agent request timed out after 30s                     | |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  | | 矫正结果: ❌ 错误                                                        | |  |
        |  | | 原因: 调用超时，无有效输出                                               | |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  |                                                                              |  |
        |  | 【运行 #5】 890ms                                                            |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  | | 输出内容:                                                                | |  |
        |  | | 北京，也被称为... [展开]                                                 | |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  | | 矫正结果: ✅ 正确                                                        | |  |
        |  | | 原因: 包含标准答案核心信息                                               | |  |
        |  | +--------------------------------------------------------------------------+ |  |
        |  |                                                                              |  |
        |  | 🔴 本题判定: 不通过 (5次中有1次错误)                                        |  |
        |  +------------------------------------------------------------------------------+  |
        |                                                                                    |
        |  +------------------------------------------------------------------------------+  |
        |  | 问题 #2: "上海的别称是什么？"                                                |  |
        |  | 标准答案: "申城、魔都"                                                       |  |
        |  | ... (5次运行结果)                                                            |  |
        |  | ✅ 本题判定: 通过 (5次全部正确)                                              |  |
        |  +------------------------------------------------------------------------------+  |
        |                                                                                    |
        |                             << 上一页 | 第 1 页 / 共 6 页 | 下一页 >>              |
        |                                                                                    |
        +------------------------------------------------------------------------------------+
        ```

    *   **后端 (Backend)**:
        *   **接口调整**：`GET /api/v1/evaluation-tasks/:taskId/results`
            - 响应体新增任务级统计字段
            - 每个运行结果增加矫正相关字段
            - 示例响应：
            ```json
            {
              "task": {
                "task_id": "uuid",
                "task_name": "A模型V1.2稳定性测试",
                "status": "SUCCEEDED",
                "enable_correction": true,
                "accuracy_rate": 85.5,
                "passed_count": 102,
                "failed_count": 18,
                "failed_due_to_correction_count": 3,
                "total_items": 120
              },
              "items": [
                {
                  "question_id": "Q0001",
                  "question": "中国的首都是哪里？",
                  "standard_answer": "北京",
                  "is_passed": false,
                  "runs": [
                    {
                      "run_index": 1,
                      "status": "SUCCEEDED",
                      "response_body": "北京是中国的首都。",
                      "latency_ms": 812,
                      "correction_status": "SUCCESS",
                      "correction_result": true,
                      "correction_reason": "核心信息与标准答案一致",
                      "created_at": "2025-10-27T10:31:12+08:00"
                    },
                    {
                      "run_index": 4,
                      "status": "FAILED",
                      "response_body": null,
                      "latency_ms": 30000,
                      "error_code": "TIMEOUT",
                      "correction_status": "SUCCESS",
                      "correction_result": false,
                      "correction_reason": "调用超时，无有效输出",
                      "created_at": "2025-10-27T10:32:45+08:00"
                    }
                  ]
                }
              ],
              "pagination": {"page": 1, "page_size": 20, "total": 120}
            }
            ```

*   **数据模型 / 接口契约 (Data Contracts & APIs)**:
    *   **`GET /api/v1/evaluation-tasks/:taskId/results` 响应体调整**：
        - **task 对象新增字段**：
            - `enable_correction` (boolean) - 是否启用矫正
            - `accuracy_rate` (float | null) - 任务准确率（0-100）
            - `passed_count` (int) - 通过的题数（5次全对）
            - `failed_count` (int) - 未通过的题数
            - `failed_due_to_correction_count` (int) - 因矫正失败导致未通过的题数
        - **items[].is_passed** (boolean) - 该问题是否通过
        - **items[].runs[] 新增字段**：
            - `correction_status` (string) - 矫正状态：SUCCESS / FAILED / PENDING / SKIPPED
            - `correction_result` (boolean | null) - 矫正结果：true(正确) / false(错误) / null
            - `correction_reason` (string | null) - 矫正原因
            - `correction_error_message` (string | null) - 矫正失败时的错误信息

*   **监控与运营 (Observability & Operations)**:
    *   前端埋点：记录用户查看结果详情页的频率、停留时长、是否展开超长文本。

*   **约束与边界 (Constraints & Boundaries)**:
    *   矫正原因（reason）最大显示长度为100字符，超出部分截断并显示省略号。
    *   问题级判定仅依赖5次矫正结果的逻辑判断，不支持自定义判定规则。

*   **非功能性需求 (Non-Functional)**:
    *   首屏加载时间应 ≤2秒（包含顶部统计和第1页的20个问题）。
    *   分页切换时间应 ≤1秒。
    *   超长文本折叠/展开操作响应时间应 ≤100ms。

*   **开放问题与待确认事项 (Open Questions & Follow-ups)**:
    *   是否需要支持按"通过/不通过"筛选问题？（责任人：产品，答复截止：V1.3规划前）
    *   是否需要在顶部统计区域增加图表（如准确率饼图）？（责任人：设计，答复截止：V1.3规划前）

---

### 阶段四：导出评测报告

---

#### **US-05（V1.2增强）: 作为评测审核人，我希望导出的CSV报告包含矫正结果和任务统计信息，以便于离线分析和归档。**

*   **价值陈述 (Value Statement)**:
    *   **作为** 评测审核人
    *   **我希望** 导出的CSV报告包含每次运行的矫正结果、矫正原因以及任务级统计信息
    *   **以便于** 将完整的评测数据离线归档、分发给团队或进行二次分析

*   **业务规则与逻辑 (Business Logic)**:
    1.  **前置条件**: 用户在结果详情页；任务状态为"已完成"。
    2.  **操作流程 (Happy Path)**:
        1. 用户在结果详情页点击"导出CSV"按钮。
        2. 前端调用 `GET /api/v1/evaluation-tasks/:taskId/export`，设置 `responseType: 'blob'`。
        3. 后端从数据库读取完整的评测数据（包括所有问题和运行结果）。
        4. 后端生成CSV文件，结构如下：
            - **前5行**：任务元信息（任务名称、类型、准确率、通过题数、创建时间）
            - **第6行**：空行（分隔符）
            - **第7行开始**：数据表头 + 所有问题的详细数据
        5. 后端返回文件流（Content-Type: text/csv; charset=utf-8）。
        6. 前端触发浏览器下载，文件名为 `{任务名称}_评测报告.csv`。
        7. 下载成功后显示提示："导出成功"。
    3.  **异常处理 (Error Handling)**:
        *   若任务未完成（HTTP 409），提示："任务尚未完成，无法导出"。
        *   若任务不存在（HTTP 404），提示："任务不存在"。
        *   若导出失败（HTTP 500），提示："导出CSV失败，请重试"。
        *   若文件名包含特殊字符（如 `/`、`\`、`:`），后端需要进行文件名安全处理（替换为下划线）。
    4.  **性能与容量提示**:
        - 大文件导出（>1000个问题）可能耗时较长（约30-60秒），前端需显示加载状态。
        - 后端使用流式写入，避免一次性加载所有数据到内存。

*   **验收标准 (Acceptance Criteria)**:
    *   **场景1: 成功导出带矫正的任务报告**
        *   **GIVEN** 我在一个启用了矫正且已完成的任务详情页
        *   **WHEN** 我点击"导出CSV"按钮
        *   **THEN** 浏览器应开始下载CSV文件，文件名为 `{任务名称}_评测报告.csv`，文件内容包含任务元信息和所有问题的矫正结果
    *   **场景2: CSV结构验证**
        *   **GIVEN** 我已下载CSV文件并用Excel打开
        *   **WHEN** 我检查文件内容
        *   **THEN** 前5行应显示任务元信息，第7行是表头，第8行开始是数据，每个问题包含5次运行的输出和矫正结果
    *   **场景3: 普通任务（未启用矫正）的导出**
        *   **GIVEN** 我在一个未启用矫正的任务详情页
        *   **WHEN** 我点击"导出CSV"按钮
        *   **THEN** CSV文件应包含矫正相关列，但矫正列内容为空
    *   **场景4: 文件名安全处理**
        *   **GIVEN** 任务名称为 `测试/模型:V1.2`
        *   **WHEN** 我导出CSV
        *   **THEN** 文件名应为 `测试_模型_V1.2_评测报告.csv`（特殊字符已替换）

---

*   **技术实现概要 (Technical Implementation Brief)**:
    *   **影响范围**: 后端 `GET /api/v1/evaluation-tasks/:taskId/export` 接口；前端结果详情页的导出按钮。

    *   **前端 / 客户端 (Frontend / Client)**:
        *   **按钮交互**（修改 `src/pages/TaskResults/index.tsx`）：
            ```typescript
            const [exporting, setExporting] = useState(false);

            const handleExport = async () => {
              try {
                setExporting(true);
                const response = await axios.get(
                  `/api/v1/evaluation-tasks/${taskId}/export`,
                  { responseType: 'blob', timeout: 120000 } // 2分钟超时
                );

                // 从响应头获取文件名
                const contentDisposition = response.headers['content-disposition'];
                const fileNameMatch = contentDisposition?.match(/filename\*=UTF-8''(.+)/);
                const fileName = fileNameMatch
                  ? decodeURIComponent(fileNameMatch[1])
                  : `${taskName}_评测报告.csv`;

                // 触发下载
                const url = window.URL.createObjectURL(new Blob([response.data]));
                const link = document.createElement('a');
                link.href = url;
                link.setAttribute('download', fileName);
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
        *   **按钮状态**：
            - 正常状态：显示"导出CSV"图标（Ant Design `<DownloadOutlined>`）
            - 加载状态：按钮 `loading={exporting}`，显示"正在生成CSV..."
            - 禁用状态：任务未完成时禁用按钮

    *   **后端 (Backend)**:
        *   **接口实现**：`GET /api/v1/evaluation-tasks/:taskId/export`
            - 查询参数：
                - `format`（可选，默认 `csv`，预留 `xlsx` 扩展）
                - `include_errors`（可选，默认 `true`，控制是否输出错误列）
            - 权限验证：单用户部署，无需额外验证；任务须为 `SUCCEEDED` 状态。
        *   **CSV生成逻辑**（新增 `app/services/export_service.py`）：
            ```python
            def generate_csv_export(task_id: str) -> Iterator[str]:
                """流式生成CSV内容"""
                task = get_task_by_id(task_id)
                items = get_all_items_with_runs(task_id)  # 使用游标流式读取

                # 第1-5行：任务元信息
                yield f"任务名称,{task.task_name}\n"
                yield f"任务类型,{'带矫正评测' if task.enable_correction else '纯评测任务'}\n"
                if task.enable_correction:
                    yield f"任务准确率,{task.accuracy_rate:.1f}%\n"
                    yield f"通过题数/总题数,{task.passed_count}/{task.total_items}\n"
                else:
                    yield f"任务准确率,-\n"
                    yield f"通过题数/总题数,-\n"
                yield f"创建时间,{task.created_at.strftime('%Y-%m-%d %H:%M:%S+08:00')}\n"
                yield "\n"  # 空行

                # 第7行：表头
                headers = [
                    "question_id", "question", "standard_answer", "is_passed",
                    # 5次运行的列
                    *[f"run_{i}_{col}" for i in range(1, 6)
                      for col in ["output", "status", "latency_ms", "error_code",
                                  "correction_result", "correction_reason"]]
                ]
                yield ",".join(headers) + "\n"

                # 第8行开始：数据行
                for item in items:
                    row = [
                        item.question_id,
                        escape_csv_field(item.question),
                        escape_csv_field(item.standard_answer),
                        "TRUE" if item.is_passed else "FALSE"
                    ]

                    # 补齐5次运行的数据
                    for i in range(1, 6):
                        run = next((r for r in item.runs if r.run_index == i), None)
                        if run:
                            row.extend([
                                escape_csv_field(run.response_body or ""),
                                run.status,
                                str(run.latency_ms),
                                run.error_code or "",
                                str(run.correction_result) if run.correction_result is not None else "",
                                escape_csv_field(run.correction_reason or "")
                            ])
                        else:
                            row.extend(["", "", "", "", "", ""])  # 空数据

                    yield ",".join(row) + "\n"

            def escape_csv_field(text: str) -> str:
                """CSV字段转义（处理逗号、引号、换行符）"""
                if not text:
                    return ""
                if "," in text or '"' in text or "\n" in text:
                    return f'"{text.replace('"', '""')}"'
                return text
            ```
        *   **HTTP响应头设置**：
            ```python
            response = StreamingResponse(
                generate_csv_export(task_id),
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": (
                        f'attachment; '
                        f'filename="{safe_filename(task.task_name)}_report.csv"; '
                        f'filename*=UTF-8\'\'{urllib.parse.quote(task.task_name + "_评测报告.csv")}'
                    )
                }
            )
            ```
        *   **文件名安全处理**：
            ```python
            def safe_filename(name: str) -> str:
                """移除文件名中的非法字符"""
                return re.sub(r'[<>:"/\\|?*]', '_', name)[:64]  # 限制长度
            ```

    *   **CSV示例**：
        ```csv
        任务名称,A模型V1.2稳定性测试
        任务类型,带矫正评测
        任务准确率,85.5%
        通过题数/总题数,102/120
        创建时间,2025-10-27 10:30:00+08:00

        question_id,question,standard_answer,is_passed,run_1_output,run_1_status,run_1_latency_ms,run_1_error_code,run_1_correction_result,run_1_correction_reason,run_2_output,...
        Q0001,中国的首都是哪里？,北京,FALSE,北京是中国的首都。,SUCCEEDED,812,,TRUE,核心信息与标准答案一致,中华人民共和国的首都是北京。,...
        Q0002,上海的别称是什么？,申城、魔都,TRUE,上海被称为申城或魔都。,SUCCEEDED,756,,TRUE,包含标准答案核心信息,...
        ```

*   **数据模型 / 接口契约 (Data Contracts & APIs)**:
    *   **`GET /api/v1/evaluation-tasks/:taskId/export` 接口**：
        - **请求参数**：
            - `format` (string, 可选, 默认 `csv`) - 导出格式：csv / xlsx
            - `include_errors` (boolean, 可选, 默认 `true`) - 是否包含错误列
        - **响应**：
            - Content-Type: `text/csv; charset=utf-8`
            - Content-Disposition: `attachment; filename="{任务名称}_report.csv"; filename*=UTF-8''{url_encoded_name}`
            - Body: CSV文件流
        - **错误响应**：
            - 404: 任务不存在
            - 409: 任务未完成（状态非 SUCCEEDED）
            - 500: 导出失败
    *   **CSV列定义**（完整版）：
        | 列名 | 类型 | 说明 |
        |------|------|------|
        | question_id | string | 问题ID |
        | question | string | 问题文本 |
        | standard_answer | string | 标准答案 |
        | is_passed | boolean | 该问题是否通过（TRUE/FALSE） |
        | run_1_output | string | 第1次运行的输出内容 |
        | run_1_status | string | 第1次运行状态 |
        | run_1_latency_ms | int | 第1次运行耗时（毫秒） |
        | run_1_error_code | string | 第1次运行错误码 |
        | run_1_correction_result | boolean/empty | 第1次矫正结果（TRUE/FALSE/空） |
        | run_1_correction_reason | string | 第1次矫正原因 |
        | run_2_output ~ run_5_correction_reason | ... | 第2-5次运行的数据（同上结构） |

*   **监控与运营 (Observability & Operations)**:
    *   后端日志：记录每次导出请求的任务ID、文件大小、生成耗时。
    *   Prometheus 指标：
        - `csv_export_total`（导出请求总数）
        - `csv_export_latency_seconds`（导出耗时分布）
        - `csv_export_size_bytes`（导出文件大小分布）

*   **约束与边界 (Constraints & Boundaries)**:
    *   CSV文件编码固定为 UTF-8 with BOM（确保Excel正常打开中文）。
    *   单个CSV文件最大支持 10,000 个问题（50,000 行数据）。
    *   导出请求超时时间为 2 分钟（可通过环境变量 `EXPORT_TIMEOUT_SECONDS` 配置）。

*   **非功能性需求 (Non-Functional)**:
    *   小文件（<100个问题）导出时间应 ≤5秒。
    *   大文件（1000个问题）导出时间应 ≤60秒。
    *   流式写入内存占用应 ≤50MB（不随数据量线性增长）。

*   **开放问题与待确认事项 (Open Questions & Follow-ups)**:
    *   是否需要支持 Excel (.xlsx) 格式导出？（责任人：产品，答复截止：V1.3规划前）
    *   是否需要在CSV中增加"任务总耗时"和"矫正总耗时"字段？（责任人：产品，答复截止：V1.3规划前）

---

## 4. 变更记录

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2025-10-27 | V1.2 Final | 正式版发布：完成模型矫正与准确率计算功能的完整设计，包含5个用户故事（US-01至US-05）覆盖创建、执行、监控、查看和导出全流程 |

---

**文档结束**
