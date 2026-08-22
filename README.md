# AI Reasoning Auditor

AI 观点审计器将观点拆成可检查的声明图，并暴露承重假设、最弱依赖与证据状态。

## 最大价值

AI 最容易误导人的地方，不是完全错误，而是把一个局部正确的观察包装成看似完整的结论。这个项目提供一个决策前的结构化刹车点：

> 在相信或执行 AI 建议之前，先看它依赖的哪一个假设最关键，以及下一步用什么最低成本验证。

它把一段观点拆成 `OBS`（观察）、`ASSUMPTION`（假设）、`INFERENCE`（推理）、`PREDICTION`（预测）和 `RECOMMENDATION`（建议），再分析推理链、承重假设、最弱环节和替代解释。它不输出“正确率”、不替用户做决定，也不把语言流畅误认为证据充分。

最适合审查：商业判断、增长策略、技术选型、市场趋势和任何准备转化为行动的 AI 长文结论。

当前版本已完成 PRD 的基础阶段，并加入下一阶段的 Provider-backed 解析：

- Schema 数据契约
- ClaimGraph 分析
- 确定性的 Mock Provider
- Markdown 报告渲染
- Decompose 阶段：Provider JSON -> ClaimGraph
- Alternative 阶段：Provider JSON -> AlternativeExplanation 列表
- Verification Planner：根据承重假设生成小规模验证步骤
- OpenAI-Compatible Provider：连接 OpenAI 或兼容 `/chat/completions` 的服务
- JSON 报告：供脚本和下游系统消费

当前不包含搜索、证据抓取、多模型或任何 Agent Framework。

## 环境

- Python 3.12+

## 安装与测试

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

本地服务端配置可参考 `.env.example`；不要把真实 Key 写入仓库。

## CLI 验收

安装后可以直接运行默认 Mock Provider：

```bash
auditor audit "未来 B2B 增长会转向 ABM"
auditor audit
auditor audit --file article.md --output report.md
auditor audit "未来 B2B 增长会转向 ABM" --compress-only
auditor audit "未来 B2B 增长会转向 ABM" --format json --output report.json
```

最小验收路径：先运行 Mock 审计，查看结构化报告顶部的“先看最影响结论的一步”，再切换 Markdown 或 JSON 导出；这三种视图来自同一份 `AuditReport`，不会产生互相矛盾的结论。

默认使用 `--provider mock`。连接 OpenAI-Compatible 服务时：

```bash
export OPENAI_API_KEY="..."
export OPENAI_BASE_URL="https://api.openai.com/v1"  # 兼容服务可替换
export OPENAI_MODEL="gpt-4o-mini"
auditor audit "未来 B2B 增长会转向 ABM" --provider openai-compatible
```

Provider 使用 Chat Completions 的 `POST /chat/completions` 协议，并对响应结构、超时和 HTTP 错误做校验。密钥不会出现在错误信息中。Mock 输出用于验证流程，不代表观点正确性，也不执行搜索或证据判断。

直接运行 `auditor audit` 会进入单轮交互提示；脚本、CI 和批量场景继续使用文本参数、`--file` 或 stdin。

## Web UI

启动本地 Web 服务：

```bash
.venv/bin/auditor-web
# 或
.venv/bin/python -m auditor.web
```

浏览器打开 `http://127.0.0.1:8000`。Web UI 支持：

- Mock 或后端代理的 OpenAI-Compatible Provider；浏览器不直接请求供应商，适合有 CORS 或客户端调用限制的供应商；
- 结构化视图：摘要指标、声明表、推理链和风险阅读；
- Markdown 视图：适合复制、下载和提交评审；
- JSON 视图：可折叠数据树，适合 API、自动化和前端集成；
- 审计状态：后台任务会显示排队、拆解声明、推理分析、替代解释、验证规划和报告生成等阶段，并显示阶段耗时；
- 桌面端单屏工作台：输入区与报告区独立滚动，模型配置收纳在设置对话框；移动端自动恢复纵向滚动；
- 声明表格、修辞风险、承重假设、替代解释和验证步骤；
- 响应式桌面/移动布局。

首次打开页面会看到 Mock 快速上手提示。切换到 OpenAI-Compatible 后，可选择常用供应商预设，或在 Provider 设置中填写 API Key、Base URL、Model 和超时。浏览器只把配置发送给本机 Web API，由后端请求供应商；API Key 不写入浏览器存储、任务状态、报告或服务器文件，成功后清空，失败时仅暂留在当前页面以便修正和重试。生产环境推荐使用启动 Web 服务的终端环境变量 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 和 `OPENAI_MODEL`，这样浏览器无需接触 Key。Base URL 只允许 HTTPS，或 localhost/127.0.0.1/::1 的本机 HTTP 服务。

### API Key 安全边界

- 临时 Key 只随当前请求发送，服务端只在请求和 Provider 生命周期内使用，不写入数据库、文件、Cookie、localStorage、任务状态或报告。
- 成功后前端立即清空 Key；失败时仅保留当前页面输入，方便修正后重试；切换回 Mock 会立即清空。
- `/api/health` 只返回是否配置，不返回 Key；HTTP 错误中的供应商回显会做脱敏。
- Key 会拒绝空白、控制字符和超过 500 个字符的值。服务端环境变量和临时输入使用同一套校验。
- 本地默认允许临时 Provider 配置；公共部署应设置 `AUDITOR_ALLOW_TRANSIENT_PROVIDER_CONFIG=false`，并只在服务端设置 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`。

### Docker / 公共部署

仓库包含可直接使用的 `Dockerfile`。平台通常会注入 `PORT`，容器会监听 `0.0.0.0`：

```bash
docker build -t reasoning-auditor .
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY="..." \
  -e OPENAI_BASE_URL="https://api.openai.com/v1" \
  -e OPENAI_MODEL="gpt-4o-mini" \
  reasoning-auditor
```

镜像默认关闭浏览器临时 Provider 配置，避免把服务变成任意访客可控的远程代理。只在受信任的本机环境中，才考虑显式设置 `AUDITOR_ALLOW_TRANSIENT_PROVIDER_CONFIG=true`。

## 最小示例

```python
from auditor.graph.ops import GraphAnalyzer
from auditor.render import MarkdownReportRenderer
from auditor.schema import (
    AuditReport,
    Claim,
    ClaimEdge,
    ClaimGraph,
    ClaimType,
    CurrentJudgement,
)

graph = ClaimGraph(
    original_text="SEO 正在死亡，企业应该转向 ABM。",
    compressed_view="SEO 的重要性将下降，因此企业应增加 ABM 投入。",
    claims=[
        Claim(id="c1", type=ClaimType.OBS, content="部分网站自然流量下降。"),
        Claim(id="c2", type=ClaimType.ASSUMPTION, content="下降主要由 AI 搜索导致。"),
        Claim(id="c3", type=ClaimType.RECOMMENDATION, content="企业增加 ABM 投入。"),
    ],
    edges=[
        ClaimEdge(from_claim_id="c1", to_claim_id="c2"),
        ClaimEdge(from_claim_id="c2", to_claim_id="c3"),
    ],
)

report = AuditReport(
    graph=graph,
    analysis=GraphAnalyzer().analyze(graph),
    judgement=CurrentJudgement(
        reasonable_insights=["部分网站自然流量下降。"],
        unverified_extrapolations=["下降主要由 AI 搜索导致。"],
    ),
)

print(MarkdownReportRenderer().render(report))
```

数据模型会拒绝重复声明 ID、悬空边、自引用边和有环图，避免分析器接收到含义不明确的 ClaimGraph。

## Provider 阶段

阶段模块只依赖统一的 `Provider.complete(prompt) -> str` 接口，因此可以使用
`MockProvider` 做确定性测试。Provider 必须返回 JSON：Decompose 返回对象，
Alternative 返回数组；纯 JSON、完整的 JSON 代码围栏，以及前置一小段说明后包裹的单个 JSON 代码围栏都可被解析；多个 payload 或无法明确定位的散文仍会被拒绝。
Decompose 会在 Provider 边界兼容少量常见别名：claim 的 `statement`/`text`
会归一为 `content`，edge 的 `source`/`target` 会归一为
`from_claim_id`/`to_claim_id`；归一化后仍执行严格 Schema 和图完整性校验。
若首次输出仍无法解析或校验，Decompose 会要求同一 Provider 按标准 Schema
自动修复一次。修复仍失败则停止；开启 Alternative 时最坏为 3 次模型调用，
不会无限重试。
Alternative 会把单字符串 `required_data` 归一为单元素数组，并丢弃缺少排除方法、
所需数据或成本的单项，不让一个坏的替代解释阻断整份报告。
Alternative 属于可选增强：供应商超时、限流、非 JSON 或响应结构异常时，会保留已完成的
ClaimGraph，并在 Markdown/结构化报告的“审计提示”中说明降级原因。

“分析替代解释”用于寻找能解释同一观察的其他普通原因，并为每个原因提供排除方法、所需数据和成本。例如“自然流量下降”除了 AI 搜索，也可能来自季节性、算法更新、网站改版或测量错误。开启后会增加一次 Provider 调用；关闭后只执行声明拆解和结构分析。

修辞扫描只把“必然、唯一、全面、革命”等词当作审计提示，不判定观点为假；明显的否定/反例语境（例如“不是必然”“并非唯一”“不一定”）会被忽略，以降低误报。

```python
import json

from auditor.providers import MockProvider
from auditor.stages import AlternativeStage, DecomposeStage

graph = DecomposeStage(
    MockProvider(default_response=json.dumps({
        "compressed_view": "观点压缩",
        "claims": [{"id": "c1", "type": "OBS", "content": "观察"}],
        "edges": [],
    }))
).run("原始观点")

alternatives = AlternativeStage(MockProvider(default_response="[]")).run(graph)
assert alternatives == []
```
