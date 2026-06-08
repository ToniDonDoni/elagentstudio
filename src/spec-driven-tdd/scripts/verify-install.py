#!/usr/bin/env python3
"""
verify-install.py — Verify spec-driven-tdd skill install against S-SDT-01.03.

Checks:
  AC1: Installed dir contains exactly the R1 file set (no more, no less)
  AC2: No git repo artifacts leaked (JOURNAL.log, SPEC-*.md, tests/, etc.)
  AC3: README "What's Included" table and result tree match installed layout
  AC4: README install commands (cp SKILL.md, cp references/*) produce R1 set
  XREF: Every local references/ link in SKILL.md resolves to an installed file
  XREF: No non-EXAMPLE files linked via SKILL.md's references/ links

Exit code: 0 if all PASS, 1 if any FAIL.
"""

import os
import re
import sys

INSTALLED = os.path.expanduser("~/.hermes/skills/software-development/spec-driven-tdd")

# --- R1: the minimal file set ---
R1_EXPECTED = {"SKILL.md", "README.md", "references/SPEC-EXAMPLE.md"}

# --- R2: forbidden git artifacts ---
FORBIDDEN_FILES = {
    "JOURNAL.log", "SKILL.current.md", "SPEC-DRAFT.md", "SPEC-ENGLISH.md",
    "SPEC-PACKAGING.md", "TASKS.md",
}
FORBIDDEN_PREFIXES = ("tests/",)

results = {"PASS": [], "FAIL": []}


def _r(name, ok, detail=""):
    list_ = results["PASS" if ok else "FAIL"]
    label = "  ✓" if ok else "  ✗"
    line = f"{label} {name}"
    if detail:
        line += f" — {detail}"
    list_.append(line)


def _gather_files(root):
    """Return list of relative paths for all files under root."""
    out = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for f in filenames:
            out.append(os.path.relpath(os.path.join(dirpath, f), root))
    return sorted(out)


def verify():
    if not os.path.isdir(INSTALLED):
        _r("Skill directory exists", False, f"not found: {INSTALLED}")
        return False

    files = _gather_files(INSTALLED)
    actual = set(files)

    # --- AC1: exactly R1 files ---
    missing = R1_EXPECTED - actual
    extras = actual - R1_EXPECTED
    _r("AC1: R1 files all present", not missing,
       f"missing: {sorted(missing)}" if missing else "")
    _r("AC1: No extra files beyond R1", not extras,
       f"extras: {sorted(extras)}" if extras else "")
    _r(f"AC1: Exactly {len(R1_EXPECTED)} files", len(actual) == len(R1_EXPECTED),
       f"got {len(actual)}")

    # --- AC2: no leaks ---
    has_leaks = False
    for f in files:
        if f in FORBIDDEN_FILES or f.startswith(FORBIDDEN_PREFIXES):
            _r(f"AC2: {f} forbidden", False, "git artifact leaked into install")
            has_leaks = True
        # root-level SPEC-*.md (only allowed in references/)
        if f == "SPEC-EXAMPLE.md" or (os.path.dirname(f) == "" and f.startswith("SPEC-")):
            _r(f"AC2: root-level {f} forbidden", False, "git artifact leaked into install")
            has_leaks = True
    if not has_leaks:
        _r("AC2: No git artifacts leaked", True)

    # --- AC3: README accuracy ---
    readme_path = os.path.join(INSTALLED, "README.md")
    if not os.path.isfile(readme_path):
        _r("AC3: README.md exists", False, "not found in installed dir")
    else:
        with open(readme_path) as fh:
            readme = fh.read()

        # All R1 files mentioned in table
        table_files_ok = all(fname in readme for fname in R1_EXPECTED)
        _r("AC3: README table lists all R1 files", table_files_ok,
           "check table for SKILL.md, README.md, SPEC-EXAMPLE.md" if not table_files_ok else "")

        # No stale file references
        stale_refs = ["spec-example-alignment", "i18n-translation",
                       "dogfooding-session", "codex-review-checklist"]
        stale_found = [s for s in stale_refs if s in readme]
        _r("AC3: No stale file references in README", not stale_found,
           f"found: {stale_found}" if stale_found else "")

        # No templates/ in tree
        has_templates_tree = "templates/" in readme
        _r("AC3: No templates/ in result tree", not has_templates_tree,
           "templates/ still appears in directory tree" if has_templates_tree else "")

    # --- AC4: install commands are correct ---
    if os.path.isfile(readme_path):
        with open(readme_path) as fh:
            readme = fh.read()
        _r("AC4: cp SKILL.md in install section", "cp SKILL.md" in readme)
        _r("AC4: cp references/* in install section", "cp references/*" in readme)
        _r("AC4: No cp templates/* in install section", "cp templates/*" not in readme)

    # --- XREF: SKILL.md references/ links vs installed files ---
    skill_path = os.path.join(INSTALLED, "SKILL.md")
    if os.path.isfile(skill_path):
        with open(skill_path) as fh:
            skill = fh.read()
        refs = set(re.findall(r'\(references/([^)]+)\)', skill))
        missing_refs = [
            r for r in refs
            if not os.path.isfile(os.path.join(INSTALLED, "references", r))
        ]
        _r("XREF: All SKILL.md references/ links resolve", not missing_refs,
           f"missing targets: {missing_refs}" if missing_refs
           else f"all {len(refs)} reference(s) verified ({', '.join(sorted(refs))})")

        non_example = [r for r in refs if "SPEC-EXAMPLE" not in r]
        _r("XREF: No non-EXAMPLE references/ links in SKILL.md", not non_example,
           f"non-EXAMPLE refs: {non_example}" if non_example else "")

    # --- Summary ---
    n_pass = len(results["PASS"])
    n_fail = len(results["FAIL"])
    print("=" * 52)
    print(f"VERIFICATION RESULTS: {n_pass} PASS / {n_fail} FAIL")
    print("=" * 52)
    for status in ("PASS", "FAIL"):
        for line in results[status]:
            print(line)
    print("=" * 52)
    return n_fail == 0


if __name__ == "__main__":
    ok = verify()
    sys.exit(0 if ok else 1)
