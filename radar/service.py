"""手游发行新业务机会与立项决策服务。"""

import csv
from datetime import datetime, timezone
from hashlib import sha256
from io import StringIO
import json
from .adapters import ADAPTERS
from .importer import parse_import
from .scoring import DIMENSIONS, asset_level, asset_pool, investment_level, normalized_scores

SECTORS={"ai","game","ai_game"}; STATUSES={"candidate","validating","watch","rejected"}
TYPES={"business","internal_tool","observation"}; STAGES={"lead","screen","evidence_7d","test_30d","scale_validation","approved","rejected"}
DECISIONS={"recommend_now","need_evidence","hold","reject"}
LIST_FIELDS=("market_evidence","competitors","risks","regions","genres","evidence_gaps","kpis","continue_thresholds","stop_loss_conditions")

class ValidationError(ValueError): pass

class OpportunityService:
    def __init__(self,repository): self.repo=repository
    def bootstrap(self,source_config=None):
        self.repo.initialize()
        for key,config in (source_config or {}).items():
            if key in ADAPTERS:self.repo.configure_source(key,config.get("config",{}),config.get("enabled",True))
        for key in ADAPTERS:
            source=self.repo.source(key)
            if source and source["enabled"]:self.collect(key)
        items=demo_opportunities()
        for item in items:
            existing=self.repo.find_seed(item["seed_key"],item["title"])
            if not existing:
                self.create_opportunity(item,"system-seed-v0.2")
            else:
                current=self.repo.get_opportunity(existing)
                if current["seed_key"]!=item["seed_key"] or current["opportunity_type"]!=item["opportunity_type"]:
                    self.update_opportunity(existing,item,"system-migrate-v0.2")
        legacy_id=self.repo.find_seed("legacy-ai-npc","AI NPC 垂直原型验证服务")
        if legacy_id:
            legacy=dict(next(item for item in items if item["seed_key"]=="observe-ai-npc"))
            legacy.update({"seed_key":"legacy-ai-npc","title":"AI NPC 垂直原型验证服务（历史演示记录）"})
            current=self.repo.get_opportunity(legacy_id)
            if current["seed_key"]!="legacy-ai-npc" or current["opportunity_type"]!="observation" or current["title"]!=legacy["title"]:
                self.update_opportunity(legacy_id,legacy,"system-migrate-v0.2")

    def collect(self,source_key=None):
        result={"inserted":0,"received":0,"sources":[]}
        for key in ([source_key] if source_key else list(ADAPTERS)):
            source=self.repo.source(key)
            if not source or not source["enabled"] or key not in ADAPTERS:raise ValidationError(f"数据源不可用：{key}")
            try:
                rows=[s.normalized() for s in ADAPTERS[key]().collect(json.loads(source["config_json"] or "{}"))]
                source_type="live_online" if json.loads(source["config_json"] or "{}").get("public_json_url") else "demo"
                for row in rows:
                    row.update({"source_type":source_type,"source_ref":row["source_url"] or key,"updated_at":row["collected_at"],"expires_at":"","freshness_status":"fresh" if source_type=="live_online" else "demo","is_estimate":int(row["evidence_type"]!="official")})
                inserted=self.repo.insert_signals(source["id"],rows)
            except Exception as exc:
                self.repo.mark_source_error(source["id"],exc)
                raise
            result["inserted"]+=inserted;result["received"]+=len(rows);result["sources"].append({"key":key,"received":len(rows),"inserted":inserted})
        return result

    def import_signals(self,payload,actor="admin"):
        try:
            rows,errors=parse_import(payload)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        if not rows:
            raise ValidationError("没有可导入的有效记录")
        source_name=str(payload.get("source_name","")).strip()
        source_ref=str(payload.get("source_ref","")).strip()
        category="ai" if payload.get("sector")=="ai" else "game"
        source_type=str(payload.get("source_type","manual_import")).strip()
        source_key=("api-" if source_type=="api_ingest" else "import-")+sha256(f"{source_name}|{source_ref}".encode("utf-8")).hexdigest()[:20]
        backup_path=self.repo.backup_before_import()
        source=self.repo.register_import_source(source_key,source_name,category,source_ref,source_type)
        inserted=self.repo.insert_signals(source["id"],rows)
        received=len(rows)+len(errors)
        self.repo.record_import(source["id"],actor,received,inserted,errors,backup_path)
        return {"source_key":source_key,"received":received,"valid":len(rows),"inserted":inserted,"duplicates":len(rows)-inserted,"errors":errors,"backup_path":backup_path}

    def submit_intelligence(self,payload,actor="analyst",force_source_type=None):
        raw_items=payload.get("items") if isinstance(payload.get("items"),list) else [payload]
        if not raw_items:raise ValidationError("至少提交一条资讯")
        source_name=str(payload.get("source_name") or raw_items[0].get("source_name") or "手动提交").strip()
        source_ref=str(payload.get("source_ref") or raw_items[0].get("source_url") or f"manual-{datetime.now(timezone.utc).date().isoformat()}").strip()
        items=[]
        for raw in raw_items:
            item=dict(raw)
            item.setdefault("sector",payload.get("sector","game"))
            item.setdefault("source_url",payload.get("source_url",""))
            item.setdefault("observed_at",payload.get("observed_at",""))
            item.setdefault("region",payload.get("region","未标注"))
            item.setdefault("evidence_type",payload.get("evidence_type","third_party_estimate"))
            item.setdefault("confidence_grade",payload.get("confidence_grade","C"))
            items.append(item)
        source_type=force_source_type or str(payload.get("source_type","manual_import"))
        import_payload={
            "format":"json","content":json.dumps({"items":items},ensure_ascii=False),
            "source_name":source_name,"source_ref":source_ref,"source_url":str(payload.get("source_url",items[0].get("source_url",""))),
            "sector":str(payload.get("sector",items[0].get("sector","game"))),"observed_at":str(payload.get("observed_at",items[0].get("observed_at",""))),
            "evidence_type":str(payload.get("evidence_type",items[0].get("evidence_type","third_party_estimate"))),
            "confidence_grade":str(payload.get("confidence_grade",items[0].get("confidence_grade","C"))),
            "region":str(payload.get("region",items[0].get("region","未标注"))),"source_type":source_type,
            "is_estimate":bool(payload.get("is_estimate",True)),
        }
        result=self.import_signals(import_payload,actor)
        rows,_=parse_import(import_payload)
        linked=[]
        for index,row in enumerate(rows):
            opportunity_id=items[index].get("opportunity_id") if index<len(items) else None
            if not opportunity_id:continue
            signal=self.repo.signal_by_dedupe(row["dedupe_key"])
            if signal:
                self.repo.link_signal(int(opportunity_id),signal["id"],"direct" if row["evidence_type"]=="official" else "estimate","资讯提交时自动关联",actor)
                linked.append({"signal_id":signal["id"],"opportunity_id":int(opportunity_id)})
        result.update({"linked":linked,"source_type":source_type})
        return result

    def intelligence_dashboard(self):
        signals=self.repo.list_signals(sector="game")+self.repo.list_signals(sector="ai_game")
        real=sorted((row for row in signals if not row["is_demo"]),key=lambda row:(row["collected_at"],row["id"]),reverse=True)
        opportunities=self.repo.list_opportunities(sector="game")+self.repo.list_opportunities(sector="ai_game")
        real_opportunities=[row for row in opportunities if not row["is_demo"]]
        return {
            "signals_total":len(real),"manual_count":sum(row["source_type"]=="manual_import" for row in real),
            "automated_count":sum(row["source_type"] in {"api_ingest","live_online"} for row in real),
            "official_count":sum(row["evidence_type"]=="official" for row in real),
            "fresh_count":sum(row["freshness_status"]=="fresh" for row in real),
            "opportunity_count":len(real_opportunities),"recommend_count":sum(row["decision_status"]=="recommend_now" for row in real_opportunities),
            "recent_signals":real[:8],"top_opportunities":real_opportunities[:5],
            "sources":self.repo.sources(),
        }

    def link_evidence(self,opportunity_id,payload,actor="analyst"):
        relation=str(payload.get("relation_type","direct")).strip()
        if relation not in {"direct","estimate","inference"}:raise ValidationError("关联类型必须是 direct、estimate 或 inference")
        try: signal_id=int(payload.get("signal_id"))
        except (TypeError,ValueError) as exc:raise ValidationError("signal_id 必须是整数") from exc
        return self.repo.link_signal(opportunity_id,signal_id,relation,str(payload.get("notes","")).strip(),actor)

    def normalize_profile(self,payload):
        def lines(key):
            value=payload.get(key,[])
            if isinstance(value,str):value=[x.strip() for x in value.splitlines() if x.strip()]
            if not isinstance(value,list):raise ValidationError(f"{key} 必须是列表")
            return json.dumps(value,ensure_ascii=False)
        item={"company_name":str(payload.get("company_name","")).strip()}
        if not item["company_name"]:raise ValidationError("公司名称不能为空")
        for key in ("target_regions","strong_genres","channels","inventory_products"):item[key+"_json"]=lines(key)
        try:
            item["monthly_test_budget"]=max(0,float(payload.get("monthly_test_budget",0)));item["acceptable_payback_months"]=max(1,int(payload.get("acceptable_payback_months",12)))
            for key in ("creative_capability","localization_capability","operations_capability","data_capability","ua_capability","channel_capability"):item[key]=min(5,max(1,int(payload.get(key,3))))
        except (TypeError,ValueError) as exc:raise ValidationError("画像数值格式错误") from exc
        return item
    def update_profile(self,payload,actor="admin"):return self.repo.update_company_profile(self.normalize_profile(payload),actor)

    def normalize_opportunity(self,payload):
        required=("title","pain","target_users","product_solution","pricing","acquisition","mvp","validation_action")
        missing=[k for k in required if not str(payload.get(k,"")).strip()]
        if missing:raise ValidationError("缺少必填字段："+", ".join(missing))
        sector=payload.get("sector","game"); typ=payload.get("opportunity_type","business"); stage=payload.get("validation_stage","lead"); decision=payload.get("decision_status","need_evidence")
        if sector not in SECTORS or typ not in TYPES or stage not in STAGES or decision not in DECISIONS:raise ValidationError("赛道、机会类型、阶段或决策状态无效")
        try:
            team=max(1,int(payload.get("team_size",1)));weeks=max(1,int(payload.get("cycle_weeks",4)));b7=max(0,float(payload.get("budget_7d",0)));b30=max(0,float(payload.get("budget_30d",payload.get("budget_cny",0))));bscale=max(0,float(payload.get("budget_scale",0)))
        except (TypeError,ValueError) as exc:raise ValidationError("团队、周期或预算格式错误") from exc
        row={k:str(payload.get(k,"")).strip() for k in required};row.update({"seed_key":payload.get("seed_key") or None,"sector":sector,"opportunity_type":typ,"owner":str(payload.get("owner","待分配")).strip() or "待分配","validation_stage":stage,"decision_status":decision,"product_source":str(payload.get("product_source","待核实")).strip(),"publisher_fit":str(payload.get("publisher_fit","待评估")).strip(),"publisher_misfit":str(payload.get("publisher_misfit","待评估")).strip(),"team_size":team,"cycle_weeks":weeks,"budget_7d":b7,"budget_30d":b30,"budget_scale":bscale,"is_demo":int(bool(payload.get("is_demo",False))),"score_rationale":str(payload.get("score_rationale","")).strip(),"payback_logic":str(payload.get("payback_logic","先用贡献现金覆盖验证与获客投入，再计算回本月。")).strip(),"next_action_due":str(payload.get("next_action_due","")).strip()})
        for field in LIST_FIELDS:
            value=payload.get(field,[])
            if isinstance(value,str):value=[x.strip() for x in value.splitlines() if x.strip()]
            if not isinstance(value,list):raise ValidationError(f"{field} 必须是列表")
            row[field+"_json"]=json.dumps(value,ensure_ascii=False)
        gates=payload.get("stage_gates") or default_gates(row["owner"],b7,b30,bscale,row["validation_action"])
        if not isinstance(gates,list):raise ValidationError("stage_gates 必须是列表")
        row["stage_gates_json"]=json.dumps(gates,ensure_ascii=False)
        current=next((g for g in gates if g.get("stage")==stage),{})
        row["stage_budget_limit"]=max(0,float(payload.get("stage_budget_limit",current.get("budget_limit",0))));row["stage_completion_condition"]=str(payload.get("stage_completion_condition",current.get("complete_when",""))).strip();row["stage_stop_condition"]=str(payload.get("stage_stop_condition",current.get("stop_when",""))).strip()
        level=asset_level(b30,bscale);row["asset_level"]=level;row["asset_pool"]=asset_pool(level);row["budget_cny"]=b7+b30+bscale;row["investment_level"]=investment_level(row["budget_cny"],weeks,team)
        row["status"]={"recommend_now":"validating","need_evidence":"candidate","hold":"watch","reject":"rejected"}[decision]
        scores,total=normalized_scores(payload.get("scores",{}),self.repo.get_company_profile())
        return row,scores,total
    def create_opportunity(self,payload,actor="analyst"):
        row,scores,total=self.normalize_opportunity(payload);oid=self.repo.create_opportunity(row,scores,total,actor);return self.repo.get_opportunity(oid)
    def update_opportunity(self,oid,payload,actor="analyst"):
        row,scores,total=self.normalize_opportunity(payload)
        if not self.repo.update_opportunity(oid,row,scores,total,actor):raise KeyError(oid)
        return self.repo.get_opportunity(oid)
    def export_csv(self,rows):
        out=StringIO(newline="");fields=["id","title","opportunity_type","regions","genres","validation_stage","decision_status","asset_level","total_score","owner","next_action_due","validation_action","product_source","publisher_fit","publisher_misfit","product_solution","pricing","team_size","budget_7d","budget_30d","budget_scale","market_evidence","kpis","continue_thresholds","stop_loss_conditions","payback_logic","evidence_gaps","is_demo",*DIMENSIONS];w=csv.DictWriter(out,fieldnames=fields);w.writeheader()
        for item in rows:
            row={k:item.get(k,"") for k in fields}
            for k in ("regions","genres","market_evidence","kpis","continue_thresholds","stop_loss_conditions","evidence_gaps"):row[k]=" | ".join(item[k])
            row.update(item["scores"]);w.writerow(row)
        return "\ufeff"+out.getvalue()
    def export_markdown(self,rows):
        lines=["# 手游发行新业务机会与立项决策导出","","> 所有演示 KPI 与预算仅为流程示例；正式阈值必须按国家、品类、平台和商业化模式配置。",""]
        for o in rows:
            lines += [f"## {o['title']}","",f"- 数据标记：{'演示数据' if o['is_demo'] else '非演示记录，仍需按证据等级复核'}",f"- 类型/决策：{o['opportunity_type']} · {o['decision_status']} · {o['validation_stage']} · {o['asset_level']} · 发行适配度 {o['total_score']}",f"- 地区/品类：{'、'.join(o['regions'])} / {'、'.join(o['genres'])}",f"- 做什么：{o['product_solution']}",f"- 产品/合作方来源：{o['product_source']}",f"- 为什么适合：{o['publisher_fit']}",f"- 为什么不适合：{o['publisher_misfit']}",f"- 商业模式：{o['pricing']}",f"- 团队与预算：{o['team_size']} 人；7天 ¥{o['budget_7d']:,.0f}；30天 ¥{o['budget_30d']:,.0f}；扩大 ¥{o['budget_scale']:,.0f}",f"- 市场证据：{'；'.join(o['market_evidence']) or '待补充'}",f"- KPI：{'；'.join(o['kpis'])}",f"- 继续门槛：{'；'.join(o['continue_thresholds'])}",f"- 止损：{'；'.join(o['stop_loss_conditions'])}",f"- 证据缺口：{'；'.join(o['evidence_gaps'])}",f"- 下一步：{o['owner']} 在 {o['next_action_due'] or '待排期'} 执行：{o['validation_action']}",f"- 回本逻辑：{o['payback_logic']}",""]
        return "\n".join(lines)

def default_gates(owner,b7,b30,bscale,action):
    return [
        {"stage":"lead","owner":owner,"budget_limit":0,"complete_when":"基本授权、产品和地区信息齐全","stop_when":"来源不明或明显不合规"},
        {"stage":"screen","owner":owner,"budget_limit":0,"complete_when":"画像匹配与证据缺口完成初筛","stop_when":"无渠道复用且回本假设不可描述"},
        {"stage":"evidence_7d","owner":owner,"budget_limit":b7,"complete_when":"7 天取证动作完成，关键证据可追溯","stop_when":"授权/数据真实性无法核验"},
        {"stage":"test_30d","owner":owner,"budget_limit":b30,"complete_when":action,"stop_when":"任一硬止损条件触发"},
        {"stage":"scale_validation","owner":owner,"budget_limit":bscale,"complete_when":"单位经济连续两个观察窗达标","stop_when":"贡献现金无法覆盖增量获客与运营"},
        {"stage":"approved","owner":"管理层","budget_limit":bscale,"complete_when":"立项书、预算与责任人批准","stop_when":"关键假设发生实质变化"},
        {"stage":"rejected","owner":owner,"budget_limit":0,"complete_when":"归档结论和证据","stop_when":"不再投入"},
    ]

def demo_opportunities():
    caveat="以下 KPI 为演示阈值，不是跨品类真理；正式值需按国家、品类、平台和商业化模式配置。"
    base={k:3 for k in DIMENSIONS}
    def item(key,title,solution,regions,genres,source,fit,misfit,model,team,b7,b30,bscale,stage,decision,owner,kpis,go,stop,risks,gaps,scores,typ="business",sector="game",weeks=8):
        return {"seed_key":key,"title":title,"opportunity_type":typ,"sector":sector,"regions":regions,"genres":genres,"pain":"发行资源存在闲置或新业务验证缺少可控投入与明确阶段门。","target_users":"目标地区玩家、产品方与公司发行团队","product_solution":solution,"product_source":source,"publisher_fit":fit,"publisher_misfit":misfit,"market_evidence":["演示数据：仅用于展示决策流程，不代表真实市场规模或产品表现"],"competitors":["当地发行商","产品方自发行","垂直服务商"],"pricing":model,"acquisition":"复用现有渠道、广告账户、素材与商务网络，先做小额可归因测试。","mvp":"7 天完成取证，30 天跑通单地区/单产品最小测试并形成贡献现金口径复盘。","team_size":team,"cycle_weeks":weeks,"budget_7d":b7,"budget_30d":b30,"budget_scale":bscale,"validation_stage":stage,"decision_status":decision,"owner":owner,"kpis":[caveat,*kpis],"continue_thresholds":go,"stop_loss_conditions":stop,"risks":risks,"evidence_gaps":gaps,"validation_action":f"7天：{source}并核验授权/数据；30天：{solution}，按示例 KPI 复盘。","next_action_due":"7天内","payback_logic":"按贡献现金计算：流水扣除平台/渠道分成、税费退款、增量买量和持续运营后，累计贡献现金覆盖7天、30天及扩大验证预算；演示回本期上限12个月。","score_rationale":"发行适配度由机会人工判断与公司画像能力各占一半；全部分值为演示，需用实际渠道、投放和产品数据校准。","scores":{**base,**scores},"is_demo":True}
    rows=[
      item("regional-agency","海外区域代理发行","取得单一国家/区域发行权，完成商店、本地化、买量、客服与活动运营。",["东南亚"],["RPG","SLG"],"从国内有数据但未出海的研发商、展会与既有商务库筛选授权产品", "可直接复用海外账户、投放、本地化和运营团队。","若无当地支付、客服或合规经验，履约成本会高于预期。","区域流水分成+最低保证金可选",4,20000,180000,800000,"evidence_7d","recommend_now","海外发行负责人",["示例：授权数据包完整率100%","示例：小测D1/付费率/ROAS达到该地区同品类内部基线"],["授权链完整且30天贡献毛利为正","买量样本达到预设统计量"],["授权不清立即停止","30天贡献现金为负且无可解释优化空间"],["版权地域冲突","买量成本波动","本地支付合规"],["真实留存/付费分地区数据","授权范围与期限","渠道结算口径"],{"channel_reuse":5,"ua_reuse":5,"localization_ops_reuse":5,"product_access":4,"strategic_synergy":5}),
      item("joint-publish","已验证中小游戏联合发行","联合产品方完成素材、投放、商店与运营，以小额预算验证放量。",["欧美","东南亚"],["休闲","混合休闲"],"从广告素材榜、开发者社群和现有BD管线寻找已有留存/变现数据的产品", "投放和素材团队可直接决定增量效果，现金验证快。","产品数据若不可审计，容易把自然量或一次性峰值误当可放大能力。","净流水分成或买量回收后分成",3,10000,100000,400000,"test_30d","recommend_now","买量负责人",["示例：CTR/CVR/CPI达到目标国家同品类内部基线","示例：D7 LTV覆盖可归因成本的趋势成立"],["至少两套素材与一个国家单位经济可复验"],["数据拒绝核验","连续两轮素材测试无改善且LTV/CPI倒挂"],["归因偏差","素材疲劳","产品更新能力不足"],["分国家留存与LTV","广告/IAP拆分","历史买量原始报表"],{"ua_reuse":5,"creative_reuse":5,"unit_economics_verifiability":5,"payback_speed":4,"strategic_synergy":5}),
      item("relaunch","老游戏区域再发行/重新包装","在合法授权与源码可维护前提下，替换商店包装、本地化和活动节奏后再发行。",["东南亚","拉美"],["RPG","模拟经营"],"从自有存量产品、明确权利链的研发商或版权方取得地区授权及合法源码", "存量运营和本地化经验可降低内容启动成本。","无完整源码、权利链或服务端能力时不可做。","区域授权分成+低额改造费",4,15000,120000,350000,"evidence_7d","need_evidence","产品运营负责人",["示例：商店页CVR相对旧版提升","示例：召回后D7与付费回收达到内部基线"],["源码可构建、授权可核验、核心漏斗有改善"],["任何权利瑕疵","源码不可维护","30天无核心指标改善"],["版权/源码合法性","技术债","老用户口碑"],["完整授权文件","源码构建证明","历史分地区数据"],{"localization_ops_reuse":5,"copyright_compliance":3,"product_access":4,"cash_exposure":4,"delivery_simplicity":3}),
      item("ai-creative","AI 广告素材批量生产与测试","围绕现有产品建立AI辅助脚本、分镜、变体和人工审校的素材测试流水线。",["全球"],["全品类"],"从公司当前投放产品和已授权素材资产中选取高消耗广告组", "素材和投放团队已有反馈闭环，可测量产能与获客增量。","没有稳定投放量或素材授权边界时，AI产能无法转化为收益。","内部降本+可选对外素材服务费",2,5000,50000,120000,"test_30d","recommend_now","素材负责人",["示例：合格素材周产能提升","示例：在同预算下胜出素材数增加且CPI不恶化"],["人工审校通过率和胜出素材数同时提升"],["侵权/平台违规","产量提升但胜出率持续下降"],["生成素材版权","品牌安全","同质化"],["当前素材成本基线","平台AI素材政策","人工审校标准"],{"creative_reuse":5,"ua_reuse":5,"cash_exposure":5,"payback_speed":5,"delivery_simplicity":4},sector="ai_game"),
      item("store-ab","App Store/Google Play 商店页本地化及 A/B 测试","为单一产品/国家重做图标、截图、视频、文案并运行商店实验。",["日韩","欧美","东南亚"],["全品类"],"从自有发行产品或取得商店素材授权的合作产品开始", "本地化、素材和数据团队可直接复用，周期短。","低自然量产品样本不足，无法在30天得到可靠结论。","内部增量收益或按国家/商店项目收费",2,3000,30000,80000,"evidence_7d","recommend_now","商店优化负责人",["示例：CVR提升需达到实验置信要求","示例：安装后D1不低于原版本"],["实验样本量达标且CVR显著改善"],["样本不足仍不得宣称胜出","CVR提升但后续质量显著恶化"],["实验样本偏差","素材审核","误导性表达"],["商店后台基线","国家/来源拆分","实验统计方案"],{"creative_reuse":5,"localization_ops_reuse":5,"cash_exposure":5,"delivery_simplicity":5,"payback_speed":5}),
      item("lqa","多语言本地化与 LQA","提供术语库、翻译、游戏内LQA、商店和客服语言包交付。",["日韩","东南亚","欧美"],["RPG","SLG","模拟经营"],"从现有合作研发商、待出海项目和区域代理项目获得合法版本与文本资产", "现有本地化/运营团队和游戏语境经验可形成复用资产。","没有稳定项目管线时容易变成人力外包，毛利和排期不稳定。","按字数/语言/版本收费+持续更新包",3,5000,60000,200000,"screen","need_evidence","本地化负责人",["示例：关键错误率、按时交付率、返工率按语言设定"],["两种语言交付质量和毛利达到内部项目线"],["版本访问不合规","返工导致贡献毛利为负"],["版本保密","翻译质量","高峰排期"],["真实项目管线","语言供应商成本","验收标准"],{"localization_ops_reuse":5,"product_access":4,"cash_exposure":4,"delivery_simplicity":4,"strategic_synergy":4}),
      item("reactivation","存量用户召回与交叉导流","对自有合法触达用户按地区和品类分群，以活动和新产品权益做召回/交叉导流。",["全球"],["存量产品相邻品类"],"仅使用公司拥有合法授权与同意范围内的存量产品和用户触达渠道", "已有用户、运营和数据能力可形成低现金成本验证。","用户同意范围、隐私政策或品类不匹配时不能实施。","降低获客成本并提升组合LTV",3,8000,80000,250000,"evidence_7d","need_evidence","用户运营负责人",["示例：送达率、召回率、D7、增量LTV按渠道/地区分层"],["增量贡献现金覆盖触达和活动成本"],["同意范围不支持立即停止","投诉/退订异常上升"],["隐私合规","打扰用户","归因污染"],["用户同意记录","可触达规模","对照组设计"],{"channel_reuse":5,"localization_ops_reuse":5,"cash_exposure":5,"copyright_compliance":3,"strategic_synergy":5}),
      item("screening-service","发行产品筛选与小额测试服务","替产品方完成数据室检查、素材探针和单市场小额测试，输出是否联合发行的决策包。",["全球"],["休闲","RPG","SLG"],"从开发者投递、展会、孵化器和合作伙伴推荐获得候选产品与测试授权", "发行团队的投放、产品和数据能力可直接商品化并为自营管线供给。","若收费与后续联合发行利益冲突，需明确独立口径。","固定评估费+后续联合发行优先权",3,5000,50000,150000,"screen","recommend_now","商务负责人",["示例：每月合格候选数、测试周期、付费转化率","示例：建议与后续真实表现的一致性"],["首批3个付费项目且交付毛利为正"],["客户不提供可核验数据","评估交付长期依赖高层个人"],["数据保密","结论责任边界","样本选择偏差"],["付费意愿访谈","交付模板","责任免责声明"],{"product_access":5,"ua_reuse":5,"data_capability":4,"cash_exposure":5,"strategic_synergy":5}),
      item("h5-cps","小游戏/H5 渠道联运或 CPS 聚合","接入已验证小游戏，向合法渠道分发并按有效新增或流水结算。",["中国大陆","东南亚"],["小游戏","H5"],"从有版号/备案及可核验数据的产品方和正规渠道商务获取联运授权", "渠道商务、运营和结算能力可复用，单项目技术投入较低。","缺乏渠道量级或结算风控时，规模与坏账风险不可控。","CPS/CPA或联运流水分成",3,10000,90000,300000,"evidence_7d","need_evidence","渠道负责人",["示例：有效新增、次留、付费率、回款周期按渠道定义"],["首个渠道回款可核验且贡献毛利为正"],["资质不全","渠道数据不可审计","回款超约定期限"],["渠道作弊","结算账期","资质合规"],["渠道真实量级","反作弊规则","回款历史"],{"channel_reuse":5,"product_access":4,"unit_economics_verifiability":4,"cash_exposure":4,"copyright_compliance":3}),
      item("playable-ads","可玩广告生产","为已有玩法和素材授权的手游制作轻量可玩广告并联动投放测试。",["欧美","东南亚"],["休闲","SLG","RPG"],"从自有投放产品和合作发行项目获得玩法、素材与广告投放授权", "素材、投放和轻量前端能力能快速形成测量闭环。","没有制作能力或投放规模时容易成为低毛利外包。","按条制作费+测试优化包",3,5000,70000,180000,"test_30d","recommend_now","创意技术负责人",["示例：互动率、落地CVR、CPI相对视频基线改善"],["至少一个国家/品类出现可重复胜出版本"],["平台拒审","互动高但安装后留存显著下降"],["玩法夸大","兼容性","制作排期"],["历史素材基线","平台规范","复用组件覆盖率"],{"creative_reuse":5,"ua_reuse":5,"delivery_simplicity":4,"payback_speed":4,"strategic_synergy":4}),
      item("co-development","有数据原型的联合开发","只对已有可玩原型和初步留存/转化数据的团队投入发行、制作与里程碑资金。",["全球"],["休闲","RPG","模拟经营"],"从孵化器、开发者社群和现有BD管线筛选可运行构建及原始测试数据", "发行可补足产品定位、素材、投放和商业化验证。","研发范围、里程碑和知识产权不清会把发行公司拖入重研发。","里程碑投资+发行分成/优先权",5,30000,300000,900000,"evidence_7d","need_evidence","产品投资负责人",["示例：D1/D7、会话、商业化事件按具体品类设门槛","示例：每里程碑燃尽与可玩内容完成度"],["原始数据可复验且30天版本验证核心假设"],["无可运行构建","IP归属不清","连续里程碑延期"],["研发延期","IP归属","预算追加"],["原始测试数据","代码/IP权属","团队履历与现金流"],{"product_access":4,"strategic_synergy":5,"cash_exposure":2,"payback_speed":2,"delivery_simplicity":2}),
      item("asset-acquisition","存量产品/IP/源码合规收购","收购权利链清晰、可构建且有历史数据的产品/IP/源码，先做技术与商业尽调。",["全球"],["RPG","SLG","模拟经营"],"从正规资产交易、版权方或退出团队取得完整权利包、源码、服务端与历史后台数据", "发行可通过再包装、区域运营和交叉导流释放存量价值。","现金占用高，任何授权、源码、数据真实性瑕疵都可能使资产归零。","买断或保底+收入分成",5,50000,350000,1500000,"evidence_7d","hold","法务与投资负责人",["示例：可构建率、权利文件完整率、历史净收入可审计性"],["技术/法务/财务三项尽调全部通过"],["权利链不完整","源码不可构建","卖方数据无法核验"],["版权诉讼","隐藏技术债","历史收入衰减"],["审计级历史流水","全链路授权","服务端与构建环境"],{"product_access":3,"copyright_compliance":2,"cash_exposure":1,"payback_speed":2,"strategic_synergy":4},weeks=20),
    ]
    rows += [
      item("internal-radar","AI 游戏商机证据工作台","维护公开证据、机会卡与阶段门，服务内部立项，不对外作为业务机会。",["内部"],["全品类"],"内部需求与公开合规数据源","提升决策留痕和复盘效率。","没有真实数据与使用责任人时只会成为空看板。","内部提效，不计算对外收入",2,0,30000,80000,"approved","need_evidence","战略分析负责人",["示例：每周有效机会更新数、证据补全率、决策周期"],["至少3个真实立项使用并形成复盘"],["连续4周无人维护或无决策引用"],["数据质量","维护责任"],["真实使用基线"],{"data_capability":5,"strategic_synergy":5,"cash_exposure":5},typ="internal_tool",sector="ai_game"),
      item("internal-ai-cost","AI 成本与质量回归看板","监控公司内部AI素材/翻译工作流的成本、质量和延迟。",["内部"],["全品类"],"内部AI调用日志与人工质检样本","可支撑AI素材和本地化降本。","不直接形成发行项目收入。","内部提效",2,0,20000,50000,"screen","need_evidence","技术负责人",["示例：单位合格输出成本、质检通过率、延迟"],["发现并阻止一次真实成本或质量回归"],["无法获得合规日志或人工基线"],["日志隐私","评测漂移"],["现有成本基线"],{"creative_reuse":4,"delivery_simplicity":4,"strategic_synergy":4},typ="internal_tool",sector="ai"),
      item("observe-ai-npc","AI NPC 引擎/原型服务","仅观察或与具备研发能力的伙伴共研，不作为发行主业优先项。",["全球"],["叙事","模拟经营"],"有成熟引擎原型、内容安全方案和B端客户线索的技术团队","仅当公司具备研发管理和B端获客能力时可能适合。","当前发行画像的渠道/投放优势难复用，技术交付重、回本慢。","B端项目费或SDK用量费",6,20000,200000,1000000,"lead","hold","技术观察负责人",["示例：会话成本、内容安全通过率、B端付费意向"],["外部伙伴承担核心研发且出现付费POC"],["需自建核心引擎或无B端客户来源"],["技术复杂度","内容安全","B端销售"],["付费客户证据","真实留存提升","推理成本"],{"channel_reuse":1,"ua_reuse":1,"delivery_simplicity":1,"payback_speed":1,"strategic_synergy":2},typ="observation",sector="ai_game",weeks=24),
      item("observe-heavy-selfdev","重资产自研新手游","观察，不在缺少已验证原型和核心制作团队时投入完整自研。",["全球"],["中重度"],"仅来自自有成熟制作团队或已有数据原型","发行能力可在后期放大产品。","核心制作、内容产能与长周期现金风险超出发行优势。","自营流水",20,50000,500000,5000000,"lead","reject","管理层",["示例：原型留存、内容产能、资金里程碑"],["核心团队和数据原型均已存在"],["从概念直接进入完整制作","资金安全垫不足"],["研发延期","现金风险","内容产能"],["原型数据","核心团队","完整预算"],{"channel_reuse":3,"cash_exposure":1,"payback_speed":1,"delivery_simplicity":1,"product_access":1},typ="observation",weeks=52),
      item("observe-industry-llm","游戏行业大模型","观察，不建议发行公司自训基础模型；优先采购API或与模型方合作。",["全球"],["全品类"],"模型厂商、云服务商或已有基础模型团队","可作为内部工具底座。","训练成本、人才和商业化路径与手游发行能力错位。","内部能力采购或合作分成",8,10000,100000,2000000,"lead","reject","技术观察负责人",["示例：采购与自训TCO、任务质量、合规"],["外部方案在成本和质量上可用"],["需要自建基础训练集群或无明确任务"],["算力成本","数据版权","模型迭代"],["真实任务基准","供应商报价","数据合规"],{"channel_reuse":1,"ua_reuse":1,"cash_exposure":1,"payback_speed":1,"delivery_simplicity":1,"strategic_synergy":2},typ="observation",sector="ai",weeks=32),
    ]
    return rows
