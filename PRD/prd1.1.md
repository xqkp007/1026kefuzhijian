# 产品需求文档：智能体输出稳定性评测工具 - V1.1（智谱 SDK 接入）

---

## 1. 综述（Overview）

### 1.1 背景与目标
- 现阶段评测工具尚未接入第三方大模型 SDK，导致后续模型切换与实验流程缺乏统一规范。
- 本版本聚焦「智谱 Zhipu」模型的 SDK 安装与基础调用能力，为后续在工作流中接入模型评测打下环境基础。
- 目标是在现有后端虚拟环境中完成 SDK 安装、密钥配置、版本验证，并沉淀标准化调用示例。

### 1.2 范围界定
- **包含**：`zai-sdk` 安装；API Key 管理方式；最小可运行示例；开发/测试验收指引；常见问题与安全要求。
- **不包含**：将智谱调用逻辑接入现有评测工作流；批量任务调度优化；前端配置界面。

### 1.3 成功标准
1. 在 `backend/.venv` 中成功安装最新版 `zai-sdk`，并记录最终版本号。
2. 在项目根目录保留 SDK 调用示例脚本，能读取 `.env` 中的密钥并成功发起一次对话请求。
3. 文档对环境准备、密钥配置、安全注意事项、验收流程说明清晰，便于产品/运营复现。
4. 相关操作具备可追踪日志或命令记录，确保团队成员按指引执行不会踩坑。

---

## 2. 用户与场景

### 2.1 核心用户
- **运维/平台工程师**：需要在本地或开发环境完成 SDK 安装、配置、连通性测试。
- **算法/模型工程师**：需要快速调用智谱模型做 Prompt 迭代验证。

### 2.2 用户旅程
1. 运维按照文档准备 `.env`，写入 `ZHIPU_API_KEY`。
2. 在项目根目录执行安装命令，确认版本无误。
3. 运行示例脚本，验证 SDK 能返回模型响应。
4. 将脚本作为后续评测工作流调用的参考模板。

---

## 3. 功能需求

### FR-01 环境依赖准备
- 使用现有虚拟环境 `backend/.venv`，不得新建全局或临时环境。
- 安装命令：`cd backend && .venv/bin/pip install --upgrade zai-sdk`
- 安装完成后需记录日志：`zai.__version__`。
- 若未来需要锁定版本，统一在 `backend/pyproject.toml` 增加依赖条目并写明原因。

### FR-02 API Key 管理
- 新增或更新 `backend/.env.example`，包含占位变量：
  ```
  ZHIPU_API_KEY="your-zhipu-api-key"
  ```
- 实际密钥只允许写入本地 `.env`，严禁提交至仓库或日志。
- 后端调用读取环境变量 `ZHIPU_API_KEY`。当变量缺失时应抛出明确的配置错误。

### FR-03 基础调用示例
- 在 `backend/app/examples/zhipu_chat_demo.py`（或同级目录）提供最小示例：
  - 读取 `.env`（使用 `python-dotenv`，此库若尚未安装需在依赖中声明）。
  - 构造 `ZhipuAiClient(api_key=...)`。
  - 发起一次 `glm-4.6` 对话请求，保留 1 条用户自定义提示词示例。
  - 控制台输出响应的 `role`、`content` 与本次调用的 `request_id`（若 SDK 返回）。
- 示例需具备容错处理（例如网络超时、401 密钥错误），并打印易懂的错误提示。

### FR-04 提示词管理
- 在 `backend/app/prompts/zhipu/` 目录集中维护智谱相关的提示词文件，命名规范为 `<use_case>_prompt.txt`（示例：`marketing_tagline_prompt.txt`）。
- 示例脚本默认读取 `backend/app/prompts/zhipu/default_chat_prompt.txt`，开发者可通过命令行参数 `--prompt-path` 指定其他提示词。
- 若提示词需要包含占位符（例如 `{product_name}`），需在示例脚本中提供参数化演示，并在 README 中说明可用占位符列表。
- 提示词文件纳入版本控制，但不得包含敏感信息；如需动态生成提示词，可在后续迭代中增加配置化支持。

### FR-05 调用参数配置
- 所有可调参数通过环境变量覆盖，默认值写入 `.env.example`，示例：
  ```
  ZHIPU_MODEL_ID="glm-4.6"
  ZHIPU_THINKING_TYPE="disabled"  # 可选：disabled/enabled/sse
  ZHIPU_MAX_TOKENS=4096
  ZHIPU_TEMPERATURE=0.7
  ZHIPU_DIALOG_MODE="single"  # 默认单轮对话
  ```
- 当前业务场景统一按照「单轮对话」执行。服务不会保留历史上下文，连续调用时输出互不依赖。
- 示例脚本在载入 `.env` 后读取上述变量，构造调用配置字典；未配置时应退回默认值，并在日志中提示生效的参数。
- 文档需提醒：开启 `thinking.type` 为 `enabled` 会额外计费且增加响应时延，默认保持 `disabled`，由业务方手动确认后再开启。

### FR-06 文档与可观测性
- 在本 PRD 和后续开发者文档中记录：
  - 环境变量配置步骤。
  - pip 安装命令与常见报错。
  - 版本验证命令。
  - 示例脚本的运行方式与输出期望。
- 若 SDK 提供调试/日志开关，需在文档中说明如何启用与定位问题。

### FR-07 评测任务接入策略
- 后端保留原有“第三方智能体”调用链：依赖 `agent_api_url`/`agent_api_headers`，解析 `data.output`。
- 新增智谱专用执行器，当 `agent_model` 以 `zhipu` 开头（或 `agent_api_url` 形如 `zhipu://*`）时，自动走 `zai-sdk` 调用链。
- 两条链路互不影响：老智能体只记录原始 JSON/流式日志，不解析智谱字段；智谱调用通过新模块处理 `messages`、`thinking` 等高级参数。
- 所有上游响应（无论来源）必须在 `logs/celery.log` 中打印原文，便于对比调试。

---

## 4. 非功能与安全要求
- **安全**：密钥严格通过环境变量管理；示例代码不得回显完整密钥；日志中屏蔽敏感信息。
- **可靠性**：示例脚本需在网络波动（如 30 秒超时）场景下给出可重试提示。
- **可维护性**：PRD 要求的所有脚本、配置路径与命令均使用仓库相对路径，避免开发者环境差异。

---

## 5. 依赖与前置条件
- Python 3.11 已配置完成。
- FastAPI/后端服务已有 `.venv` 并安装基础依赖。
- 开发者已从智谱开放平台申请有效的 API Key。
- 如需运行示例脚本，建议先执行 `cp backend/.env.example backend/.env` 并写入真实密钥。

---

## 6. 验收与测试计划

| 场景 | 步骤 | 期望结果 |
|------|------|----------|
| 安装验证 | `cd backend && .venv/bin/pip install --upgrade zai-sdk` | 命令执行成功，无错误退出；`zai-sdk` 版本满足 >=0.0.4 |
| 版本确认 | `cd backend && .venv/bin/python -c "import zai; print(zai.__version__)"` | 控制台正确打印版本号 |
| 示例运行 | `cd backend && .venv/bin/python app/examples/zhipu_chat_demo.py` | 输出请求参数摘要与模型返回文本；无异常时退出码为 0 |
| 异常场景 | 删除或清空 `.env` 中的 `ZHIPU_API_KEY`，再次运行示例 | 程序抛出「缺少 API Key」提示，退出码非 0 |
| 单轮校验 | 在默认配置下连续运行两次示例脚本 | 第二次调用不引用第一次输出，验证未保留上下文 |

---

## 7. 风险与对策
- **网络访问受限**：本地若无法访问外网，请预先申请白名单或使用镜像源；文档需给出备用下载方式（如离线 wheel）。
- **SDK 版本更新不兼容**：当新版 SDK 引入 breaking change，需在变更前验证并在 PRD 中记录升级说明。
- **密钥泄露风险**：示例脚本与日志中不得输出密钥；建议配合内部秘钥管理平台定期轮换。
- **接口限流**：智谱侧若限制调用频率，开发时应控制请求频率；后续工作流接入时需要统一的限流策略。

---

## 8. 里程碑与交付物
- **M1（完成安装与验证）**：更新后端依赖、确认版本号、提交安装日志。
- **M2（示例脚本可运行）**: 新增 `zhipu_chat_demo.py`，通过手动测试。
- **M3（文档合入）**: 本 PRD 与开发者指引同步到仓库，确保团队成员都可获取。

---

## 9. 附录
- 智谱开放平台：https://open.bigmodel.cn/
- 官方 SDK 文档：https://open.bigmodel.cn/dev/howuse
- 内部安全规范：参考《AI 工程师工作规范》第 6 节

## 10. 调用示例 

安装 SDK

Copy
# 安装最新版本
pip install zai-sdk
# 或指定版本
pip install zai-sdk==0.0.4
验证安装

Copy
import zai
print(zai.__version__)
基础调用

Copy
from zai import ZhipuAiClient

client = ZhipuAiClient(api_key="your-api-key")  # 请填写您自己的 API Key

response = client.chat.completions.create(
    model="glm-4.6",
    messages=[
        {"role": "user", "content": "作为一名营销专家，请为我的产品创作一个吸引人的口号"},
        {"role": "assistant", "content": "当然，要创作一个吸引人的口号，请告诉我一些关于您产品的信息"},
        {"role": "user", "content": "智谱AI开放平台"}
        ],
    thinking={
        "type": "enabled",    # 启用深度思考模式
    },
    max_tokens=65536,          # 最大输出 tokens
    temperature=1.0           # 控制输出的随机性
)

# 获取完整回复
print(response.choices[0].message)
