# DEMO database for screenshots only: invented scores, NOT results. Built outside the repo.
import sys
from datetime import UTC, datetime

from src.database import get_engine, get_session, init_db
from src.models import PaperORM, RunORM, ScoreORM

url = "sqlite:///" + sys.argv[1]
e = get_engine(url); init_db(e); s = get_session(e)
rows = [("demo_01","DEMO Alpha Trees","ICLR",2020,80,"Verified"),("demo_02","DEMO Beta Nets","NeurIPS",2022,55,"Partially Verified"),
        ("demo_03","DEMO Gamma Forests","ICML",2021,35,"Needs Review"),("demo_04","DEMO Delta Boosting","KDD",2019,10,"Failed"),
        ("demo_05","DEMO Epsilon (not scored)","ICLR",2023,None,None)]
for pid,t,v,y,sc,lab in rows:
    s.add(PaperORM(paper_id=pid,title=t,year=y,venue=v,repo_url="https://example.org/r",paper_url=None,license="MIT",target_script="m.py",expected_claims="{}",source_table_or_section="{}"))
s.flush()
for pid,t,v,y,sc,lab in rows:
    if sc is None: continue
    s.add(RunORM(run_id=f"run-{pid}",paper_id=pid,status="COMPLETED" if sc>50 else "FAILED",exit_code=0 if sc>50 else 1,execution_time=42.0,stdout="demo line 1\ndemo line 2",stderr="",timestamp=datetime(2026,10,1,tzinfo=UTC)))
    s.flush()
    s.add(ScoreORM(score_id=f"s-{pid}",paper_id=pid,run_id=f"run-{pid}",tier1_build=sc,tier2_metrics=sc/2,tier3_stability=sc/4,tier4_artifacts=60.0,total_score=sc,status_label=lab,summary="DEMO DATA: invented for a screenshot."))
s.commit()
