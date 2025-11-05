# 产品需求文档：智能体输出稳定性评测工具 - V1.3（端到端多轮会话评测）

> 文档状态：正式版（Final）
> 创建日期：2025-11-05
> 基于版本：V1.2（模型矫正与准确率计算）

---

## 1. 综述（Overview）

### 1.1 背景与目标

- 现状：评测系统对数据集中每一题默认执行固定次数（如5次）单轮调用；当业务上存在“需要连续追问”的题目时，缺乏对话上下文，无法复现真实用户场景。
- 目标：在不改“质检/矫正”逻辑的前提下，先调整“Agent 请求层”实现端到端多轮评测；同时在前端详情/导出层面新增对 `session_group` 的分组展示，方便识别一段连续对话。

### 1.2 核心思路（业务语言）

- 在 Excel 新增可选列 `session_group`：同一组内的多行表示“同一段连续对话”；为空表示单轮题。
- 系统按文件行序处理题目：同一 `session_group` 的多行按上下顺序依次作为第1轮、第2轮、…进行发送。
- 端到端重复：对于每个多轮分组，创建 n 个稳定 `session_id`（n=RUNS_PER_ITEM）。每个 `session_id` 表示一条完整的对话路径：从该组的第1行依次对话至最后一行。第 r 行的第 k 次结果，取自第 k 条会话路径的第 r 次响应。
- 单轮题保持现有逻辑：无 `session_group` 的行，`session_id` 为空，执行 n 次（n=RUNS_PER_ITEM）。

### 1.3 范围界定

- 调整范围：
-  - 后端：数据导入与会话调度已在上一轮实现，本次仅补充导出列配置。
-  - 前端：任务详情页按 `session_group` 分组展示、标注多轮路径；CSV 导出增加可选列。
- 保持不变：核心矫正/准确率逻辑。

---

## 2. 业务流程（User Journey）

1) 创建任务：沿用 V1.0/V1.2 流程，上传数据集（CSV/Excel）。可在表中为需要多轮的题目填写同一个 `session_group` 值；未填则视为单轮题。
2) 执行评测：
   - 系统按导入顺序处理各行；属于同一 `session_group` 的多行视为一段会话。
   - 对每个分组，生成 n 个会话 `S1..Sn`（n=RUNS_PER_ITEM）。对每个 `S_k`，按组内行顺序依次发送问题（第1轮→第2轮→…），把该路径上第 r 次响应写回分组第 r 行的 run_k。
   - 无分组（单轮）行：执行 n 次请求（`session_id` 为空）。
3) 查看/导出结果：
   - 任务详情页：同 `session_group` 的题目被包裹在同一个会话分组容器中（显示“多轮对话 grpX，n 轮 × RUNS_PER_ITEM 次”），组内仍展示每轮的 run 结果；单轮题保持原样。
   - 导出：在错误详情 CSV 中追加可选列 `session_group`，便于外部分析。

---

## 3. 功能特性

### 3.1 数据集格式

- 必填列：`question`、`standard_answer`
- 建议列：`question_id`（若缺失系统自动生成 UUID）
- 可选列（沿用）：`system_prompt`、`user_context`
- 新增可选列：`session_group`
  - 相同非空值表示同一段对话；空表示单轮题。
  - 轮次顺序：以文件中出现的上下顺序为准。

示例（节选）：

| question_id | question         | standard_answer | session_group |
|-------------|------------------|-----------------|---------------|
| q1          | 你好             | 你好            | grp_001       |
| q2          | 继续刚才的话题？ | ……              | grp_001       |
| q3          | 单轮问题A        | 答案A           |               |

### 3.2 会话与请求策略

- `session_id` 生成
  - 策略：本地确定性生成（不依赖服务端返回），推荐格式 `sha1(taskId|session_group|k)`（k=1..n），保证每个会话路径稳定可复现。
  - 同组 n 条路径：相同 `session_group` 下生成 n 个不同的 `session_id`；每个 `session_id` 对应一条完整会话路径。
  - 单轮题：`session_id` 置空（或不传）。
- `tpuid`
  - 如需按用户维度在 aico 端记录历史，可通过后端环境变量 `DEFAULT_AGENT_EXTRA_FIELDS` 注入 `{"tpuid":"<your_user_id>"}`，系统自动合并到请求体。
- 运行与映射
  - 多轮组：会话 `S_k` 依序调用全组问题，分组第 r 行的 run_k = `S_k` 的第 r 次响应。
  - 单轮行：执行 n 次，写入 run_1..run_n。
- 其他字段：`doc_list`、`image_url`、`query`、`stream` 等保持与现有一致；`stream` 默认 true。

### 3.3 前端展示规则

- 会话分组容器：每个非空 `session_group` 渲染为一段折叠/展开区域，顺序跟随上传顺序。
- 轮次行：显示 “第 r 轮：<question>”，下方保留 run_1..run_n 卡片，卡片说明改为 “路径 S_k 第 r 轮输出”。
- 单轮题：沿用原卡片布局。
- 视觉提示：组头增加“多轮对话”标识 + 轮次数 + 会话路径数量；若 `session_group` 缺失则不显示。

ASCII 结构示意：

```
┌──────────────────────────────────────────────┐
│ 会话 grpA（3 轮 × 5 次）                     │
│ ├─ 轮 1：Q1《你好》                         │
│ │   ├─ run#1 (S1 第1轮)                      │
│ │   ├─ run#2 (S2 第1轮)                      │
│ │   ├─ run#3 (S3 第1轮)                      │
│ │   ├─ run#4 (S4 第1轮)                      │
│ │   └─ run#5 (S5 第1轮)                      │
│ ├─ 轮 2：Q2《请继续》                       │
│ │   ├─ run#1 (S1 第2轮)                      │
│ │   ├─ run#2 (S2 第2轮)                      │
│ │   ├─ run#3 (S3 第2轮)                      │
│ │   ├─ run#4 (S4 第2轮)                      │
│ │   └─ run#5 (S5 第2轮)                      │
│ └─ 轮 3：Q3《最终报价》                     │
│     ├─ run#1 (S1 第3轮)                      │
│     ├─ run#2 (S2 第3轮)                      │
│     ├─ run#3 (S3 第3轮)                      │
│     ├─ run#4 (S4 第3轮)                      │
│     └─ run#5 (S5 第3轮)                      │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│ 单轮题（未分组）                             │
│ ├─ run#1                                     │
│ ├─ run#2                                     │
│ ├─ run#3                                     │
│ ├─ run#4                                     │
│ └─ run#5                                     │
└──────────────────────────────────────────────┘
```

### 3.4 兼容性

- 旧数据集（无 `session_group` 列）完全兼容，全部按单轮题处理。
- 新增列为可选，未填不影响原有流程与统计。

---

## 4. 数据契约（Data Contract）

### 4.1 数据集（输入）

- 列集合：`{question, standard_answer}` + 可选 `{question_id, system_prompt, user_context, session_group}`
- 行顺序：系统严格按文件顺序处理；同组多轮即按该顺序发送。

### 4.2 Agent 请求载荷（对 aico）

```json
{
  "doc_list": [],
  "image_url": "",
  "query": "<行的question>",
  "session_id": "<同组复用或空>",
  "stream": true,
  "tpuid": "<可选，通过 DEFAULT_AGENT_EXTRA_FIELDS 注入>"
}
```

### 4.3 内部状态

- `session_map`: 进程内缓存，键：`task_id + session_group`，值：确定性计算的 `session_id`。
- 对于单轮题，不写入 `session_map`。

---

## 5. 验收标准（Acceptance Criteria）

1) 单轮不变：未填写 `session_group` 的行，发送请求时 `session_id` 为空，执行次数等于 `RUNS_PER_ITEM`。
2) 多轮端到端：同一 `session_group` 的多行按顺序发送；为该组创建 n 条会话路径，组内第 r 行的第 k 次结果来自第 k 条路径的第 r 次响应。
3) 请求总量：对一个 m 轮的分组，HTTP 请求 = m × n（n=RUNS_PER_ITEM）。
4) 顺序正确：多轮对话按文件行序严格执行，不乱序、不丢轮。
5) 兼容性：未提供 `session_group` 列的历史数据集可正常创建与执行。
6) 限定范围：矫正/准确率逻辑不变。

---

## 6. 配置与运维

- 复用既有配置：`RUNS_PER_ITEM`、`USE_STREAM`、`DEFAULT_AGENT_EXTRA_FIELDS` 等保持不变。
- 导出新增列可通过参数控制是否启用（默认开启）。
- 如后续需要改为“首轮由 aico 分配 `session_id` 再复用”的策略，可在实现时新增开关（例如 `SESSION_ID_STRATEGY=from_response|local_deterministic`），不在本次范围。

---

## 7. 风险与对策

- 风险：数据集中同组行分散在很远位置，实际会话逻辑偏离用户心智。
  - 对策：由数据维护方确保同一 `session_group` 的行在文件中相邻或按期望顺序排列；系统严格遵循文件顺序，不做重排。
- 风险：多轮分组较长时，请求量为 m×n，整体时延与成本上升。
  - 对策：在任务创建时控制 RUNS_PER_ITEM；后续可引入任务级并发与速率限制调优（不在本次范围）。
- 风险：aico 平台对 `session_id` 的字符集或长度有限制。
  - 对策：采用 SHA-1 十六进制串（40位，字母数字）保障兼容性。

---

## 8. 变更影响与不做事项（Out of Scope）

- 不改任务列表/创建页的交互；详情页仅新增分组容器，不调整现有 run 卡片样式。
- 不修改质检/矫正规则与准确率计算。
- 不接入显式的历史消息拼接（多轮上下文仍由 aico 基于 `session_id` 维护）。

---

## 9. 里程碑与交付

- M1 需求冻结：PRD 1.3 合入仓库（本文件）。
- M2 后端实现：
  - 读取 `session_group` 列（导入层），并在执行时为同组复用稳定 `session_id`；多轮行单次执行。
  - 仅改 Agent 请求层；矫正逻辑保持不变。
- M3 验收：按第 5 节验收标准覆盖单轮/多轮混合数据集测试。

---

## 10. 附：aico 接口参考（节选）

- 请求（流式示例）：

```bash
curl -X POST 'http://<host>/aicoapi/gateway/v2/chatbot/api_run/<appId_uuid>' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <API_KEY>' \
  -d '{
        "doc_list":[],
        "image_url":"",
        "query":"{query}",
        "session_id":"<可为空或同组复用>",
        "stream":true,
        "tpuid":"<可选>"
      }'
```

- 返回（流式关键字段）：`event`、`session_id`、`data.choices[0].delta.content` 等 —— 本版本不依赖返回的 `session_id`，采用本地确定性值。
