const sourceTypeLabels={demo:'演示数据',manual_import:'人工导入',live_online:'真实在线'};
const freshnessLabels={fresh:'有效',stale:'已过期',unknown:'日期未知',demo:'演示'};

const sourceNav=document.createElement('button');
sourceNav.className='nav';
sourceNav.dataset.view='source-registry';
sourceNav.textContent='数据来源';
document.querySelector('.sidebar nav').appendChild(sourceNav);

const sourceView=document.createElement('section');
sourceView.id='source-registry';
sourceView.className='view';
sourceView.innerHTML=`<div class="section-head"><div><p class="eyebrow">SOURCE REGISTRY</p><h2>数据来源与导入</h2></div><p>演示、人工导入和真实在线数据分开登记；没有授权时只展示接入计划。</p></div>
<div id="source-kpis" class="source-kpis"></div>
<div class="source-layout">
  <div>
    <div class="source-panel admin-only"><h3>导入本地快照</h3><form id="import-form" class="import-form">
      <label class="wide">本地文件<input name="file" type="file" accept=".csv,.json,.html,.htm" required></label>
      <label>来源名称<input name="source_name" required placeholder="例如：内部市场报告"></label>
      <label>赛道<select name="sector"><option value="ai_game">AI×游戏</option><option value="game">游戏</option><option value="ai">AI</option></select></label>
      <label>观察日期<input name="observed_at" type="date"></label>
      <label>证据类型<select name="evidence_type"><option value="third_party_estimate">第三方估算</option><option value="model_inference">模型推断</option><option value="official">官方</option></select></label>
      <label>置信等级<select name="confidence_grade"><option>C</option><option>D</option><option>B</option><option>A</option><option>E</option></select></label>
      <label><input name="is_estimate" type="checkbox" checked> 包含估算或推断</label>
      <div class="wide"><button class="primary" type="submit">校验、备份并导入</button></div>
      <p id="import-state" class="wide source-muted">文件仅发送到当前本地服务；导入前自动备份 SQLite。</p>
    </form></div>
    <div class="source-panel" style="margin-top:14px"><h3>计划连接器</h3><div id="connector-list" class="connector-list"></div></div>
  </div>
  <div class="source-panel"><h3>来源登记</h3><div class="table-wrap"><table class="source-table"><thead><tr><th>来源</th><th>类型</th><th>健康</th><th>信号</th><th>最近成功/引用</th></tr></thead><tbody id="source-list"></tbody></table></div></div>
</div>`;
document.querySelector('main').appendChild(sourceView);

function sourceRefText(value){return value?esc(value):'未登记'}
async function loadSources(){
  try{
    const [sources,connectors,dashboard]=await Promise.all([api('/api/sources'),api('/api/source-connectors'),api('/api/dashboard')]);
    const byType=dashboard.signals_by_source_type||{};
    $('#source-kpis').innerHTML=[['演示资讯',byType.demo||0],['人工导入',byType.manual_import||0],['真实在线',byType.live_online||0],['已登记来源',sources.length]].map(([a,b])=>`<div class="source-kpi"><small>${a}</small><strong>${b}</strong></div>`).join('');
    $('#source-list').innerHTML=sources.map(s=>`<tr><td><strong>${esc(s.name)}</strong><small class="source-muted">${esc(s.source_key)}</small></td><td>${sourceTypeLabels[s.source_type]||esc(s.source_type)}</td><td><span class="source-health health-${esc(s.health_status)}">${esc(s.health_status)}</span>${s.last_error?`<small class="source-muted">${esc(s.last_error)}</small>`:''}</td><td>${Number(s.signal_count||0)}</td><td>${esc(s.last_success_at||'尚未成功')}<small class="source-muted">${sourceRefText(s.source_ref)}</small></td></tr>`).join('');
    $('#connector-list').innerHTML=(connectors.connectors||[]).map(c=>`<div class="connector"><strong>${esc(c.name)}</strong><small>${esc(c.authority)} · ${esc(c.status)} · ${esc(c.auth)}</small><div>${esc(c.scope)}</div></div>`).join('');
  }catch(error){toast(error.message)}
}

sourceNav.onclick=()=>{
  document.querySelectorAll('.nav,.view').forEach(x=>x.classList.remove('active'));
  sourceNav.classList.add('active');sourceView.classList.add('active');loadSources();
};

$('#import-form [name=file]').onchange=event=>{
  const file=event.target.files[0];if(!file)return;
  if(!$('#import-form [name=source_name]').value)$('#import-form [name=source_name]').value=file.name.replace(/\.[^.]+$/,'');
  const match=file.name.match(/(20\d{2})(\d{2})(\d{2})/);if(match)$('#import-form [name=observed_at]').value=`${match[1]}-${match[2]}-${match[3]}`;
};
$('#import-form').onsubmit=async event=>{
  event.preventDefault();const form=event.currentTarget,file=form.elements.file.files[0],status=$('#import-state');
  if(!file)return;if(file.size>5_000_000){status.textContent='文件超过5 MB，未上传。';return}
  status.textContent='正在校验并创建导入前备份…';
  try{
    const format=file.name.split('.').pop().toLowerCase().replace('htm','html');
    const result=await api('/api/import',{method:'POST',body:JSON.stringify({format,content:await file.text(),source_ref:file.name,source_name:form.elements.source_name.value,sector:form.elements.sector.value,observed_at:form.elements.observed_at.value,evidence_type:form.elements.evidence_type.value,confidence_grade:form.elements.confidence_grade.value,is_estimate:form.elements.is_estimate.checked})});
    status.textContent=`导入完成：接收 ${result.received}，新增 ${result.inserted}，重复 ${result.duplicates}，错误 ${result.errors.length}。`;
    await loadSources();
  }catch(error){status.textContent='导入失败：'+error.message}
};

loadSignals=async function loadTraceableSignals(){
  try{
    const rows=await api('/api/signals');
    $('#signal-list').innerHTML=rows.map(s=>`<article class="signal"><div><h3>${esc(s.title)} <span class="tag">${sourceTypeLabels[s.source_type]||esc(s.source_type)}</span>${s.is_estimate?'<span class="tag demo">估算/推断</span>':''}</h3><p>${esc(s.summary)}</p><div class="signal-meta">${labels[s.sector]} · ${esc(s.source_name)} · 采集：${esc(s.collected_at)} · 更新：${esc(s.updated_at||s.collected_at)} · 观察：${esc(s.observed_period)} · 原始引用：${sourceRefText(s.source_ref)} ${s.source_url?`· <a href="${esc(s.source_url)}" target="_blank" rel="noopener">原始链接</a>`:''}</div></div><span class="evidence signal-${esc(s.freshness_status)}">${labels[s.evidence_type]||esc(s.evidence_type)} · ${s.confidence_grade}级 · ${freshnessLabels[s.freshness_status]||esc(s.freshness_status)}</span></article>`).join('');
  }catch(error){toast(error.message)}
};

const originalShowDetail=showDetail;
showDetail=function showTraceableDetail(id){
  originalShowDetail(id);
  const opportunity=state.current;
  if(!opportunity)return;
  const links=opportunity.evidence_links||[];
  const html=links.length?links.map(link=>`<li><strong>${esc(link.relation_type)}</strong> · ${esc(link.title)} · ${sourceTypeLabels[link.source_type]||esc(link.source_type)} · ${link.is_estimate?'估算/推断':'直接证据'} · ${freshnessLabels[link.freshness_status]||esc(link.freshness_status)}<br><small>${esc(link.source_ref||link.source_url||'未登记原始引用')}</small></li>`).join(''):'<li class="missing">尚未关联可追溯证据；该机会不得自动晋级或形成确定性金额结论。</li>';
  $('#detail .detail-grid').insertAdjacentHTML('beforeend',`<div class="detail-block wide"><strong>可追溯证据 · ${links.length?'已关联':'缺失'}</strong><ul>${html}</ul></div>`);
};
