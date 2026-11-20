const governanceButton = document.createElement('button');
governanceButton.className = 'nav';
governanceButton.dataset.view = 'update-rules';
governanceButton.textContent = '更新规则中心';
$('.sidebar nav').appendChild(governanceButton);

const governanceView = document.createElement('section');
governanceView.id = 'update-rules';
governanceView.className = 'view';
governanceView.innerHTML = `<div class="section-head"><div><p class="eyebrow">UPDATE GOVERNANCE</p><h2>更新规则中心</h2></div><p>明确何时更新、更新什么、如何去重，以及什么时候可以计算机会规模。</p></div><div id="governance-content"><div class="empty">正在读取规则...</div></div>`;
document.querySelector('main').appendChild(governanceView);

const governanceList = value => (Array.isArray(value) ? value : []).map(item => `<li>${esc(item)}</li>`).join('');

async function loadGovernanceRules() {
  const root = $('#governance-content');
  try {
    const rules = await api('/api/update-rules');
    const runtime = rules.runtime;
    const dedupeNames = {exact: '精确重复', event_cluster: '同一事件', opportunity_merge: '同一机会', contradiction: '冲突证据'};
    root.innerHTML = `<div class="governance-status"><div><small>当前执行</small><strong>${esc(runtime.actual_trigger)}</strong></div><div><small>真实数据源</small><strong>${runtime.live_sources} 个</strong></div><div><small>当前资讯 / 机会</small><strong>${runtime.signal_count} / ${runtime.opportunity_count}</strong></div><div><small>规则版本</small><strong>${esc(rules.rules_version)}</strong></div></div><div class="governance-notice"><b>${esc(runtime.execution_state)}：</b>${esc(runtime.notice)}</div><div class="governance-grid">${rules.schedules.map(rule => `<article class="rule-card"><h3>${esc(rule.name)}</h3><div class="rule-meta"><span>${esc(rule.frequency)}</span>${rule.times.map(time => `<span>${esc(time)}</span>`).join('')}</div><ul>${governanceList(rule.content)}</ul><p><b>产出：</b>${esc(rule.output)}</p></article>`).join('')}</div><section class="governance-block"><h3>每轮更新内容</h3><p>八个空间维度都必须满足最小字段要求，缺失字段进入补证而不是自动形成结论。</p><div class="governance-dimensions">${rules.content_dimensions.map(item => `<div class="dimension-card"><strong>${esc(item.name)}</strong><span>${item.required.map(esc).join(' · ')}</span></div>`).join('')}</div></section><section class="governance-block"><h3>重叠、合并与冲突规则</h3>${Object.entries(rules.deduplication).map(([key, item]) => `<div class="dedupe-step"><b>${dedupeNames[key]}</b><span>${esc(item.rule)}<br><small>处理：${esc(item.action)}</small></span><em>${esc(item.status)}</em></div>`).join('')}</section><section class="governance-block"><h3>证据有效期</h3><div class="governance-grid">${rules.freshness.map(item => `<div class="dimension-card"><strong>${esc(item.content)} · ${esc(item.valid_for)}</strong><span>过期处理：${esc(item.expired_action)}</span></div>`).join('')}</div></section><section class="governance-block"><h3>机会规模与上限</h3><p>${esc(rules.ceiling_model.formula)}</p><div class="rule-meta">${rules.ceiling_model.scenarios.map(item => `<span>${esc(item)}</span>`).join('')}<span>${esc(rules.ceiling_model.frequency)}</span></div><p><b>必要输入：</b>${rules.ceiling_model.required_inputs.map(esc).join(' · ')}</p><p><b>输出：</b>${rules.ceiling_model.outputs.map(esc).join(' · ')}</p><p class="missing">${esc(rules.ceiling_model.confidence_gate)}</p></section>`;
  } catch (error) {
    root.innerHTML = `<div class="empty">规则读取失败：${esc(error.message)}</div>`;
  }
}

governanceButton.onclick = () => {
  document.querySelectorAll('.nav,.view').forEach(item => item.classList.remove('active'));
  governanceButton.classList.add('active');
  governanceView.classList.add('active');
  loadGovernanceRules();
};

