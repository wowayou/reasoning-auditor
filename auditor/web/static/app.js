const opinion = document.querySelector("#opinion");
const provider = document.querySelector("#provider");
const includeAlternatives = document.querySelector("#include-alternatives");
const auditButton = document.querySelector("#audit-button");
const clearButton = document.querySelector("#clear-button");
const errorMessage = document.querySelector("#error-message");
const errorWrap = document.querySelector("#error-wrap");
const retryButton = document.querySelector("#retry-button");
const reportStatus = document.querySelector("#report-status");
const auditProgress = document.querySelector("#audit-progress");
const progressCurrent = document.querySelector("#progress-current");
const progressElapsed = document.querySelector("#progress-elapsed");
const progressBar = document.querySelector("#progress-bar");
const progressSteps = document.querySelector("#progress-steps");
const structuredView = document.querySelector("#structured-view");
const markdownView = document.querySelector("#markdown-view");
const markdownSource = document.querySelector("#markdown-source");
const jsonView = document.querySelector("#json-view");
const jsonTree = document.querySelector("#json-tree");
const onboarding = document.querySelector("#onboarding");
const providerSettings = document.querySelector("#provider-settings");
const apiKey = document.querySelector("#api-key");
const baseUrl = document.querySelector("#base-url");
const model = document.querySelector("#model");
const timeout = document.querySelector("#timeout");
const providerPreset = document.querySelector("#provider-preset");
const configHint = document.querySelector("#config-hint");
const characterCount = document.querySelector("#character-count");
const providerSummaryText = document.querySelector("#provider-summary-text");
const privacyNoteText = document.querySelector("#privacy-note-text");
let latestArtifacts = { markdown: "", json: "" };
const EXPECTED_WEB_BUILD = 9;
let progressTimer = null;
let progressStarted = 0;
let progressIndex = 0;
let progressStageList = [];

const progressStages = [
  ["decompose", "拆解声明"],
  ["analyze", "分析推理链"],
  ["rhetoric", "扫描修辞风险"],
  ["alternatives", "寻找替代解释"],
  ["verification", "规划验证步骤"],
  ["report", "生成审计报告"],
];

function startProgress(includeAlternative) {
  progressStageList = progressStages.filter(([id]) => includeAlternative || id !== "alternatives");
  progressIndex = 0;
  progressStarted = performance.now();
  auditProgress.hidden = false;
  progressBar.classList.remove("is-error");
  progressSteps.innerHTML = progressStageList.map(([, label]) => `<li><span class="step-dot"></span><span>${label}</span></li>`).join("");
  progressCurrent.textContent = "排队中";
  progressElapsed.textContent = "0.0s";
  progressBar.style.width = "4%";
  reportStatus.textContent = "正在排队 · 等待审计任务启动";
}

function renderProgress() {
  const elapsed = (performance.now() - progressStarted) / 1000;
  const [id, label] = progressStageList[progressIndex] || ["", "准备审计"];
  progressCurrent.textContent = label;
  progressElapsed.textContent = `${elapsed.toFixed(1)}s`;
  progressBar.style.width = `${Math.max(8, ((progressIndex + 1) / progressStageList.length) * 100)}%`;
  progressSteps.querySelectorAll("li").forEach((step, index) => {
    step.classList.toggle("is-done", index < progressIndex);
    step.classList.toggle("is-current", index === progressIndex);
  });
  reportStatus.textContent = `正在${label} · 已完成 ${progressIndex}/${Math.max(progressStageList.length - 1, 1)} 个阶段`;
}

function finishProgress(stages, durationMs) {
  if (progressTimer) window.clearInterval(progressTimer);
  progressTimer = null;
  progressIndex = Math.max(0, (stages?.length || progressStageList.length) - 1);
  renderProgress();
  progressBar.style.width = "100%";
  progressCurrent.textContent = "审计完成";
  progressElapsed.textContent = `${((durationMs || performance.now() - progressStarted) / 1000).toFixed(1)}s`;
  progressSteps.querySelectorAll("li").forEach((step) => {
    step.classList.remove("is-current");
    step.classList.add("is-done");
  });
  window.setTimeout(() => { auditProgress.hidden = true; }, 900);
}

function updateProgressFromJob(job) {
  const elapsed = Number(job.elapsed_ms || 0) / 1000;
  progressElapsed.textContent = `${elapsed.toFixed(1)}s`;
  const currentIndex = progressStageList.findIndex(([id]) => id === job.current_stage);
  if (currentIndex >= 0) progressIndex = currentIndex;
  if (job.status === "queued") {
    progressCurrent.textContent = "排队中";
    progressBar.style.width = "4%";
  } else if (job.status === "running") {
    renderProgress();
  }
  progressSteps.querySelectorAll("li").forEach((step, index) => {
    step.classList.toggle("is-done", index < progressIndex);
    step.classList.toggle("is-current", index === progressIndex && job.status === "running");
  });
}

async function pollAuditJob(jobId) {
  const deadline = Date.now() + 5 * 60 * 1000;
  while (Date.now() < deadline) {
    const response = await fetch(`/api/audit/jobs/${encodeURIComponent(jobId)}`);
    const job = await response.json();
    if (!response.ok) throw new Error(job.detail || "无法读取审计状态");
    updateProgressFromJob(job);
    if (job.status === "completed") return job.result;
    if (job.status === "failed") throw new Error(job.error || "审计失败");
    await new Promise((resolve) => window.setTimeout(resolve, 250));
  }
  throw new Error("审计等待超过 5 分钟，请检查 Provider 或重新尝试。");
}

function failProgress() {
  if (progressTimer) window.clearInterval(progressTimer);
  progressTimer = null;
  progressCurrent.textContent = "审计暂停";
  progressBar.classList.add("is-error");
  const current = progressSteps.querySelector("li.is-current");
  if (current) current.classList.add("is-error");
}

const providerPresets = {
  openai: { baseUrl: "https://api.openai.com/v1", model: "gpt-4o-mini" },
  deepseek: { baseUrl: "https://api.deepseek.com/v1", model: "deepseek-chat" },
  openrouter: { baseUrl: "https://openrouter.ai/api/v1", model: "openai/gpt-4o-mini" },
  custom: { baseUrl: "", model: "" },
};

function updateProviderHint() {
  const configured = provider.value === "openai-compatible";
  configHint.textContent = configured
    ? "请求由本机后端转发到供应商，不会让浏览器直接连接供应商。Key 仅用于本次请求；成功后清空，失败时保留以便修正或重试。"
    : "Mock 完全离线运行，不需要 API Key。";
  const presetLabel = providerPreset.options[providerPreset.selectedIndex]?.text || "自定义";
  const modelLabel = model.value.trim() || model.placeholder || "未指定模型";
  providerSummaryText.textContent = configured ? `${presetLabel} · ${modelLabel}` : "Mock · 本地演示";
  privacyNoteText.textContent = configured
    ? "临时 Key 不落盘；成功后清空，失败时保留以便重试。"
    : "Mock 在本地运行，不发送 API Key。";
}

function applyPreset() {
  const preset = providerPresets[providerPreset.value] || providerPresets.custom;
  if (providerPreset.value !== "custom") {
    baseUrl.value = preset.baseUrl;
    model.value = preset.model;
  }
  updateProviderHint();
}

function openProviderSettings(selectProvider = false) {
  if (selectProvider) provider.value = "openai-compatible";
  updateProviderHint();
  if (!providerSettings.open) providerSettings.showModal();
  window.setTimeout(() => apiKey.focus(), 0);
}

function explainError(message) {
  const text = String(message || "请求失败");
  if (text.includes("remained invalid after one automatic repair")) {
    return "模型输出经过一次自动格式修复后仍不符合 ClaimGraph Schema。请重试，或换用更稳定的 JSON 模型。";
  }
  if (text.includes("provider alternatives failed schema validation")) {
    return "模型返回的替代解释格式不完整。系统会丢弃缺少排除方法、所需数据或成本的项目；请重试以获得可验证的替代解释。";
  }
  if (text.includes("provider decomposition failed schema validation")) {
    return "模型返回了无法识别的声明结构。系统已兼容常见字段并自动请求一次格式修复，但仍未通过严格校验；请重试或换用更稳定的 JSON 模型。";
  }
  if (text.includes("OPENAI_API_KEY is required")) {
    return "没有找到 API Key。请在 Provider 设置中填写临时 Key，或在启动 Web 服务的终端设置 OPENAI_API_KEY。";
  }
  if (text.includes("HTTP 401")) return `${text} 若供应商限制客户端调用，请确认 Key、模型和账号属于同一供应商，并从该供应商控制台复制 API 根地址。`;
  if (text.includes("HTTP 403")) return `${text} 这通常是模型权限、区域限制或账号配额问题。`;
  if (text.includes("HTTP 404")) return `${text} 常见原因是 Base URL 多写或少写了 /v1，或模型名不存在。`;
  if (text.includes("HTTP 429")) return `${text} 请稍后重试，或降低调用频率。`;
  return text;
}

function updateCharacterCount() {
  characterCount.textContent = `${opinion.value.length.toLocaleString("zh-CN")} / 100,000`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function riskClass(risk) {
  return `risk-${String(risk || "").toLowerCase()}`;
}

function listItems(items, renderItem) {
  if (!items || items.length === 0) return '<p class="subtle">暂无记录</p>';
  return `<ol class="list">${items.map(renderItem).join("")}</ol>`;
}

function renderJsonValue(value, key = null) {
  if (value === null) return `<span class="json-string">null</span>`;
  if (typeof value === "string") return `<span class="json-string">&quot;${escapeHtml(value)}&quot;</span>`;
  if (typeof value === "number") return `<span class="json-number">${value}</span>`;
  if (typeof value === "boolean") return `<span class="json-boolean">${value}</span>`;
  const entries = Array.isArray(value) ? value.map((item, index) => [index, item]) : Object.entries(value);
  const open = Array.isArray(value) ? "[" : "{";
  const close = Array.isArray(value) ? "]" : "}";
  const id = `json-${Math.random().toString(36).slice(2)}`;
  const children = entries.map(([entryKey, entryValue]) => `<div class="json-node"><span class="json-key">${escapeHtml(entryKey)}</span>: ${renderJsonValue(entryValue, entryKey)}</div>`).join("");
  return `<button class="json-toggle" data-json-toggle="${id}" type="button">▼</button>${open}<span id="${id}">${children}</span>${close}`;
}

function renderJsonTree(jsonText) {
  try {
    jsonTree.innerHTML = renderJsonValue(JSON.parse(jsonText));
    jsonTree.querySelectorAll("[data-json-toggle]").forEach((button) => button.addEventListener("click", () => {
      const target = document.querySelector(`#${button.dataset.jsonToggle}`);
      const collapsed = target.hidden;
      target.hidden = !collapsed;
      button.textContent = collapsed ? "▼" : "▶";
    }));
  } catch {
    jsonTree.textContent = jsonText;
  }
}

function renderStructured(report) {
  const graph = report.graph;
  const analysis = report.analysis;
  const rhetoric = report.rhetoric;
  const typeCounts = graph.claims.reduce((counts, claim) => {
    counts[claim.type] = (counts[claim.type] || 0) + 1;
    return counts;
  }, {});
  const weakestClaim = graph.claims.find((claim) => claim.id === analysis.weakest_link?.claim_id);
  const chains = listItems(analysis.reasoning_chains, (chain) => {
    const labels = chain.claim_ids.map((claimId) => {
      const claim = graph.claims.find((entry) => entry.id === claimId);
      return claim ? `${claim.type}: ${claim.content}` : claimId;
    });
    return `<li>${escapeHtml(labels.join(" → "))}</li>`;
  });
  const claims = graph.claims.map((claim) => `
    <tr>
      <td>${escapeHtml(claim.type)}</td>
      <td>${escapeHtml(claim.content)}</td>
      <td>${escapeHtml(claim.evidence_status)}</td>
    </tr>`).join("");
  const assumptions = listItems(analysis.load_bearing_assumptions, (item) => {
    const claim = graph.claims.find((entry) => entry.id === item.claim_id);
    return `<li>${escapeHtml(claim?.content || item.claim_id)}<p>${escapeHtml(item.reason)}</p></li>`;
  });
  const alternatives = listItems(report.alternatives, (item) => `
    <li>${escapeHtml(item.content)}
      <p>排除方法：${escapeHtml(item.exclusion_method)}</p>
      <p>需要数据：${escapeHtml(item.required_data.join("、"))}；成本：${escapeHtml(item.cost)}</p>
    </li>`);
  const verification = listItems(report.verification_steps, (item) => `
    <li>${escapeHtml(item.experiment)}
      <p>成本：${escapeHtml(item.cost)}；周期：${escapeHtml(item.duration)}</p>
    </li>`);
  const weakest = analysis.weakest_link
    ? `<p class="subtle">${escapeHtml(analysis.weakest_link.reason)}</p>`
    : '<p class="subtle">暂无最弱环节</p>';
  const weakestContent = weakestClaim?.content || "暂无连接主要结论的承重假设";
  const nextAction = weakestClaim
    ? "优先验证这个声明，再决定是否扩大行动。"
    : "先补充可观测事实或证据，再继续外推。";
  structuredView.classList.remove("empty-state");
  structuredView.innerHTML = `
    <section class="audit-focus">
      <div class="audit-focus-copy">
        <p class="section-kicker">AUDIT FOCUS</p>
        <h3>先看最影响结论的一步</h3>
        <p>${escapeHtml(weakestContent)}</p>
      </div>
      <div class="audit-focus-action"><span>建议动作</span><strong>${escapeHtml(nextAction)}</strong></div>
    </section>
    <section class="summary-grid">
      <div><strong>${graph.claims.length}</strong><span>声明总数</span></div>
      <div><strong>${typeCounts.ASSUMPTION || 0}</strong><span>隐藏假设</span></div>
      <div><strong>${report.alternatives.length}</strong><span>替代解释</span></div>
      <div><strong>${report.verification_steps.length}</strong><span>验证步骤</span></div>
    </section>
    <section class="report-block">
      <h3>压缩后的真实观点</h3>
      <p>${escapeHtml(graph.compressed_view)}</p>
    </section>
    <section class="report-block">
      <h3>修辞风险</h3>
      <div class="risk-line">
        <span class="risk-badge ${riskClass(rhetoric.risk)}">${escapeHtml(rhetoric.risk)}</span>
        <span class="subtle">${rhetoric.flags.length ? `命中：${escapeHtml(rhetoric.flags.join("、"))}` : "未命中预设修辞词"}</span>
      </div>
    </section>
    <section class="report-block">
      <h3>声明结构</h3>
      <div class="table-wrap"><table class="claim-table"><thead><tr><th>类型</th><th>内容</th><th>证据状态</th></tr></thead><tbody>${claims}</tbody></table></div>
    </section>
    <section class="report-block">
      <h3>推理链</h3>
      ${chains}
    </section>
    <section class="report-block">
      <h3>最大承重假设</h3>
      ${assumptions}
      <div class="subtle" style="margin-top:14px">最弱环节：${escapeHtml(weakestClaim?.content || "暂无")}</div>
      ${weakest}
    </section>
    <section class="report-block">
      <h3>替代解释</h3>
      ${alternatives}
    </section>
    <section class="report-block">
      <h3>当前判断</h3>
      <p><strong>合理洞察：</strong>${escapeHtml(report.judgement.reasonable_insights.join("；") || "暂无")}</p>
      <p style="margin-top:10px"><strong>未经验证外推：</strong>${escapeHtml(report.judgement.unverified_extrapolations.join("；") || "暂无")}</p>
    </section>
    <section class="report-block">
      <h3>下一步验证</h3>
      ${verification}
    </section>
    ${report.warnings?.length ? `<section class="report-block"><h3>审计提示</h3>${listItems(report.warnings, (item) => `<li>${escapeHtml(item)}</li>`)}</section>` : ""}`;
}

function setView(view) {
  document.querySelectorAll(".view-tab").forEach((tab) => {
    const active = tab.dataset.view === view;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  structuredView.hidden = view !== "structured";
  markdownView.hidden = view !== "markdown";
  jsonView.hidden = view !== "json";
}

function downloadArtifact(kind) {
  const text = latestArtifacts[kind];
  if (!text) return;
  const blob = new Blob([text], { type: kind === "json" ? "application/json" : "text/markdown" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = kind === "json" ? "reasoning-audit.json" : "reasoning-audit.md";
  link.click();
  URL.revokeObjectURL(link.href);
}

async function copyArtifact(kind, button) {
  const text = latestArtifacts[kind];
  if (!text) return;
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
  } else {
    const helper = document.createElement("textarea");
    helper.value = text;
    helper.style.position = "fixed";
    helper.style.opacity = "0";
    document.body.appendChild(helper);
    helper.select();
    document.execCommand("copy");
    helper.remove();
  }
  const original = button.textContent;
  button.textContent = "已复制";
  setTimeout(() => { button.textContent = original; }, 1400);
}

async function runAudit() {
  const text = opinion.value.trim();
  if (!text) {
    errorMessage.textContent = "请输入要审计的观点。";
    errorWrap.hidden = false;
    opinion.focus();
    return;
  }
  errorWrap.hidden = true;
  auditButton.disabled = true;
  startProgress(includeAlternatives.checked);
  try {
    const response = await fetch("/api/audit/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        provider: provider.value,
        include_alternatives: includeAlternatives.checked,
        api_key: apiKey.value.trim() || null,
        base_url: baseUrl.value.trim() || null,
        model: model.value.trim() || null,
        timeout: Number(timeout.value || 60),
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "审计失败");
    const result = await pollAuditJob(payload.job_id);
    renderStructured(result.report);
    latestArtifacts = { markdown: result.markdown, json: result.json };
    markdownSource.textContent = result.markdown;
    renderJsonTree(result.json);
    reportStatus.textContent = `完成 · ${result.report.graph.claims.length} 条声明 · ${result.report.rhetoric.risk} 修辞风险`;
    finishProgress(result.stages, result.duration_ms);
    setView("structured");
  } catch (error) {
    reportStatus.textContent = "审计失败";
    failProgress();
    errorMessage.textContent = explainError(error.message);
    errorWrap.hidden = false;
  } finally {
    if (provider.value === "openai-compatible" && !errorWrap.hidden) {
      apiKey.dataset.retry = "true";
    } else if (provider.value === "openai-compatible") {
      apiKey.value = "";
      delete apiKey.dataset.retry;
    }
    auditButton.disabled = false;
  }
}

auditButton.addEventListener("click", runAudit);
retryButton.addEventListener("click", runAudit);
clearButton.addEventListener("click", () => { opinion.value = ""; updateCharacterCount(); opinion.focus(); });
opinion.addEventListener("input", updateCharacterCount);
opinion.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    runAudit();
  }
});
document.querySelector("#dismiss-onboarding").addEventListener("click", () => { onboarding.hidden = true; });
document.querySelector("#open-provider-settings").addEventListener("click", () => {
  openProviderSettings(true);
});
document.querySelector("#edit-provider-settings").addEventListener("click", () => openProviderSettings(false));
document.querySelector("#close-provider-settings").addEventListener("click", () => providerSettings.close());
document.querySelector("#cancel-provider-settings").addEventListener("click", () => providerSettings.close());
document.querySelector("#save-provider-settings").addEventListener("click", () => {
  updateProviderHint();
  providerSettings.close();
});
provider.addEventListener("change", () => {
  updateProviderHint();
  if (provider.value === "openai-compatible" && !baseUrl.value.trim()) openProviderSettings(false);
});
providerPreset.addEventListener("change", applyPreset);
model.addEventListener("input", updateProviderHint);
baseUrl.addEventListener("input", updateProviderHint);
providerSettings.addEventListener("click", (event) => {
  const bounds = providerSettings.getBoundingClientRect();
  const inside = event.clientX >= bounds.left && event.clientX <= bounds.right
    && event.clientY >= bounds.top && event.clientY <= bounds.bottom;
  if (!inside) providerSettings.close();
});
document.querySelectorAll("[data-download]").forEach((button) => button.addEventListener("click", () => downloadArtifact(button.dataset.download)));
document.querySelectorAll("[data-copy]").forEach((button) => button.addEventListener("click", () => copyArtifact(button.dataset.copy, button)));
document.querySelectorAll(".view-tab").forEach((tab) => tab.addEventListener("click", () => setView(tab.dataset.view)));

fetch("/api/health")
  .then((response) => response.json())
  .then((data) => {
    const state = document.querySelector("#service-state");
    if (data.web_build !== EXPECTED_WEB_BUILD) {
      state.querySelector(".state-dot").classList.add("is-error");
      state.querySelector("span:last-child").textContent = `服务版本过旧 · 后端 build ${data.web_build ?? "未知"} · 请重启`;
    } else {
      state.querySelector(".state-dot").classList.add("is-ready");
      const providerState = data.openai_configured ? "Provider 已配置" : "Mock 可用";
      state.querySelector("span:last-child").textContent = `服务在线 · ${providerState} · build ${data.web_build}`;
    }
    if (data.openai_defaults?.model) model.placeholder = data.openai_defaults.model;
    if (data.openai_defaults?.base_url && !baseUrl.value) baseUrl.value = data.openai_defaults.base_url;
  })
  .catch(() => {
    const state = document.querySelector("#service-state");
    state.querySelector(".state-dot").classList.add("is-error");
    state.querySelector("span:last-child").textContent = "服务不可用";
  });

updateProviderHint();
updateCharacterCount();
