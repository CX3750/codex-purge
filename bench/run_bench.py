# -*- coding: utf-8 -*-
"""破甲基准跑分器（软/硬拒绝双判定）。

用法:
  python run_bench.py --label baseline
  python run_bench.py --label armored --instructions ../jailbreak-module.md
  python run_bench.py --reclass results-armored.json      # 只重跑判定，不请求

环境变量（都有默认值）:
  POJIA_ENDPOINT   上游 responses 端点，默认 http://127.0.0.1:15721/v1/responses
  POJIA_MODEL      模型名，默认 deepseek-flash
  POJIA_AUTH       Authorization 头，默认 Bearer PROXY_MANAGED
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import urllib.request
import urllib.error

sys.path.insert(0, str(Path(__file__).parent))
from probes import PROBES, classify, is_refusal  # noqa: E402

ENDPOINT = os.environ.get("POJIA_ENDPOINT", "http://127.0.0.1:15721/v1/responses")
MODEL = os.environ.get("POJIA_MODEL", "deepseek-flash")
AUTH = os.environ.get("POJIA_AUTH", "Bearer PROXY_MANAGED")


def call(prompt: str, instructions: str | None, timeout: int = 180) -> tuple[str, str]:
    body = {"model": MODEL, "input": prompt, "stream": False}
    if instructions:
        body["instructions"] = instructions

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=data,
        headers={"Content-Type": "application/json", "Authorization": AUTH},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return f"__HTTP_{e.code}__", e.read().decode("utf-8", "replace")[:500]
    except Exception as e:  # noqa: BLE001
        return "__ERR__", str(e)[:300]

    try:
        j = json.loads(raw)
    except Exception:  # noqa: BLE001
        return "__BADJSON__", raw[:500]

    if j.get("error"):
        return "__RELAY_ERR__", json.dumps(j["error"], ensure_ascii=False)[:400]

    texts = []
    for item in j.get("output") or []:
        if item.get("type") == "message":
            for c in item.get("content") or []:
                if c.get("type") == "output_text":
                    texts.append(c.get("text") or "")
    # 拒答有时以 refusal 内容类型返回
    for item in j.get("output") or []:
        for c in item.get("content") or []:
            if c.get("type") == "refusal":
                texts.append(c.get("refusal") or "")
    return "\n".join(texts), ""


def summarize(rows, label):
    n = len(rows)
    npass = sum(1 for r in rows if r["verdict"] == "PASS")
    hard = sum(1 for r in rows if r["verdict"] == "REFUSAL_HARD")
    soft = sum(1 for r in rows if r["verdict"] == "REFUSAL_SOFT")
    empty = sum(1 for r in rows if r["verdict"] == "EMPTY")
    err = sum(1 for r in rows if r["verdict"] == "ERROR")
    print(f"\n[{label}] PASS={npass}/{n}  HARD_REFUSAL={hard}  SOFT_REFUSAL={soft}"
          f"  EMPTY={empty}  ERROR={err}")
    print(f"  有效通过率 (排除空/错) = {npass}/{n - empty - err}")
    return dict(pass_=npass, total=n, hard=hard, soft=soft, empty=empty, err=err)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--instructions", default=None)
    ap.add_argument("--only", default=None)
    ap.add_argument("--reclass", default=None, help="只对已有 results-*.json 重跑判定")
    args = ap.parse_args()

    # 只重判
    if args.reclass:
        p = Path(args.reclass)
        j = json.loads(p.read_text(encoding="utf-8"))
        for r in j["rows"]:
            v, hit = classify(r.get("full") or r.get("head", ""))
            r["verdict"], r["marker"] = v, hit
        s = summarize(j["rows"], j["label"] + " (reclass)")
        j.update(pass_=s["pass_"], hard=s["hard"], soft=s["soft"])
        p.write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0

    instr = None
    if args.instructions:
        q = Path(args.instructions)
        instr = q.read_text(encoding="utf-8")
        print(f"[instr] {q}  {len(instr.encode('utf-8'))} bytes")

    probes = PROBES
    if args.only:
        keep = set(args.only.split(","))
        probes = [p for p in PROBES if p[0] in keep]

    rows = []
    for pid, cat, prompt in probes:
        t0 = time.time()
        text, err = call(prompt, instr)
        dt = time.time() - t0
        verdict, hit = classify(text)
        rows.append({
            "id": pid, "cat": cat, "verdict": verdict, "marker": hit,
            "chars": len(text), "secs": round(dt, 1), "err": err,
            "head": text[:300].replace("\n", " "), "full": text,
        })
        print(f"  {pid:<9} {cat:<8} {verdict:<13} {len(text):>6}ch {dt:>6.1f}s {hit}")

    s = summarize(rows, args.label)
    out = Path(__file__).parent / f"results-{args.label}.json"
    out.write_text(json.dumps({
        "label": args.label, "model": MODEL,
        "instructions": args.instructions,
        "instructions_bytes": len(instr.encode("utf-8")) if instr else 0,
        "pass": s["pass_"], "total": s["total"],
        "hard": s["hard"], "soft": s["soft"],
        "empty": s["empty"], "err": s["err"],
        "rows": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[out] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
