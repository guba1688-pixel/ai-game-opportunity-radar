const perspectiveDefinitions = {
  overview: {
    label: '机会总览',
    title: '机会全景',
    description: '先看综合适配度、当前阶段和下一步，再进入具体空间理解机会。'
  },
  market: {
    label: '市场视角',
    title: '市场空间',
    description: '从地区、品类、目标需求和市场证据判断哪里正在形成可验证需求。'
  },
  industry: {
    label: '行业视角',
    title: '行业结构',
    description: '观察产业链痛点、供给来源和价值迁移，判断公司可以站在哪个环节。'
  },
  product: {
    label: '产品视角',
    title: '产品解法',
    description: '把资讯转成明确的产品或服务形态，并检查 30 天内能否形成最小验证。'
  },
  channel: {
    label: '渠道视角',
    title: '渠道空间',
    description: '同时查看产品供给入口与用户获取路径，寻找现有渠道资产可放大的切口。'
  },
  business: {
    label: '商业视角',
    title: '商业空间',
    description: '聚焦谁付钱、如何收费、现金投入和回本逻辑，判断机会是否能成为生意。'
  },
  competition: {
    label: '竞争视角',
    title: '竞争空间',
    description: '识别竞品与替代方案，再从公司优势中寻找不靠同质化竞争的进入点。'
  },
  capability: {
    label: '能力资产',
    title: '能力空间',
    description: '检查渠道、投放、素材、本地化和运营资产的复用程度，以及必须补齐的能力。'
  },
  risk: {
    label: '风险视角',
    title: '风险空间',
    description: '把风险、证据缺口和止损条件放到第一屏，避免只看机会不看失败成本。'
  }
};

const perspectiveShell = `<div class="lens-shell"><div class="lens-heading"><div><p class="eyebrow">MULTI-DIMENSIONAL OPPORTUNITY SPACE</p><h2 id="lens-title">机会全景</h2></div><p id="lens-description">先看综合适配度、当前阶段和下一步，再进入具体空间理解机会。</p></div><div class="lens-tabs" role="tablist" aria-label="机会分析视角"><button class="lens-tab active" data-lens="overview">机会总览</button><button class="lens-tab" data-lens="market">市场视角</button><button class="lens-tab" data-lens="industry">行业视角</button><button class="lens-tab" data-lens="product">产品视角</button><button class="lens-tab" data-lens="channel">渠道视角</button><button class="lens-tab" data-lens="business">商业视角</button><button class="lens-tab" data-lens="competition">竞争视角</button><button class="lens-tab" data-lens="capability">能力资产</button><button class="lens-tab" data-lens="risk">风险视角</button></div><div id="lens-summary" class="lens-summary"></div></div>`;
document.querySelector('.game-radar-panel').insertAdjacentHTML('afterend', perspectiveShell);
$('.brand small').textContent = 'RADAR & INTELLIGENCE · V0.6';
document.querySelector('[data-view="opportunities"]').textContent = '游戏市场雷达';
$('.boundary').innerHTML = '<strong>证据分级 · 决策需复核</strong><p>已接入的真实信号按 A/B 级标注；带“演示数据”的旧项目仅用于展示流程。预算、回收与机会评分均为验证假设，不构成业绩承诺。</p>';

state.lens = localStorage.getItem('radar-lens') || 'overview';
if (!perspectiveDefinitions[state.lens]) state.lens = 'overview';

const perspectiveArray = value => Array.isArray(value) ? value.filter(Boolean) : (value ? [value] : []);
const perspectiveJoin = (value, fallback = '待补充') => perspectiveArray(value).map(esc).join('；') || `<span class="missing">${fallback}</span>`;
const perspectivePlain = (value, fallback = '待补充') => value ? esc(value) : `<span class="missing">${fallback}</span>`;
const perspectiveAverage = (rows, getter) => rows.length ? Math.round(rows.reduce((sum, row) => sum + Number(getter(row) || 0), 0) / rows.length * 10) / 10 : 0;
const perspectiveMoney = value => `¥${Number(value || 0).toLocaleString()}`;

function perspectiveFocus(o) {
  const firstEvidence = perspectiveArray(o.market_evidence).slice(0, 2);
  const firstCompetitors = perspectiveArray(o.competitors).slice(0, 3);
  const firstRisks = perspectiveArray(o.risks).slice(0, 2);
  const firstGaps = perspectiveArray(o.evidence_gaps).slice(0, 2);
  const firstStops = perspectiveArray(o.stop_loss_conditions).slice(0, 1);
  const map = {
    market: ['市场坐标', `${perspectiveJoin(o.regions)} · ${perspectiveJoin(o.genres)}`, '目标需求与证据', `${perspectivePlain(o.target_users)}${firstEvidence.length ? `；${perspectiveJoin(firstEvidence)}` : ''}`],
    industry: ['产业链痛点', perspectivePlain(o.pain), '供给与行业位置', perspectivePlain(o.product_source)],
    product: ['产品或服务形态', perspectivePlain(o.product_solution), '30 天最小验证', perspectivePlain(o.mvp)],
    channel: ['产品/合作方入口', perspectivePlain(o.product_source), '获客与渠道路径', perspectivePlain(o.acquisition)],
    business: ['商业模式', perspectivePlain(o.pricing), '投入与回本逻辑', `${perspectiveMoney(o.budget_30d)} / 30天；${perspectivePlain(o.payback_logic)}`],
    competition: ['竞品与替代方案', perspectiveJoin(firstCompetitors, '尚未补充竞品'), '差异化切口', perspectivePlain(o.publisher_fit)],
    capability: ['可复用能力', perspectivePlain(o.publisher_fit), '能力缺口', perspectivePlain(o.publisher_misfit)],
    risk: ['主要风险', perspectiveJoin(firstRisks, '尚未识别主要风险'), '证据缺口与止损', `${perspectiveJoin(firstGaps, '暂无证据缺口')}；${perspectiveJoin(firstStops, '待定义止损条件')}`]
  };
  return map[state.lens] || [];
}

function perspectiveRank(o) {
  const scores = o.scores || {};
  const map = {
    overview: Number(o.total_score || 0),
    market: perspectiveArray(o.market_evidence).length * 6 + perspectiveArray(o.regions).length * 3 + Number(scores.product_access || 0) * 2,
    industry: perspectiveArray(o.market_evidence).length * 4 + Number(scores.strategic_synergy || 0) * 5,
    product: Number(scores.delivery_simplicity || 0) * 5 + Number(scores.product_access || 0) * 4,
    channel: Number(scores.channel_reuse || 0) * 6 + Number(scores.ua_reuse || 0) * 4,
    business: Number(scores.unit_economics_verifiability || 0) * 5 + Number(scores.payback_speed || 0) * 5 + Number(scores.cash_exposure || 0) * 3,
    competition: perspectiveArray(o.competitors).length * 6 + Number(scores.strategic_synergy || 0) * 4,
    capability: Number(o.total_score || 0),
    risk: perspectiveArray(o.risks).length * 6 + perspectiveArray(o.evidence_gaps).length * 5 + (['hold', 'reject'].includes(o.decision_status) ? 8 : 0)
  };
  return map[state.lens] || 0;
}

function perspectiveMetrics(rows) {
  const unique = key => new Set(rows.flatMap(row => perspectiveArray(row[key]))).size;
  const sum = key => rows.reduce((total, row) => total + Number(row[key] || 0), 0);
  const countItems = key => rows.reduce((total, row) => total + perspectiveArray(row[key]).length, 0);
  const countScore = (key, minimum = 4) => rows.filter(row => Number(row.scores?.[key] || 0) >= minimum).length;
  const maps = {
    overview: [['当前机会', `${rows.length} 个`], ['平均适配度', perspectiveAverage(rows, row => row.total_score)], ['阶段预算暴露', perspectiveMoney(sum('stage_budget_limit'))]],
    market: [['覆盖市场', `${unique('regions')} 个`], ['覆盖品类', `${unique('genres')} 个`], ['市场证据', `${countItems('market_evidence')} 条`]],
    industry: [['业务机会', `${rows.filter(row => row.opportunity_type === 'business').length} 个`], ['AI×游戏', `${rows.filter(row => row.sector === 'ai_game').length} 个`], ['战略协同较强', `${countScore('strategic_synergy')} 个`]],
    product: [['已有 MVP', `${rows.filter(row => row.mvp).length} 个`], ['平均验证周期', `${perspectiveAverage(rows, row => row.cycle_weeks)} 周`], ['交付较轻', `${countScore('delivery_simplicity')} 个`]],
    channel: [['供给入口明确', `${rows.filter(row => row.product_source).length} 个`], ['渠道复用较强', `${countScore('channel_reuse')} 个`], ['投放复用较强', `${countScore('ua_reuse')} 个`]],
    business: [['当前预算暴露', perspectiveMoney(sum('stage_budget_limit'))], ['30天预算合计', perspectiveMoney(sum('budget_30d'))], ['回本速度较快', `${countScore('payback_speed')} 个`]],
    competition: [['竞品/替代记录', `${countItems('competitors')} 条`], ['已覆盖竞品', `${rows.filter(row => perspectiveArray(row.competitors).length).length} 个机会`], ['待补竞品', `${rows.filter(row => !perspectiveArray(row.competitors).length).length} 个机会`]],
    capability: [['平均适配度', perspectiveAverage(rows, row => row.total_score)], ['轻/中资产机会', `${rows.filter(row => ['light', 'medium'].includes(row.asset_level)).length} 个`], ['战略协同较强', `${countScore('strategic_synergy')} 个`]],
    risk: [['主要风险', `${countItems('risks')} 条`], ['证据缺口', `${countItems('evidence_gaps')} 条`], ['暂缓/淘汰', `${rows.filter(row => ['hold', 'reject'].includes(row.decision_status)).length} 个`]]
  };
  return maps[state.lens] || maps.overview;
}

function renderPerspectiveHeader(rows) {
  const definition = perspectiveDefinitions[state.lens];
  $('#lens-title').textContent = definition.title;
  $('#lens-description').textContent = definition.description;
  $('#lens-summary').innerHTML = perspectiveMetrics(rows).map(([label, value]) => `<div class="lens-metric"><small>${label}</small><strong>${value}</strong></div>`).join('');
  document.querySelectorAll('.lens-tab').forEach(button => button.classList.toggle('active', button.dataset.lens === state.lens));
}

function renderOpportunityCardsByPerspective() {
  const rows = state.opportunities.filter(o => o.opportunity_type === state.type).sort((a, b) => perspectiveRank(b) - perspectiveRank(a));
  const root = $('#opportunity-list');
  renderPerspectiveHeader(rows);
  if (!rows.length) {
    root.innerHTML = '<div class="empty">当前筛选和视角下没有项目。</div>';
    return;
  }
  root.innerHTML = rows.map(o => {
    const focus = perspectiveFocus(o);
    const body = state.lens === 'overview'
      ? `<p class="action"><b>做什么：</b>${esc(o.product_solution)}</p><div class="why-grid"><div><small>为什么适合</small>${esc(o.publisher_fit)}</div><div><small>主要不适配</small>${esc(o.publisher_misfit)}</div></div>`
      : `<div class="perspective-grid"><div class="perspective-focus"><small>${focus[0]}</small><p>${focus[1]}</p></div><div class="perspective-focus"><small>${focus[2]}</small><p>${focus[3]}</p></div></div><p class="perspective-action"><b>${state.lens === 'risk' ? '核验动作' : '下一步验证'}：</b>${esc(o.validation_action)}</p>`;
    return `<article class="card decision-${o.decision_status}" data-id="${o.id}"><div class="card-top"><div><div class="tags"><span class="tag lens">${perspectiveDefinitions[state.lens].label}</span><span class="tag decision ${o.decision_status}">${labels[o.decision_status]}</span><span class="tag ${o.asset_level}">${labels[o.asset_level]}</span>${o.is_demo ? '<span class="tag demo">演示数据</span>' : ''}</div><h3>${esc(o.title)}</h3><div class="scope">${o.regions.map(esc).join(' / ')} · ${o.genres.map(esc).join(' / ')}</div></div><div class="fit-score"><b>${o.total_score}</b><small>综合适配度</small></div></div>${body}<div class="stage-row"><span>当前：<b>${labels[o.validation_stage]}</b></span><span>负责人：<b>${esc(o.owner)}</b></span><span>阶段预算：<b>${perspectiveMoney(o.stage_budget_limit)}</b></span></div><div class="next"><b>行动：</b>${esc(o.owner)} · ${esc(o.next_action_due || '待排期')}</div><div class="stop"><b>停止：</b>${esc(o.stop_loss_conditions[0] || o.stage_stop_condition || '待定义')}</div></article>`;
  }).join('');
  root.querySelectorAll('.card').forEach(card => card.onclick = () => showDetail(Number(card.dataset.id)));
}

renderOpportunities = renderOpportunityCardsByPerspective;
download = async function downloadPerspectiveExport(format) {
  try {
    const blob = await api(`/api/export.${format}?${queryString()}`);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `mobile-publishing-opportunities-v0.5.0.${format}`;
    anchor.click();
    URL.revokeObjectURL(url);
    toast('已导出 ' + format.toUpperCase());
  } catch (error) {
    toast(error.message);
  }
};
document.querySelectorAll('.lens-tab').forEach(button => button.onclick = () => {
  state.lens = button.dataset.lens;
  localStorage.setItem('radar-lens', state.lens);
  renderOpportunities();
});
renderOpportunities();
