from __future__ import annotations

import argparse, csv, json
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from math import log
from pathlib import Path
from statistics import mean
from typing import Dict, List, Tuple

from trf_one.backtest import Historical1X2Quote, fit_blend_weight, geometric_blend_1x2
from trf_one.providers.understat import normalize_team_name
from trf_one.structural import DixonColesStructuralModel, MatchRecord, StructuralConfig


def dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_football_matches(path: Path):
    out=defaultdict(list)
    with path.open("r",encoding="utf-8-sig",newline="") as fh:
        for r in csv.DictReader(fh):
            out[r["competition"]].append({
                "date":dt(r["date"]),"home":r["home_team"],"away":r["away_team"],
                "hg":int(float(r["home_goals"])),"ag":int(float(r["away_goals"]))
            })
    return out


def load_xg(path: Path):
    out=defaultdict(list)
    with path.open("r",encoding="utf-8-sig",newline="") as fh:
        for r in csv.DictReader(fh):
            out[r["competition"]].append({
                "date":dt(r["date"]),"home":r["home_team"],"away":r["away_team"],
                "hg":int(r["home_goals"]),"ag":int(r["away_goals"]),
                "hxg":float(r["home_xg"]),"axg":float(r["away_xg"])
            })
    return out


def load_quotes(path: Path):
    out=defaultdict(list)
    with path.open("r",encoding="utf-8-sig",newline="") as fh:
        for r in csv.DictReader(fh):
            out[r["competition"]].append(Historical1X2Quote(
                date=dt(r["date"]),home_team=r["home_team"],away_team=r["away_team"],
                home_odds=float(r["home_odds"]),draw_odds=float(r["draw_odds"]),away_odds=float(r["away_odds"]),
                bookmaker=r["bookmaker"],snapshot_type=r["snapshot_type"]
            ))
    return out


def similarity(a: str,b: str) -> float:
    return SequenceMatcher(None,normalize_team_name(a),normalize_team_name(b)).ratio()


def align_xg_to_football_data(xg_rows, fd_rows):
    by_key=defaultdict(list)
    for r in fd_rows:
        by_key[(r["date"].date(),r["hg"],r["ag"])].append(r)

    aligned=[]; rejected=0
    for x in xg_rows:
        candidates=by_key.get((x["date"].date(),x["hg"],x["ag"]),[])
        if not candidates:
            rejected+=1; continue
        scored=[]
        for c in candidates:
            s=(similarity(x["home"],c["home"])+similarity(x["away"],c["away"]))/2
            scored.append((s,c))
        scored.sort(key=lambda z:z[0],reverse=True)
        if not scored or scored[0][0] < 0.58:
            rejected+=1; continue
        if len(scored)>1 and scored[0][0]-scored[1][0] < 0.08:
            rejected+=1; continue
        c=scored[0][1]
        aligned.append(MatchRecord(
            date=c["date"],home_team=c["home"],away_team=c["away"],
            home_goals=c["hg"],away_goals=c["ag"],home_xg=x["hxg"],away_xg=x["axg"]
        ))
    aligned.sort(key=lambda r:r.date)
    return aligned,rejected


def outcome(r: MatchRecord):
    return 0 if r.home_goals>r.away_goals else 1 if r.home_goals==r.away_goals else 2


def ll(rows):
    return sum(-log(max(min(p[y],1-1e-15),1e-15)) for p,y in rows)/len(rows)


def brier(rows):
    return sum(sum((p-(1 if i==y else 0))**2 for i,p in enumerate(probs)) for probs,y in rows)/len(rows)


def block_id(d):
    return (d.year,(d.month-1)//3+1)


def audit_comp(rows: List[MatchRecord], quotes: List[Historical1X2Quote], min_train=500):
    qmap={(q.date.date(),q.home_team,q.away_team):q for q in quotes if q.snapshot_type=="CLOSE"}
    blocks=sorted({block_id(r.date) for r in rows})
    market_rows=[]; goals_rows=[]; xg_rows=[]; blend_rows=[]; weights=[]
    hist_market=[]; hist_xg=[]; hist_y=[]

    common=dict(half_life_days=365,ridge=.05,learning_rate=.035,max_iter=130,tol=1e-6,
                rho_min=-.18,rho_max=.18,rho_steps=25,max_goals=9)
    goals_cfg=StructuralConfig(target_mode="goals",**common)
    xg_cfg=StructuralConfig(target_mode="xg",**common)

    for block in blocks:
        test=[r for r in rows if block_id(r.date)==block]
        cutoff=min(r.date for r in test)
        train=[r for r in rows if r.date<cutoff]
        if len(train)<min_train: continue

        goals_model=DixonColesStructuralModel(goals_cfg).fit(train,as_of=cutoff)
        xg_model=DixonColesStructuralModel(xg_cfg).fit(train,as_of=cutoff)
        w=fit_blend_weight(hist_market,hist_xg,hist_y,step=.05) if len(hist_y)>=250 else 0.0
        pending=[]

        for r in test:
            q=qmap.get((r.date.date(),r.home_team,r.away_team))
            if q is None: continue
            gp=goals_model.forecast(r.home_team,r.away_team).probabilities
            xp=xg_model.forecast(r.home_team,r.away_team).probabilities
            p_goal=(gp["home_win"],gp["draw"],gp["away_win"])
            p_xg=(xp["home_win"],xp["draw"],xp["away_win"])
            p_market=q.fair_probabilities("shin")
            y=outcome(r)
            p_blend=geometric_blend_1x2(p_market,p_xg,w)
            market_rows.append((p_market,y)); goals_rows.append((p_goal,y)); xg_rows.append((p_xg,y)); blend_rows.append((p_blend,y))
            weights.append(w); pending.append((p_market,p_xg,y))
        for a,b,y in pending:
            hist_market.append(a); hist_xg.append(b); hist_y.append(y)

    return {
        "n":len(xg_rows),
        "market":{"log_loss":ll(market_rows),"brier":brier(market_rows)},
        "goals_model":{"log_loss":ll(goals_rows),"brier":brier(goals_rows)},
        "real_xg_model":{"log_loss":ll(xg_rows),"brier":brier(xg_rows)},
        "market_xg_blend":{
            "log_loss":ll(blend_rows),"brier":brier(blend_rows),
            "mean_xg_weight":mean(weights) if weights else 0.0,
            "final_xg_weight":weights[-1] if weights else 0.0
        },
        "delta_vs_market":{
            "goals_log_loss":ll(goals_rows)-ll(market_rows),
            "xg_log_loss":ll(xg_rows)-ll(market_rows),
            "blend_log_loss":ll(blend_rows)-ll(market_rows),
            "goals_brier":brier(goals_rows)-brier(market_rows),
            "xg_brier":brier(xg_rows)-brier(market_rows),
            "blend_brier":brier(blend_rows)-brier(market_rows),
        }
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--matches",default="data/xg/matches.csv")
    p.add_argument("--odds",default="data/xg/odds_1x2.csv")
    p.add_argument("--xg",default="data/xg/understat_xg.csv")
    p.add_argument("--output",default="data/xg/real_xg_audit.json")
    args=p.parse_args()

    fd=load_football_matches(Path(args.matches)); xg=load_xg(Path(args.xg)); quotes=load_quotes(Path(args.odds))
    report={"competitions":{},"alignment":{}}
    for comp in sorted(xg):
        aligned,rejected=align_xg_to_football_data(xg[comp],fd.get(comp,[]))
        report["alignment"][comp]={
            "understat_rows":len(xg[comp]),"aligned":len(aligned),"rejected":rejected,
            "coverage":len(aligned)/len(xg[comp]) if xg[comp] else 0.0
        }
        if len(aligned)<500:
            continue
        print(f"Real xG audit {comp}: aligned {len(aligned)}/{len(xg[comp])}",flush=True)
        report["competitions"][comp]=audit_comp(aligned,quotes.get(comp,[]))
    Path(args.output).write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
