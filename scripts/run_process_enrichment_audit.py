from __future__ import annotations

import argparse, csv, json
from datetime import datetime
from math import log
from pathlib import Path
from statistics import mean
from typing import Dict, List

from trf_one.backtest import Historical1X2Quote, fit_blend_weight, geometric_blend_1x2
from trf_one.process_model import ProcessXGProxy, ProcessProxyConfig
from trf_one.providers.football_data_uk import ProcessMatchRecord
from trf_one.structural import DixonColesStructuralModel, MatchRecord, StructuralConfig


def dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_process(path: Path) -> Dict[str, List[ProcessMatchRecord]]:
    out: Dict[str, List[ProcessMatchRecord]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            rec=ProcessMatchRecord(
                date=dt(r["date"]),home_team=r["home_team"],away_team=r["away_team"],
                home_goals=float(r["home_goals"]),away_goals=float(r["away_goals"]),
                home_shots=float(r["home_shots"]),away_shots=float(r["away_shots"]),
                home_sot=float(r["home_sot"]),away_sot=float(r["away_sot"]),
                home_corners=float(r["home_corners"]),away_corners=float(r["away_corners"]),
            )
            out.setdefault(r["competition"],[]).append(rec)
    for rows in out.values(): rows.sort(key=lambda x:x.date)
    return out


def load_quotes(path: Path) -> Dict[str, List[Historical1X2Quote]]:
    out={}
    with path.open("r",encoding="utf-8-sig",newline="") as fh:
        for r in csv.DictReader(fh):
            out.setdefault(r["competition"],[]).append(Historical1X2Quote(
                date=dt(r["date"]),home_team=r["home_team"],away_team=r["away_team"],
                home_odds=float(r["home_odds"]),draw_odds=float(r["draw_odds"]),
                away_odds=float(r["away_odds"]),bookmaker=r["bookmaker"],snapshot_type=r["snapshot_type"],
            ))
    return out


def outcome(r):
    return 0 if r.home_goals>r.away_goals else 1 if r.home_goals==r.away_goals else 2


def brier(rows):
    return sum(sum((p-(1 if i==y else 0))**2 for i,p in enumerate(probs)) for probs,y in rows)/len(rows)


def ll(rows):
    return sum(-log(max(min(probs[y],1-1e-15),1e-15)) for probs,y in rows)/len(rows)


def block_id(d: datetime):
    return (d.year,(d.month-1)//3+1)


def audit_comp(rows,quotes,min_train=500):
    qmap={(q.date,q.home_team,q.away_team):q for q in quotes if q.snapshot_type=="CLOSE"}
    blocks=sorted({block_id(r.date) for r in rows})
    goal_rows=[]; proc_rows=[]; market_rows=[]; blend_rows=[]
    hist_market=[]; hist_proc=[]; hist_y=[]; weights=[]

    common=dict(half_life_days=365,ridge=.05,learning_rate=.035,max_iter=120,tol=1e-6,
                rho_min=-.18,rho_max=.18,rho_steps=25,max_goals=9)
    base_cfg=StructuralConfig(target_mode="goals",**common)
    proc_cfg=StructuralConfig(target_mode="xg",**common)

    for block in blocks:
        test=[r for r in rows if block_id(r.date)==block]
        cutoff=min(r.date for r in test)
        train=[r for r in rows if r.date<cutoff]
        if len(train)<min_train: continue

        goal_train=[MatchRecord(r.date,r.home_team,r.away_team,r.home_goals,r.away_goals) for r in train]
        goal_model=DixonColesStructuralModel(base_cfg).fit(goal_train,as_of=cutoff)

        proxy=ProcessXGProxy(ProcessProxyConfig(max_iter=140,tol=1e-6)).fit(train)
        proc_model=DixonColesStructuralModel(proc_cfg).fit(proxy.transform(train),as_of=cutoff)

        w=fit_blend_weight(hist_market,hist_proc,hist_y,step=.05) if len(hist_y)>=250 else 0.0
        pending=[]
        for r in test:
            q=qmap.get((r.date,r.home_team,r.away_team))
            if q is None: continue
            gp=goal_model.forecast(r.home_team,r.away_team).probabilities
            pp=proc_model.forecast(r.home_team,r.away_team).probabilities
            p_goal=(gp["home_win"],gp["draw"],gp["away_win"])
            p_proc=(pp["home_win"],pp["draw"],pp["away_win"])
            p_market=q.fair_probabilities("shin")
            y=outcome(r)
            p_blend=geometric_blend_1x2(p_market,p_proc,w)
            goal_rows.append((p_goal,y)); proc_rows.append((p_proc,y))
            market_rows.append((p_market,y)); blend_rows.append((p_blend,y))
            weights.append(w); pending.append((p_market,p_proc,y))
        for a,b,y in pending:
            hist_market.append(a); hist_proc.append(b); hist_y.append(y)

    return {
        "n":len(proc_rows),
        "market":{"log_loss":ll(market_rows),"brier":brier(market_rows)},
        "goals_model":{"log_loss":ll(goal_rows),"brier":brier(goal_rows)},
        "process_model":{"log_loss":ll(proc_rows),"brier":brier(proc_rows)},
        "market_process_blend":{
            "log_loss":ll(blend_rows),"brier":brier(blend_rows),
            "mean_process_weight":mean(weights) if weights else 0.0,
            "final_process_weight":weights[-1] if weights else 0.0
        },
        "delta_vs_market":{
            "goals_log_loss":ll(goal_rows)-ll(market_rows),
            "process_log_loss":ll(proc_rows)-ll(market_rows),
            "blend_log_loss":ll(blend_rows)-ll(market_rows),
            "goals_brier":brier(goal_rows)-brier(market_rows),
            "process_brier":brier(proc_rows)-brier(market_rows),
            "blend_brier":brier(blend_rows)-brier(market_rows),
        },
        "method":{
            "refit":"quarterly blocked walk-forward",
            "process_proxy":"shots + shots on target + corners, training-window only",
            "structural_max_iter":120,
            "proxy_max_iter":140,
            "note":"Quarterly blocking reduces compute while preserving strict chronological OOS comparison."
        }
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--process",default="data/process/process.csv")
    ap.add_argument("--odds",default="data/process/odds_1x2.csv")
    ap.add_argument("--output",default="data/process/process_audit.json")
    args=ap.parse_args()
    process=load_process(Path(args.process)); quotes=load_quotes(Path(args.odds))
    report={"competitions":{}}
    for comp in sorted(process):
        if comp not in quotes: continue
        print("Process audit",comp,flush=True)
        report["competitions"][comp]=audit_comp(process[comp],quotes[comp])
    Path(args.output).write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
