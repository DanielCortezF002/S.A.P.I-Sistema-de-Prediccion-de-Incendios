#!/usr/bin/env python3
"""Lectura local de estado Git S.A.P.I. — sin network, no modifica archivos."""
import argparse, subprocess, json
from pathlib import Path

def cmd(repo, args):
    p=subprocess.run(["git","-C",str(repo),*args],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=12)
    return {"ok":p.returncode==0,"value":p.stdout.strip() if p.returncode==0 else p.stderr.strip()}

def main():
    a=argparse.ArgumentParser();a.add_argument("repo",help="Ruta al checkout S.A.P.I.");p=a.parse_args()
    repo=Path(p.repo)
    report={"repo":str(repo.resolve()),"branch":cmd(repo,["branch","--show-current"]),"head":cmd(repo,["rev-parse","HEAD"]),"status":cmd(repo,["status","--short"]),"main":cmd(repo,["rev-parse","origin/main"]),"origin":cmd(repo,["remote","get-url","origin"])}
    print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=="__main__":main()
