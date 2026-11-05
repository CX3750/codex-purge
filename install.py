# -*- coding: utf-8 -*-
"""Install the pojia instruction layer.

Writes:
  $CODEX_HOME/pojia/codex-base.md      module + official base, spliced
  $CODEX_HOME/pojia.config.toml        profile layer (from profiles/ template)
  $CODEX_HOME/pojia/install-state.json state record

The main config.toml is NOT modified. Rollback deletes the profile layer.

Usage:
  python install.py              install
  python install.py --status     show state
  python install.py --rollback   remove the profile layer
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent
MODULE_SRC = REPO / "jailbreak-module.md"
PROFILE_TPL = REPO / "profiles" / "pojia.config.toml"

PROFILE_NAME = "pojia"

CODEX_HOME = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
STAGE = CODEX_HOME / PROFILE_NAME
PROMPT_FILE = STAGE / "codex-base.md"
PROFILE_FILE = CODEX_HOME / f"{PROFILE_NAME}.config.toml"
STATE_FILE = STAGE / "install-state.json"

# Candidate locations for the official base instructions. Using the one that is
# already effective keeps Codex's own tool discipline (apply_patch / exec / plan).
BASE_CANDIDATES = [
    CODEX_HOME / "purge-instructions.md",
    CODEX_HOME / "codex-purge" / "official-template.txt",
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def find_base():
    for c in BASE_CANDIDATES:
        if c.exists() and c.stat().st_size > 2000:
            return c
    return None


def build_prompt():
    """Splice module + official base. Module first: it sets the contract.

    Keeping the official base is deliberate. Replacing base instructions
    wholesale drops the tool-use rules (apply_patch / exec_command /
    update_plan), which visibly degrades coding performance.
    """
    module_txt = MODULE_SRC.read_text(encoding="utf-8")
    base = find_base()

    if base:
        base_txt = base.read_text(encoding="utf-8", errors="replace")
        merged = module_txt.rstrip() + "\n\n" + base_txt.lstrip()
        src = f"{base.name} ({base.stat().st_size}B)"
    else:
        merged = module_txt
        src = "module-only (no official base found)"

    STAGE.mkdir(parents=True, exist_ok=True)
    PROMPT_FILE.write_text(merged, encoding="utf-8")
    return PROMPT_FILE, src


def write_profile():
    tpl = PROFILE_TPL.read_text(encoding="utf-8")
    posix = PROMPT_FILE.as_posix()
    # Substitute only on the assignment line, never inside comments.
    lines = []
    for line in tpl.splitlines():
        if line.lstrip().startswith("model_instructions_file") and "@PROMPT_PATH@" in line:
            line = f'model_instructions_file = "{posix}"'
        lines.append(line)
    body = "\n".join(lines) + "\n"
    header = (
        f"# pojia profile layer — generated {datetime.now().isoformat(timespec='seconds')}\n"
        f"# from profiles/{PROFILE_TPL.name}; edit the template and re-run install.py\n"
        f"# activate: codex -p {PROFILE_NAME}\n"
        f"# rollback: python install.py --rollback\n\n"
    )
    PROFILE_FILE.write_text(header + body, encoding="utf-8")
    return PROFILE_FILE


def cmd_install() -> int:
    if not MODULE_SRC.exists():
        print(f"[!] module missing: {MODULE_SRC}")
        return 1
    if not PROFILE_TPL.exists():
        print(f"[!] profile template missing: {PROFILE_TPL}")
        return 1

    STAGE.mkdir(parents=True, exist_ok=True)

    # Back up an existing profile layer, but never overwrite the first backup
    if PROFILE_FILE.exists() and not STATE_FILE.exists():
        bak = PROFILE_FILE.with_suffix(f".toml.bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(PROFILE_FILE, bak)
        print(f"[bak] {bak}")

    prompt, src = build_prompt()
    cfg = write_profile()

    state = {
        "installed_at": datetime.now().isoformat(timespec="seconds"),
        "codex_home": str(CODEX_HOME),
        "profile_name": PROFILE_NAME,
        "profile_file": str(PROFILE_FILE),
        "prompt_file": str(prompt),
        "prompt_bytes": prompt.stat().st_size,
        "base_source": src,
        "main_config_touched": False,
        "activate": f"codex -p {PROFILE_NAME}",
        "rollback": "python install.py --rollback",
    }
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    main_cfg = CODEX_HOME / "config.toml"
    print(f"[ok] prompt  : {prompt}  ({prompt.stat().st_size}B)")
    print(f"[ok] base    : {src}")
    print(f"[ok] profile : {PROFILE_FILE}")
    print(f"[ok] main config untouched: {main_cfg}")
    print()
    print(f"activate:  codex -p {PROFILE_NAME}")
    print(f"rollback:  python {Path(__file__).name} --rollback")
    return 0


def cmd_status() -> int:
    print(f"CODEX_HOME : {CODEX_HOME}")
    print(f"profile    : {PROFILE_FILE}  {'present' if PROFILE_FILE.exists() else 'absent'}")
    if PROFILE_FILE.exists():
        print(f"             {PROFILE_FILE.stat().st_size}B  sha={sha(PROFILE_FILE)}")
    for p in (MODULE_SRC, PROMPT_FILE):
        state = "present" if p.exists() else "absent"
        extra = f"  {p.stat().st_size}B  sha={sha(p)}" if p.exists() else ""
        print(f"{p.name:<24} {state}{extra}")
    if STATE_FILE.exists():
        print("\n--- install-state.json ---")
        print(STATE_FILE.read_text(encoding="utf-8"))
    return 0


def cmd_rollback() -> int:
    if PROFILE_FILE.exists():
        bak = PROFILE_FILE.with_suffix(f".toml.removed-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.move(str(PROFILE_FILE), str(bak))
        print(f"[ok] profile archived: {bak}")
    else:
        print("[i] no profile layer to remove")
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    print("[ok] done. The main config.toml was never modified by this installer.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    args = ap.parse_args()
    if args.status:
        return cmd_status()
    if args.rollback:
        return cmd_rollback()
    return cmd_install()


if __name__ == "__main__":
    raise SystemExit(main())
