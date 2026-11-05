# -*- coding: utf-8 -*-
"""Toggle the instruction layer for the Codex DESKTOP app.

The desktop app runs `codex.exe app-server`, which does not accept `-p`.
So the only lever for it is the `model_instructions_file` line in the main
config.toml. This script rewrites exactly that one line and nothing else.

  python pojia-switch.py --on       point at the generated prompt
  python pojia-switch.py --off      restore the original value
  python pojia-switch.py --status   show current state

(The PowerShell twin in pojia-switch.ps1 does the same thing; this one is for
users on non-Windows or who prefer Python.)
"""
import argparse
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

CODEX_HOME = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
CFG = CODEX_HOME / "config.toml"
STAGE = CODEX_HOME / "pojia"
PROMPT = STAGE / "codex-base.md"
STATE = STAGE / "desktop-switch.json"
BAK_DIR = STAGE / "desktop-backup"

LINE_RE = re.compile(r'^\s*model_instructions_file\s*=\s*(.+?)\s*$')


def current_value():
    for line in CFG.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE_RE.match(line)
        if m:
            return m.group(1).strip()
    return None


def set_value(value):
    lines = CFG.read_text(encoding="utf-8", errors="replace").splitlines()
    hit = False
    for i, line in enumerate(lines):
        if re.match(r'^\s*model_instructions_file\s*=', line):
            lines[i] = f"model_instructions_file = {value}"
            hit = True
    if not hit:
        raise SystemExit("model_instructions_file line not found in config.toml")
    CFG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def status():
    cur = current_value()
    print(f"config : {CFG}")
    print(f"current: {cur}")
    if STATE.exists():
        print("--- desktop-switch.json ---")
        print(STATE.read_text(encoding="utf-8"))
    print(">>> ON" if (cur and "pojia" in cur) else ">>> OFF")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--on", action="store_true")
    ap.add_argument("--off", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    if a.status or (not a.on and not a.off):
        status()
        return 0

    if not CFG.exists():
        raise SystemExit(f"config.toml not found: {CFG}")
    if not PROMPT.exists():
        raise SystemExit(f"prompt not found: {PROMPT}\nrun install.py first")

    old = current_value()
    if not old:
        raise SystemExit("no model_instructions_file line to anchor on")

    BAK_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE.exists():
        bak = BAK_DIR / f"config.toml.before-pojia-{datetime.now():%Y%m%d-%H%M%S}"
        shutil.copy2(CFG, bak)
        STATE.write_text(json.dumps({
            "original": old,
            "backup": str(bak),
            "touched_at": datetime.now().isoformat(timespec="seconds"),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[bak] {bak}")

    if a.on:
        if "pojia" in old:
            print("already on")
            return 0
        new = f'"{PROMPT.as_posix()}"'
        set_value(new)
        print("[ok] ON  (restart the desktop app)")
        print(f"  {old}")
        print(f"  -> {new}")
    else:
        orig = old
        if STATE.exists():
            orig = json.loads(STATE.read_text(encoding="utf-8")).get("original") or old
        if "pojia" in orig:
            raise SystemExit(f"cannot determine original value; edit manually: {CFG}")
        set_value(orig)
        print("[ok] restored  (restart the desktop app)")
        print(f"  {old}")
        print(f"  -> {orig}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
