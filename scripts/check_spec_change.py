"""spec/contract 变更必须伴随 test 变更的检查（SDD 闸门）。

用法：
  python scripts/check_spec_change.py          # 检查暂存区（staged）
  python scripts/check_spec_change.py HEAD     # 检查最近一次提交

退出码：
  0 通过；1 存在 spec/contract 变更但无 test 变更；2 无法读取 git 状态。

设计：
- 任何 spec / contract 文档或契约代码的变更，都必须至少伴随一个 tests/ 变更，
  保证「规格先行、测试同步」，避免契约与实现/测试静默脱节。
- 纯文档勘误（typo）可加 `--allow-docs-only` 显式跳过，但默认不跳过。
"""
from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

SPEC_PATTERNS = (
    "docs/**/*-spec*.md",
    "docs/**/*-contract*.md",
    "src/chanlun/*_contract.py",
)

TEST_PATTERNS = ("tests/**",)

HOOK_SKIP_ENV = "SPEC_CHANGE_CHECK_ALLOW_DOCS_ONLY"


def _changed_files(target: str | None) -> list[str]:
    if target is None:
        cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]
    else:
        cmd = ["git", "diff", "--name-only", "--diff-filter=ACMR", target]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git diff failed")
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="git ref to diff against (default: staged changes)",
    )
    parser.add_argument(
        "--allow-docs-only",
        action="store_true",
        help="explicitly allow spec/contract changes without test changes (typo-only fixes)",
    )
    args = parser.parse_args()

    allow_docs_only = args.allow_docs_only or __import__("os").environ.get(HOOK_SKIP_ENV) == "1"

    try:
        files = _changed_files(args.target)
    except RuntimeError as exc:
        print(f"[spec-change-check] {exc}", file=sys.stderr)
        return 2

    spec_changed = [path for path in files if _matches(path, SPEC_PATTERNS)]
    test_changed = [path for path in files if _matches(path, TEST_PATTERNS)]

    if not spec_changed:
        print("[spec-change-check] no spec/contract change detected — pass")
        return 0

    if test_changed:
        print(
            f"[spec-change-check] spec/contract change accompanied by test change — pass "
            f"({len(spec_changed)} spec file(s), {len(test_changed)} test file(s))"
        )
        return 0

    print(
        "[spec-change-check] BLOCKED: spec/contract changed but no tests/ changed.",
        file=sys.stderr,
    )
    for path in spec_changed:
        print(f"  spec/contract: {path}", file=sys.stderr)
    print(
        "  Add/update a test under tests/ in the same commit, or run with "
        f"--allow-docs-only (env {HOOK_SKIP_ENV}=1) for typo-only fixes.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
