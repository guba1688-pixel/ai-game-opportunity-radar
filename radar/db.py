"""SQLite v3 兼容迁移、持久化、来源健康与审计仓储。"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS sources (id INTEGER PRIMARY KEY,source_key TEXT UNIQUE NOT NULL,name TEXT NOT NULL,category TEXT NOT NULL CHECK(category IN ('ai','game')),adapter TEXT NOT NULL,config_json TEXT NOT NULL DEFAULT '{}',enabled INTEGER NOT NULL DEFAULT 1,last_run_at TEXT,source_type TEXT NOT NULL DEFAULT 'demo',source_ref TEXT NOT NULL DEFAULT '',health_status TEXT NOT NULL DEFAULT 'never_run',last_success_at TEXT,last_error TEXT NOT NULL DEFAULT '',updated_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY,source_id INTEGER NOT NULL REFERENCES sources(id),title TEXT NOT NULL,summary TEXT NOT NULL,sector TEXT NOT NULL CHECK(sector IN ('ai','game','ai_game')),source_name TEXT NOT NULL,source_url TEXT NOT NULL,collected_at TEXT NOT NULL,observed_period TEXT NOT NULL,region TEXT NOT NULL,metric_name TEXT NOT NULL,metric_value TEXT NOT NULL,metric_unit TEXT NOT NULL,evidence_type TEXT NOT NULL CHECK(evidence_type IN ('official','third_party_estimate','model_inference','demo')),confidence_grade TEXT NOT NULL CHECK(confidence_grade IN ('A','B','C','D','E')),is_demo INTEGER NOT NULL CHECK(is_demo IN (0,1)),dedupe_key TEXT UNIQUE NOT NULL,raw_json TEXT NOT NULL,source_type TEXT NOT NULL DEFAULT 'demo',source_ref TEXT NOT NULL DEFAULT '',updated_at TEXT NOT NULL DEFAULT '',expires_at TEXT NOT NULL DEFAULT '',freshness_status TEXT NOT NULL DEFAULT 'unknown',is_estimate INTEGER NOT NULL DEFAULT 0 CHECK(is_estimate IN (0,1)));
CREATE TABLE IF NOT EXISTS opportunities (id INTEGER PRIMARY KEY,title TEXT NOT NULL,sector TEXT NOT NULL CHECK(sector IN ('ai','game','ai_game')),status TEXT NOT NULL DEFAULT 'candidate' CHECK(status IN ('candidate','validating','watch','rejected')),pain TEXT NOT NULL,target_users TEXT NOT NULL,product_solution TEXT NOT NULL,market_evidence_json TEXT NOT NULL,competitors_json TEXT NOT NULL,pricing TEXT NOT NULL,acquisition TEXT NOT NULL,mvp TEXT NOT NULL,team_size INTEGER NOT NULL,budget_cny REAL NOT NULL,cycle_weeks INTEGER NOT NULL,investment_level TEXT NOT NULL CHECK(investment_level IN ('L1','L2','L3','L4')),asset_pool TEXT NOT NULL CHECK(asset_pool IN ('light','heavy')),risks_json TEXT NOT NULL,validation_action TEXT NOT NULL,is_demo INTEGER NOT NULL CHECK(is_demo IN (0,1)),created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS opportunity_scores (opportunity_id INTEGER PRIMARY KEY REFERENCES opportunities(id) ON DELETE CASCADE,scores_json TEXT NOT NULL,total_score REAL NOT NULL,rationale TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS opportunity_signal_links (opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,signal_id INTEGER NOT NULL REFERENCES signals(id) ON DELETE CASCADE,relation_type TEXT NOT NULL,notes TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,PRIMARY KEY(opportunity_id,signal_id));
CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY,actor TEXT NOT NULL,module TEXT NOT NULL,action TEXT NOT NULL,object_type TEXT NOT NULL,object_id TEXT NOT NULL,before_json TEXT,after_json TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS company_profiles (id INTEGER PRIMARY KEY CHECK(id=1),company_name TEXT NOT NULL,target_regions_json TEXT NOT NULL,strong_genres_json TEXT NOT NULL,channels_json TEXT NOT NULL,monthly_test_budget REAL NOT NULL,creative_capability INTEGER NOT NULL,localization_capability INTEGER NOT NULL,operations_capability INTEGER NOT NULL,data_capability INTEGER NOT NULL,ua_capability INTEGER NOT NULL,channel_capability INTEGER NOT NULL,inventory_products_json TEXT NOT NULL,acceptable_payback_months INTEGER NOT NULL,updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_signals_sector ON signals(sector);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at DESC);
"""

V2_COLUMNS = {
    "seed_key":"TEXT", "opportunity_type":"TEXT NOT NULL DEFAULT 'business'", "regions_json":"TEXT NOT NULL DEFAULT '[]'", "genres_json":"TEXT NOT NULL DEFAULT '[]'",
    "product_source":"TEXT NOT NULL DEFAULT ''", "publisher_fit":"TEXT NOT NULL DEFAULT ''", "publisher_misfit":"TEXT NOT NULL DEFAULT ''", "owner":"TEXT NOT NULL DEFAULT '待分配'",
    "validation_stage":"TEXT NOT NULL DEFAULT 'lead'", "decision_status":"TEXT NOT NULL DEFAULT 'need_evidence'", "asset_level":"TEXT NOT NULL DEFAULT 'light'",
    "budget_7d":"REAL NOT NULL DEFAULT 0", "budget_30d":"REAL NOT NULL DEFAULT 0", "budget_scale":"REAL NOT NULL DEFAULT 0", "stage_budget_limit":"REAL NOT NULL DEFAULT 0",
    "stage_completion_condition":"TEXT NOT NULL DEFAULT ''", "stage_stop_condition":"TEXT NOT NULL DEFAULT ''", "evidence_gaps_json":"TEXT NOT NULL DEFAULT '[]'",
    "kpis_json":"TEXT NOT NULL DEFAULT '[]'", "continue_thresholds_json":"TEXT NOT NULL DEFAULT '[]'", "stop_loss_conditions_json":"TEXT NOT NULL DEFAULT '[]'",
    "payback_logic":"TEXT NOT NULL DEFAULT ''", "next_action_due":"TEXT NOT NULL DEFAULT ''", "stage_gates_json":"TEXT NOT NULL DEFAULT '[]'"
}

SOURCE_V3_COLUMNS = {
    "source_type":"TEXT NOT NULL DEFAULT 'demo'", "source_ref":"TEXT NOT NULL DEFAULT ''",
    "health_status":"TEXT NOT NULL DEFAULT 'never_run'", "last_success_at":"TEXT",
    "last_error":"TEXT NOT NULL DEFAULT ''", "updated_at":"TEXT NOT NULL DEFAULT ''"
}
SIGNAL_V3_COLUMNS = {
    "source_type":"TEXT NOT NULL DEFAULT 'demo'", "source_ref":"TEXT NOT NULL DEFAULT ''",
    "updated_at":"TEXT NOT NULL DEFAULT ''", "expires_at":"TEXT NOT NULL DEFAULT ''",
    "freshness_status":"TEXT NOT NULL DEFAULT 'unknown'",
    "is_estimate":"INTEGER NOT NULL DEFAULT 0"
}

JSON_FIELDS = ("market_evidence","competitors","risks","regions","genres","evidence_gaps","kpis","continue_thresholds","stop_loss_conditions","stage_gates")
BASE_COLUMNS = ["title","sector","status","pain","target_users","product_solution","market_evidence_json","competitors_json","pricing","acquisition","mvp","team_size","budget_cny","cycle_weeks","investment_level","asset_pool","risks_json","validation_action","is_demo"]
V2_WRITE_COLUMNS = ["seed_key","opportunity_type","regions_json","genres_json","product_source","publisher_fit","publisher_misfit","owner","validation_stage","decision_status","asset_level","budget_7d","budget_30d","budget_scale","stage_budget_limit","stage_completion_condition","stage_stop_condition","evidence_gaps_json","kpis_json","continue_thresholds_json","stop_loss_conditions_json","payback_logic","next_action_due","stage_gates_json"]


def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Repository:
    def __init__(self, db_path): self.path=Path(db_path); self.path.parent.mkdir(parents=True,exist_ok=True)

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10); db.row_factory=sqlite3.Row; db.execute("PRAGMA foreign_keys=ON")
        try: yield db; db.commit()
        except Exception: db.rollback(); raise
        finally: db.close()

    def initialize(self):
        with self.connect() as db:
            db.executescript(SCHEMA)
            columns={r[1] for r in db.execute("PRAGMA table_info(opportunities)")}
            migrated=False
            for name,declaration in V2_COLUMNS.items():
                if name not in columns: db.execute(f"ALTER TABLE opportunities ADD COLUMN {name} {declaration}"); migrated=True
            migrated_v3=False
            for table,declarations in (("sources",SOURCE_V3_COLUMNS),("signals",SIGNAL_V3_COLUMNS)):
                current={r[1] for r in db.execute(f"PRAGMA table_info({table})")}
                for name,declaration in declarations.items():
                    if name not in current:
                        db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")
                        migrated_v3=True
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_opps_seed_key ON opportunities(seed_key) WHERE seed_key IS NOT NULL")
            db.execute("CREATE INDEX IF NOT EXISTS idx_opps_decision_stage ON opportunities(decision_status,validation_stage)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_signals_source_freshness ON signals(source_type,freshness_status)")
            db.execute("INSERT OR IGNORE INTO company_profiles VALUES(1,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("示例手游发行公司",json.dumps(["东南亚","日韩","欧美"],ensure_ascii=False),json.dumps(["休闲","SLG","RPG","小游戏"],ensure_ascii=False),json.dumps(["App Store","Google Play","Meta Ads","TikTok Ads"],ensure_ascii=False),600000,4,4,4,4,4,4,json.dumps(["存量手游A（演示）","存量用户池（演示）"],ensure_ascii=False),12,now()))
            for key,name,category in (("ai_market","AI 市场公开信号示例","ai"),("game_market","游戏市场公开信号示例","game")):
                db.execute("INSERT OR IGNORE INTO sources(source_key,name,category,adapter,config_json) VALUES(?,?,?,?,?)",(key,name,category,key,"{}"))
            if migrated:
                self._audit(db,"system","schema","migrate_v2","database","2",None,{"version":"2","strategy":"additive"})
            if migrated_v3:
                self._audit(db,"system","schema","migrate_v3","database","3",None,{"version":"3","strategy":"additive"})
            db.execute("UPDATE sources SET source_type='demo',source_ref=source_key,health_status=CASE WHEN last_run_at IS NULL THEN 'never_run' ELSE 'healthy' END,last_success_at=last_run_at,updated_at=COALESCE(last_run_at,'') WHERE adapter IN ('ai_market','game_market')")
            db.execute("UPDATE signals SET source_type='demo',source_ref=source_name,updated_at=collected_at,freshness_status='demo',is_estimate=1 WHERE is_demo=1")
            db.execute("INSERT INTO schema_meta(key,value) VALUES('schema_version','3') ON CONFLICT(key) DO UPDATE SET value='3'")

    def source(self,key):
        with self.connect() as db:
            row=db.execute("SELECT * FROM sources WHERE source_key=?",(key,)).fetchone(); return dict(row) if row else None
    def sources(self):
        with self.connect() as db: return [dict(r) for r in db.execute("SELECT s.*,COUNT(g.id) signal_count FROM sources s LEFT JOIN signals g ON g.source_id=s.id GROUP BY s.id ORDER BY s.id")]
    def configure_source(self,key,config,enabled=True):
        with self.connect() as db: db.execute("UPDATE sources SET config_json=?,enabled=? WHERE source_key=?",(json.dumps(config or {},ensure_ascii=False),int(bool(enabled)),key))
    def insert_signals(self,source_id,rows):
        inserted=0; columns=["title","summary","sector","source_name","source_url","collected_at","observed_period","region","metric_name","metric_value","metric_unit","evidence_type","confidence_grade","is_demo","dedupe_key","raw_json","source_type","source_ref","updated_at","expires_at","freshness_status","is_estimate"]
        with self.connect() as db:
            for row in rows:
                values=[row.get(c, {"source_type":"demo","source_ref":"","updated_at":row.get("collected_at",""),"expires_at":"","freshness_status":"demo" if row.get("is_demo") else "unknown","is_estimate":int(row.get("evidence_type") in {"third_party_estimate","model_inference","demo"})}.get(c)) for c in columns]
                cursor=db.execute(f"INSERT OR IGNORE INTO signals(source_id,{','.join(columns)}) VALUES({','.join(['?']*(len(columns)+1))})",[source_id,*values]); inserted+=cursor.rowcount
            stamp=now()
            db.execute("UPDATE sources SET last_run_at=?,last_success_at=?,health_status='healthy',last_error='',updated_at=? WHERE id=?",(stamp,stamp,stamp,source_id))
        return inserted
    def list_signals(self,sector="",evidence_type="",query="",source_type="",freshness=""):
        clauses=[];args=[]
        if sector: clauses.append("sector=?");args.append(sector)
        if evidence_type: clauses.append("evidence_type=?");args.append(evidence_type)
        if source_type: clauses.append("source_type=?");args.append(source_type)
        if freshness: clauses.append("freshness_status=?");args.append(freshness)
        if query: clauses.append("(title LIKE ? OR summary LIKE ?)");args.extend([f"%{query}%"]*2)
        with self.connect() as db: return [dict(r) for r in db.execute("SELECT * FROM signals"+(" WHERE "+" AND ".join(clauses) if clauses else "")+" ORDER BY collected_at DESC,id DESC",args)]

    def signal_by_dedupe(self,dedupe_key):
        with self.connect() as db:
            row=db.execute("SELECT * FROM signals WHERE dedupe_key=?",(dedupe_key,)).fetchone()
            return dict(row) if row else None

    def register_import_source(self,source_key,name,category,source_ref,source_type="manual_import"):
        stamp=now()
        with self.connect() as db:
            db.execute("INSERT INTO sources(source_key,name,category,adapter,config_json,enabled,source_type,source_ref,health_status,updated_at) VALUES(?,?,?,?,?,0,?,?,'never_run',?) ON CONFLICT(source_key) DO UPDATE SET name=excluded.name,category=excluded.category,source_type=excluded.source_type,source_ref=excluded.source_ref,updated_at=excluded.updated_at",(source_key,name,category,source_type,"{}",source_type,source_ref,stamp))
            return dict(db.execute("SELECT * FROM sources WHERE source_key=?",(source_key,)).fetchone())

    def record_import(self,source_id,actor,received,inserted,errors,backup_path):
        with self.connect() as db:
            after={"received":received,"inserted":inserted,"skipped":received-inserted,"errors":errors,"backup_path":backup_path}
            status="degraded" if errors else ("healthy" if inserted else "no_change")
            db.execute("UPDATE sources SET health_status=?,last_error=?,updated_at=? WHERE id=?",(status,"；".join(str(e.get("message","")) for e in errors[:3]),now(),source_id))
            self._audit(db,actor,"sources","import","source",source_id,None,after)

    def mark_source_error(self,source_id,message):
        with self.connect() as db:
            db.execute("UPDATE sources SET health_status='error',last_error=?,last_run_at=?,updated_at=? WHERE id=?",(str(message)[:500],now(),now(),source_id))

    def backup_before_import(self):
        target_dir=self.path.parent/"import_backups"
        target_dir.mkdir(parents=True,exist_ok=True)
        target=target_dir/f"before-import-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')}.db"
        source=sqlite3.connect(self.path)
        backup=sqlite3.connect(target)
        try: source.backup(backup)
        finally: backup.close();source.close()
        return str(target)

    def get_company_profile(self):
        with self.connect() as db:
            row=db.execute("SELECT * FROM company_profiles WHERE id=1").fetchone(); item=dict(row)
        for key in ("target_regions","strong_genres","channels","inventory_products"): item[key]=json.loads(item.pop(key+"_json"))
        item["localization_ops_capability"]=round((item["localization_capability"]+item["operations_capability"])/2)
        return item
    def update_company_profile(self,item,actor):
        before=self.get_company_profile(); columns=["company_name","target_regions_json","strong_genres_json","channels_json","monthly_test_budget","creative_capability","localization_capability","operations_capability","data_capability","ua_capability","channel_capability","inventory_products_json","acceptable_payback_months"]
        with self.connect() as db:
            db.execute("UPDATE company_profiles SET "+",".join(f"{c}=?" for c in columns)+",updated_at=? WHERE id=1",[*[item[c] for c in columns],now()]); self._audit(db,actor,"company_profile","update","company_profile",1,before,item)
        return self.get_company_profile()

    def find_seed(self,seed_key,title):
        with self.connect() as db:
            row=db.execute("SELECT id FROM opportunities WHERE seed_key=? OR (seed_key IS NULL AND title=? AND is_demo=1) ORDER BY id LIMIT 1",(seed_key,title)).fetchone(); return row[0] if row else None
    def create_opportunity(self,row,scores,total,actor):
        stamp=now(); columns=BASE_COLUMNS+V2_WRITE_COLUMNS
        with self.connect() as db:
            cur=db.execute(f"INSERT INTO opportunities({','.join(columns)},created_at,updated_at) VALUES({','.join(['?']*(len(columns)+2))})",[*[row[c] for c in columns],stamp,stamp]); oid=cur.lastrowid
            db.execute("INSERT INTO opportunity_scores VALUES(?,?,?,?)",(oid,json.dumps(scores,ensure_ascii=False),total,row.get("score_rationale",""))); self._audit(db,actor,"opportunities","create","opportunity",oid,None,{**row,"scores":scores,"total_score":total})
        return oid
    def update_opportunity(self,oid,row,scores,total,actor):
        before=self.get_opportunity(oid)
        if not before:return False
        columns=BASE_COLUMNS+V2_WRITE_COLUMNS
        with self.connect() as db:
            db.execute("UPDATE opportunities SET "+",".join(f"{c}=?" for c in columns)+",updated_at=? WHERE id=?",[*[row[c] for c in columns],now(),oid]); db.execute("UPDATE opportunity_scores SET scores_json=?,total_score=?,rationale=? WHERE opportunity_id=?",(json.dumps(scores,ensure_ascii=False),total,row.get("score_rationale",""),oid)); self._audit(db,actor,"opportunities","update","opportunity",oid,before,{**row,"scores":scores,"total_score":total})
        return True
    def delete_opportunity(self,oid,actor):
        before=self.get_opportunity(oid)
        if not before:return False
        with self.connect() as db: db.execute("DELETE FROM opportunities WHERE id=?",(oid,));self._audit(db,actor,"opportunities","delete","opportunity",oid,before,None)
        return True
    def get_opportunity(self,oid):
        with self.connect() as db: row=db.execute("SELECT o.*,s.scores_json,s.total_score,s.rationale score_rationale FROM opportunities o JOIN opportunity_scores s ON s.opportunity_id=o.id WHERE o.id=?",(oid,)).fetchone()
        if not row:return None
        item=self._decode_opportunity(row);item["evidence_links"]=self.evidence_links(oid);item["evidence_trace_status"]="linked" if item["evidence_links"] else "missing";return item
    def list_opportunities(self,sector="",pool="",status="",query="",region="",genre="",asset="",stage="",decision="",min_fit=""):
        clauses=[];args=[]
        filters=(("o.sector",sector),("o.asset_pool",pool),("o.status",status),("o.asset_level",asset),("o.validation_stage",stage),("o.decision_status",decision))
        for col,val in filters:
            if val:clauses.append(f"{col}=?");args.append(val)
        if region:clauses.append("o.regions_json LIKE ?");args.append(f"%{region}%")
        if genre:clauses.append("o.genres_json LIKE ?");args.append(f"%{genre}%")
        if min_fit:clauses.append("s.total_score>=?");args.append(float(min_fit))
        if query:clauses.append("(o.title LIKE ? OR o.pain LIKE ? OR o.product_solution LIKE ? OR o.product_source LIKE ?)");args.extend([f"%{query}%"]*4)
        sql="SELECT o.*,s.scores_json,s.total_score,s.rationale score_rationale FROM opportunities o JOIN opportunity_scores s ON s.opportunity_id=o.id"+(" WHERE "+" AND ".join(clauses) if clauses else "")+" ORDER BY CASE o.decision_status WHEN 'recommend_now' THEN 1 WHEN 'need_evidence' THEN 2 WHEN 'hold' THEN 3 ELSE 4 END,s.total_score DESC,o.updated_at DESC"
        with self.connect() as db:items=[self._decode_opportunity(r) for r in db.execute(sql,args)]
        for item in items:item["evidence_links"]=self.evidence_links(item["id"]);item["evidence_trace_status"]="linked" if item["evidence_links"] else "missing"
        return items
    def evidence_links(self,opportunity_id):
        sql="SELECT l.relation_type,l.notes,l.created_at,s.id signal_id,s.title,s.source_name,s.source_type,s.source_ref,s.source_url,s.collected_at,s.updated_at,s.observed_period,s.evidence_type,s.confidence_grade,s.freshness_status,s.is_estimate FROM opportunity_signal_links l JOIN signals s ON s.id=l.signal_id WHERE l.opportunity_id=? ORDER BY l.created_at DESC"
        with self.connect() as db:return [dict(r) for r in db.execute(sql,(opportunity_id,))]
    def link_signal(self,opportunity_id,signal_id,relation_type,notes,actor):
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM opportunities WHERE id=?",(opportunity_id,)).fetchone():raise KeyError(opportunity_id)
            if not db.execute("SELECT 1 FROM signals WHERE id=?",(signal_id,)).fetchone():raise ValueError("证据不存在")
            db.execute("INSERT INTO opportunity_signal_links(opportunity_id,signal_id,relation_type,notes,created_at) VALUES(?,?,?,?,?) ON CONFLICT(opportunity_id,signal_id) DO UPDATE SET relation_type=excluded.relation_type,notes=excluded.notes",(opportunity_id,signal_id,relation_type,notes,now()))
            self._audit(db,actor,"opportunities","link_evidence","opportunity",opportunity_id,None,{"signal_id":signal_id,"relation_type":relation_type,"notes":notes})
        return self.get_opportunity(opportunity_id)
    def dashboard(self):
        with self.connect() as db:
            row=dict(db.execute("SELECT COUNT(*) total,SUM(decision_status='recommend_now') recommend_now,SUM(decision_status='need_evidence') need_evidence,SUM(decision_status IN ('hold','reject')) paused,SUM(asset_level='light') light,SUM(asset_level='medium') medium,SUM(asset_level='heavy') heavy,ROUND(SUM(stage_budget_limit),0) budget_exposure,SUM(is_demo=1) demo FROM opportunities").fetchone())
            row["signals"]=db.execute("SELECT COUNT(*) FROM signals").fetchone()[0];row["signals_by_source_type"]={r[0]:r[1] for r in db.execute("SELECT source_type,COUNT(*) FROM signals GROUP BY source_type")};row["average_fit"]=db.execute("SELECT ROUND(AVG(total_score),1) FROM opportunity_scores").fetchone()[0] or 0;row["by_stage"]={r[0]:r[1] for r in db.execute("SELECT validation_stage,COUNT(*) FROM opportunities GROUP BY validation_stage")};return row
    def audit_logs(self,limit=100):
        with self.connect() as db:return [dict(r) for r in db.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?",(limit,))]
    @staticmethod
    def _decode_opportunity(row):
        item=dict(row)
        for field in JSON_FIELDS:item[field]=json.loads(item.pop(field+"_json"))
        item["scores"]=json.loads(item.pop("scores_json"));item["is_demo"]=bool(item["is_demo"]);return item
    @staticmethod
    def _audit(db,actor,module,action,object_type,object_id,before,after):
        db.execute("INSERT INTO audit_logs(actor,module,action,object_type,object_id,before_json,after_json,created_at) VALUES(?,?,?,?,?,?,?,?)",(actor,module,action,object_type,str(object_id),json.dumps(before,ensure_ascii=False) if before else None,json.dumps(after,ensure_ascii=False) if after else None,now()))
