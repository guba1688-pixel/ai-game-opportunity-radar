const intelLabels={manual_import:'手动提交',api_ingest:'API自动写入',live_online:'在线采集',demo:'演示来源',fresh:'有效',stale:'已过期',unknown:'待核实',official:'官方事实',third_party_estimate:'第三方估算',model_inference:'分析推断'};
const intelDate=value=>value?String(value).slice(0,10):'未标注';

function switchWorkspace(view){
  document.querySelectorAll('.nav,.view').forEach(node=>node.classList.remove('active'));
  document.querySelector(`.nav[data-view="${view}"]`)?.classList.add('active');
  $('#'+view)?.classList.add('active');
  if(view==='home')loadIntelligenceHome();
  if(view==='opportunities')loadGameRadarWorkspace();
  if(view==='signals')loadMarketNews();
  if(view==='submit-intelligence')prepareIntelligenceForm();
  if(view==='automation')loadAutomationStatus();
  if(view==='profile')loadProfile();
  if(view==='audit')loadAudit();
}

function gameDashboard(rows){
  const byStage={};rows.forEach(row=>byStage[row.validation_stage]=(byStage[row.validation_stage]||0)+1);
  return {
    recommend_now:rows.filter(row=>row.decision_status==='recommend_now').length,
    need_evidence:rows.filter(row=>row.decision_status==='need_evidence').length,
    paused:rows.filter(row=>['hold','reject'].includes(row.decision_status)).length,
    budget_exposure:rows.reduce((sum,row)=>sum+Number(row.stage_budget_limit||0),0),
    light:rows.filter(row=>row.asset_level==='light').length,medium:rows.filter(row=>row.asset_level==='medium').length,heavy:rows.filter(row=>row.asset_level==='heavy').length,
    average_fit:rows.length?Math.round(rows.reduce((sum,row)=>sum+Number(row.total_score||0),0)/rows.length*10)/10:0,by_stage:byStage,
  };
}

function renderGameRadar(rows){
  const root=$('#game-radar-points'),all=rows.filter(row=>row.opportunity_type==='business'),real=all.filter(row=>!row.is_demo),examples=all.filter(row=>row.is_demo).slice(0,Math.max(0,10-real.length)),business=[...real,...examples].sort((a,b)=>Number(b.total_score)-Number(a.total_score));
  if(!business.length){root.innerHTML='<div class="empty">当前筛选下没有游戏机会。</div>';return}
  const priority={recommend_now:20,need_evidence:43,hold:70,reject:86},seen={};
  root.innerHTML=business.map((row,index)=>{
    const groupIndex=seen[row.decision_status]||0;seen[row.decision_status]=groupIndex+1;
    const offsets=[0,-12,12,-6,6,-17,17],xShift=((groupIndex%3)-1)*3;
    const x=Math.max(7,Math.min(93,8+(Number(row.total_score||0)-55)/40*84+xShift));
    const y=Math.max(8,Math.min(92,(priority[row.decision_status]||50)+offsets[groupIndex%offsets.length]));
    return `<button class="radar-point ${row.is_demo?'demo':''} ${row.decision_status}" style="left:${x}%;top:${y}%" data-radar-id="${row.id}" title="${esc(row.title)}"><b>${esc(row.title)}</b><small>${row.total_score} · ${esc(labels[row.asset_level])}</small></button>`;
  }).join('');
  root.querySelectorAll('[data-radar-id]').forEach(button=>button.onclick=()=>showDetail(Number(button.dataset.radarId)));
}

async function loadGameRadarWorkspace(){
  try{
    const suffix=queryString(),join=suffix?'&'+suffix:'';
    const [meta,game,aiGame]=await Promise.all([api('/api/meta'),api('/api/opportunities?sector=game'+join),api('/api/opportunities?sector=ai_game'+join)]);
    state.opportunities=[...game,...aiGame].sort((a,b)=>Number(b.total_score)-Number(a.total_score));
    renderPermissions(meta.permissions);renderDashboard(gameDashboard(state.opportunities));renderOpportunities();renderGameRadar(state.opportunities);
  }catch(error){toast(error.message)}
}

function sourceRows(rows,limit=6){
  const visible=(rows||[]).filter(row=>row.source_type!=='demo').slice(0,limit);
  if(!visible.length)return '<div class="empty">还没有已接入的真实资讯来源。</div>';
  return visible.map(row=>`<div class="source-row"><i class="source-dot ${esc(row.health_status)}"></i><span title="${esc(row.name)}">${esc(row.name)}</span><small>${row.signal_count||0} 条 · ${esc(intelLabels[row.source_type]||row.source_type)}</small></div>`).join('');
}

function currentWeekWindow(now=new Date()){
  const start=new Date(now);start.setHours(0,0,0,0);start.setDate(start.getDate()-((start.getDay()+6)%7));
  const end=new Date(start);end.setDate(end.getDate()+7);
  const labelDate=value=>`${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,'0')}-${String(value.getDate()).padStart(2,'0')}`;
  const displayEnd=new Date(end);displayEnd.setDate(displayEnd.getDate()-1);
  return {start,end,label:`${labelDate(start)} 至 ${labelDate(displayEnd)}`};
}
function collectedInWindow(row,window){
  const collected=new Date(row.collected_at||'');
  return !Number.isNaN(collected.getTime())&&collected>=window.start&&collected<window.end;
}
function decisionField(summary,label){
  const escaped=label.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),match=String(summary||'').match(new RegExp(`${escaped}[：:]([\\s\\S]*?)(?=事实[：:]|影响[：:]|老板决策[：:]|行动建议[：:]|负责人[：:]|$)`));
  return match?match[1].trim():'';
}
function decisionMeta(row){
  const text=`${row.title||''} ${row.summary||''}`,metric=String(row.metric_name||''),deadlineText=/^\d{4}-\d{2}-\d{2}$/.test(String(row.metric_value||''))?String(row.metric_value):'';
  const deadline=deadlineText?new Date(`${deadlineText}T23:59:59`):null,days=deadline?Math.ceil((deadline-new Date())/86400000):null;
  let type='市场判断';
  if(/增长窗口/.test(metric))type='增长窗口';
  else if(/支付风险|收入影响/.test(metric))type='收入与现金';
  else if(/合规/.test(metric))type='合规与上架';
  else if(/合规|审核|年龄|许可|声明|身份/.test(text))type='合规与上架';
  else if(/支付|费率|分成|收入|回收/.test(text))type='收入与现金';
  else if(/Next Fest|获客|自然量|增长|发行/.test(text))type='增长窗口';
  else if(/留存|原型|产品|玩法/.test(metric+text))type='产品验证';
  const impact=decisionField(row.summary,'影响')||decisionField(row.summary,'为什么重要')||'需结合公司产品与目标市场确认实际影响。';
  const action=decisionField(row.summary,'老板决策')||decisionField(row.summary,'行动建议')||'指定负责人，在本周内完成适用性核查并回报。';
  const owner=decisionField(row.summary,'负责人')||'待指定';
  const urgency=days===null?'本周判断':days<0?'已逾期':days<=7?`${days}天内`:days<=30?`${days}天内`:`${deadlineText}前`;
  const level=days!==null&&days<=7?'critical':days!==null&&days<=30?'urgent':metric.startsWith('老板决策/')?'decision':'observe';
  return {type,impact,action,owner,deadlineText,days,urgency,level};
}
function ceoDecisionRank(row){
  const meta=decisionMeta(row),isDecision=String(row.metric_name||'').startsWith('老板决策/')?0:1,deadline=meta.days===null?9999:meta.days;
  return isDecision*10000+deadline*10+attentionRank(row);
}

async function loadIntelligenceHome(){
  try{
    const [data,aiRows,gameRows,aiGameRows]=await Promise.all([api('/api/intelligence-dashboard'),api('/api/signals?sector=ai'),api('/api/signals?sector=game'),api('/api/signals?sector=ai_game')]);
    const aiSignals=aiRows.filter(row=>!row.is_demo),gameSignals=[...gameRows,...aiGameRows].filter(row=>!row.is_demo).sort((a,b)=>String(b.collected_at).localeCompare(String(a.collected_at))),smallSignals=gameSignals.filter(isSmallStudioSignal),headSignals=gameSignals.filter(row=>!isSmallStudioSignal(row)),allSignals=[...gameSignals,...aiSignals].sort((a,b)=>String(b.collected_at).localeCompare(String(a.collected_at)));
    const official=allSignals.filter(row=>row.evidence_type==='official').length,estimates=allSignals.filter(row=>row.evidence_type==='third_party_estimate').length;
    const week=currentWeekWindow(),weeklySignals=allSignals.filter(row=>collectedInWindow(row,week));
    const decisionSignals=weeklySignals.filter(row=>String(row.metric_name||'').startsWith('老板决策/')),urgentSignals=weeklySignals.filter(row=>{const days=decisionMeta(row).days;return days!==null&&days<=30});
    const focus=weeklySignals.slice().sort((a,b)=>ceoDecisionRank(a)-ceoDecisionRank(b)||String(b.collected_at).localeCompare(String(a.collected_at))).slice(0,4);
    $('#home-update-time').textContent=`决策数据刷新：${new Date().toLocaleString('zh-CN',{hour12:false})}`;
    $('#intel-kpis').innerHTML=[['急',urgentSignals.length,'30天内截止','red'],['决',decisionSignals.length,'待决策事项','amber'],['机',data.recommend_count,'可验证机会','green'],['周',weeklySignals.length,'本周新增','blue'],['证',official,'官方证据','violet']].map(([icon,value,label,tone])=>`<div class="intel-kpi ${tone}"><span class="icon">${icon}</span><div><strong>${value}</strong><small>${label}</small></div></div>`).join('');
    const hero=$('#home .intel-hero');hero.querySelector('.eyebrow').textContent='CEO WEEKLY DECISION DESK';hero.querySelector('h2').textContent=urgentSignals.length?`本周 ${urgentSignals.length} 项临近截止，${decisionSignals.length} 项需要判断`:`本周 ${decisionSignals.length} 项需要老板判断`;hero.querySelector('p:not(.eyebrow)').textContent='先看影响收入、上架和现金安全的变化，再看增长机会；长期政策基线不占用老板注意力。';
    const focusHead=$('#home-focus').closest('.focus-panel').querySelector('.panel-head>div');
    focusHead.querySelector('small').textContent='CEO DECISION PRIORITIES';focusHead.querySelector('h3').textContent='老板本周要拍板';
    let focusWeek=focusHead.querySelector('.focus-week');if(!focusWeek){focusWeek=document.createElement('p');focusWeek.className='panel-explain focus-week';focusHead.appendChild(focusWeek)}
    focusWeek.textContent=`${week.label} · ${urgentSignals.length} 项临近截止 · ${decisionSignals.length} 项待决策 · 每周一换周`;
    $('#home-focus').innerHTML=focus.length?focus.map(ceoDecisionCard).join(''):'<div class="weekly-empty"><b>本周暂无需要老板拍板的新增事项</b><span>不重复展示旧资讯；新证据进入资讯池后会自动出现在这里。</span></div>';
    $('#home-opportunities').innerHTML=data.top_opportunities.length?data.top_opportunities.map(row=>`<div class="radar-row"><div><h4>${esc(row.title)}</h4><p>${esc(row.regions.join(' / '))} · 下一步：${esc(row.validation_action)}</p></div><span class="mini-badge ${row.decision_status}">${esc(labels[row.decision_status])}</span><b class="radar-score">${row.total_score}</b></div>`).join(''):'<div class="empty">还没有游戏机会。</div>';
    $('#home-small-signals').innerHTML=smallSignals.length?smallSignals.slice(0,8).map(newsItem).join(''):'<div class="empty">暂时还没有标记为中小厂商机会的动态。</div>';
    $('#home-small-count').textContent=`${smallSignals.length} 条`;
    $('#home-game-signals').innerHTML=headSignals.length?headSignals.slice(0,5).map(newsItem).join(''):'<div class="empty">还没有头部市场风向资讯。</div>';
    $('#home-ai-signals').innerHTML=aiSignals.length?aiSignals.slice(0,6).map(newsItem).join(''):'<div class="empty">还没有AI趋势资讯。</div>';
    $('#home-ai-count').textContent=`${aiSignals.length} 条`;
    const risks=data.top_opportunities.flatMap(row=>[
      row.evidence_gaps?.[0]?{tone:'verify',label:'证据缺口',title:row.title,text:row.evidence_gaps[0]}:null,
      row.stop_loss_conditions?.[0]?{tone:'critical',label:'停止线',title:row.title,text:row.stop_loss_conditions[0]}:null,
    ]).filter(Boolean).slice(0,6);
    $('#home-risks').innerHTML=risks.length?risks.map(row=>`<div class="risk-row ${row.tone}"><span>${row.label}</span><div><b>${esc(row.title)}</b><p>${esc(row.text)}</p></div></div>`).join(''):'<div class="empty">当前没有风险条目。</div>';
    $('#home-coverage').innerHTML=[['A级/官方',official,allSignals.length,'critical'],['第三方估算',estimates,allSignals.length,'verify'],['游戏资讯',gameSignals.length,allSignals.length,'green'],['自动采集',data.automated_count,Math.max(1,allSignals.length),'trend']].map(([label,value,total,tone])=>coverageItem(label,value,total,tone)).join('');
    $('#home-sources').innerHTML=sourceRows(data.sources,5);
  }catch(error){toast(error.message)}
}

function smallStudioLens(row){
  const metric=String(row.metric_name||'');
  if(metric.startsWith('中小厂商/'))return metric.replace('中小厂商/','');
  const text=`${row.title||''} ${row.summary||''}`;
  if(/费率|分成|成本|降本/.test(text))return '平台降本';
  if(/留存|基准|小测|原型|试玩/.test(text))return '低成本验证';
  if(/自然量|商店|发现|Next Fest|愿望单/.test(text))return '自然增长';
  if(/东南亚|区域|本地化|发行/.test(text))return '区域发行';
  return '';
}
function isSmallStudioSignal(row){return Boolean(smallStudioLens(row))}

function attentionTone(row){
  if(row.evidence_type==='official'&&row.confidence_grade==='A')return 'critical';
  if(row.evidence_type==='third_party_estimate'||['C','D','E'].includes(row.confidence_grade))return 'verify';
  return 'trend';
}
function attentionRank(row){return {critical:0,verify:1,trend:2}[attentionTone(row)]??3}
function focusCard(row){
  const tone=attentionTone(row),label=tone==='critical'?'重点事实':tone==='verify'?'待验证估算':'趋势观察';
  const lens=smallStudioLens(row);
  return `<article class="focus-card ${tone} ${lens?'small-studio':''}"><div class="focus-top"><span>${lens?esc(lens):label}</span><time>${intelDate(row.observed_period)}</time></div><h4>${esc(row.title)}</h4><p>${esc(row.summary)}</p><footer>${esc(row.sector==='game'?'游戏市场':'AI趋势')} · ${esc(row.source_name)} · ${esc(row.confidence_grade)}级</footer></article>`;
}
function ceoDecisionCard(row){
  const meta=decisionMeta(row),tone=attentionTone(row),fact=decisionField(row.summary,'事实')||String(row.summary||'').split('行动建议')[0].trim();
  return `<article class="ceo-decision-card ${meta.level}"><div class="ceo-card-top"><span class="decision-type">${esc(meta.type)}</span><span class="deadline-badge">${esc(meta.urgency)}</span></div><h4>${esc(row.title)}</h4><p class="decision-fact">${esc(fact)}</p><div class="decision-lines"><div><span>业务影响</span><b>${esc(meta.impact)}</b></div><div><span>建议决策</span><b>${esc(meta.action)}</b></div></div><footer><span>负责人：${esc(meta.owner)}</span><span>${esc(row.source_name)} · ${esc(row.confidence_grade)}级</span>${row.source_url?`<a href="${esc(row.source_url)}" target="_blank" rel="noopener">原始来源</a>`:''}</footer></article>`;
}
function coverageItem(label,value,total,tone){
  const percent=Math.max(0,Math.min(100,Math.round(Number(value||0)/Math.max(1,Number(total||1))*100)));
  return `<div class="coverage-item ${tone}"><div><span>${label}</span><b>${value}</b></div><div class="coverage-track"><i style="width:${percent}%"></i></div><small>${percent}%</small></div>`;
}
function newsItem(row){
  const tone=attentionTone(row),label=tone==='critical'?'重点':tone==='verify'?'待验证':'趋势',lens=smallStudioLens(row);
  return `<article class="news-item ${tone} ${lens?'small-studio-news':''}"><div class="news-top"><h4><span class="news-priority ${lens?'actionable':tone}">${esc(lens||label)}</span>${esc(row.title)}</h4><time>${intelDate(row.observed_period)}</time></div><p>${esc(row.summary)}</p><div class="news-badges"><span class="mini-badge ${row.source_type}">${esc(intelLabels[row.source_type]||row.source_type)}</span><span class="mini-badge">${esc(intelLabels[row.evidence_type]||row.evidence_type)} · ${esc(row.confidence_grade)}级</span><span class="mini-badge">${esc(row.region)}</span>${row.source_url?`<a class="source-link" href="${esc(row.source_url)}" target="_blank" rel="noopener">查看来源</a>`:''}</div></article>`;
}

async function loadMarketNews(){
  try{
    const params=new URLSearchParams({sector:'game'}),q=$('#news-q')?.value||'',evidence=$('#news-evidence')?.value||'',sourceType=$('#news-source-type')?.value||'';
    if(q)params.set('q',q);if(evidence)params.set('evidence_type',evidence);if(sourceType)params.set('source_type',sourceType);
    let rows=await api('/api/signals?'+params.toString());
    const aiGame=await api('/api/signals?sector=ai_game'+(q?'&q='+encodeURIComponent(q):'')+(evidence?'&evidence_type='+encodeURIComponent(evidence):'')+(sourceType?'&source_type='+encodeURIComponent(sourceType):''));
    rows=[...rows,...aiGame].sort((a,b)=>String(b.collected_at).localeCompare(String(a.collected_at)));
    $('#signal-list').innerHTML=rows.length?rows.map(row=>`<article class="signal ${row.source_type==='manual_import'?'manual':row.source_type==='api_ingest'||row.source_type==='live_online'?'automated':''}"><div><h3>${esc(row.title)} ${row.is_demo?'<span class="tag demo">演示数据</span>':''}<span class="signal-source mini-badge ${row.source_type}">${esc(intelLabels[row.source_type]||row.source_type)}</span></h3><p class="signal-summary">${esc(row.summary)}</p><div class="signal-meta">${esc(row.region)} · ${esc(row.source_name)} · 观察日期 ${esc(row.observed_period)}${row.source_url?` · <a href="${esc(row.source_url)}" target="_blank" rel="noopener">查看来源</a>`:''}</div></div><span class="evidence">${esc(intelLabels[row.evidence_type]||row.evidence_type)} · ${esc(row.confidence_grade)}级</span></article>`).join(''):'<div class="empty">当前筛选下没有资讯。</div>';
  }catch(error){toast(error.message)}
}

async function prepareIntelligenceForm(){
  try{
    const rows=await api('/api/opportunities');
    const select=$('#intelligence-opportunity'),current=select.value;
    select.innerHTML='<option value="">暂不关联，先进入资讯池</option>'+rows.filter(row=>['game','ai_game'].includes(row.sector)&&!row.is_demo).map(row=>`<option value="${row.id}">${esc(row.title)}</option>`).join('');
    select.value=current;
    const date=$('#intelligence-form').elements.observed_at;if(!date.value)date.value=new Date().toISOString().slice(0,10);
  }catch(error){toast(error.message)}
}

async function submitIntelligence(event){
  event.preventDefault();const form=event.target,data=Object.fromEntries(new FormData(form));data.sector='game';data.source_type='manual_import';
  if(!data.opportunity_id)delete data.opportunity_id;
  try{
    const result=await api('/api/intelligence',{method:'POST',body:JSON.stringify(data)});
    $('#intelligence-save-state').textContent=`已保存：新增 ${result.inserted} 条，重复 ${result.duplicates} 条${result.linked?.length?'，并已关联机会':''}`;
    toast('资讯已保存并更新综合面板');form.reset();await prepareIntelligenceForm();await loadAll();
  }catch(error){$('#intelligence-save-state').textContent=error.message}
}

async function loadAutomationStatus(){
  try{
    const status=await api('/api/ingestion-status');
    $('#api-key-status').textContent=status.api_key_enabled?'API 密钥已启用':'本机角色模式';
    $('#api-key-status').className='status-pill '+(status.api_key_enabled?'ok':'');
    $('#automation-sources').innerHTML=sourceRows(status.sources,12);
    renderDeepSeekStatus(status.deepseek||{});
  }catch(error){toast(error.message)}
}

function renderDeepSeekStatus(status){
  const badge=$('#deepseek-status'),form=$('#deepseek-form');
  badge.textContent=status.configured?`已配置 · ${status.model}`:'未配置 API Key';
  badge.className='status-pill '+(status.configured?'ok':'warning');
  if(form){form.elements.base_url.value=status.base_url||'https://api.deepseek.com';form.elements.model.value=status.model||'deepseek-flash'}
  $('#deepseek-save-state').textContent=status.configured?`密钥来源：${status.key_source==='environment'?'服务器环境变量':'服务器安全配置文件'}。网页不会显示密钥。`:'请粘贴 DeepSeek 平台生成的 sk- 密钥并保存。';
}

async function saveDeepSeekConfig(event){
  event.preventDefault();const form=event.target,data=Object.fromEntries(new FormData(form));
  $('#deepseek-save-state').textContent='正在保存…';
  try{
    const status=await api('/api/deepseek/config',{method:'POST',body:JSON.stringify(data)});
    form.elements.api_key.value='';renderDeepSeekStatus(status);toast('DeepSeek 配置已保存');
  }catch(error){$('#deepseek-save-state').textContent=error.message}
}

async function testDeepSeek(){
  const button=$('#deepseek-test');button.disabled=true;button.textContent='连接中…';
  try{
    const result=await api('/api/deepseek/test',{method:'POST',body:'{}'});
    $('#deepseek-save-state').textContent=`连接成功：${result.model} · 本次 ${result.total_tokens||0} tokens`;
    $('#deepseek-status').textContent='连接正常';$('#deepseek-status').className='status-pill ok';toast('DeepSeek 连接正常');
  }catch(error){$('#deepseek-save-state').textContent=error.message;toast('DeepSeek 连接失败')}
  finally{button.disabled=false;button.textContent='测试连接'}
}

document.querySelectorAll('.nav').forEach(button=>button.onclick=()=>switchWorkspace(button.dataset.view));
document.querySelectorAll('[data-jump]').forEach(button=>button.onclick=()=>switchWorkspace(button.dataset.jump));
$('#news-search').onclick=loadMarketNews;
$('#search').onclick=loadGameRadarWorkspace;
$('#news-q').onkeydown=event=>{if(event.key==='Enter')loadMarketNews()};
$('#intelligence-form').onsubmit=submitIntelligence;
$('#deepseek-form').onsubmit=saveDeepSeekConfig;
$('#deepseek-test').onclick=testDeepSeek;
$('#copy-api-example').onclick=async()=>{await navigator.clipboard.writeText($('#api-example').textContent);toast('API 示例已复制')};
switchWorkspace('home');
