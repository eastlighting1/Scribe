from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {
    ".git",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
    ".idea",
    ".vscode",
}
TEXT_EXTENSIONS = {
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
    ".json",
    ".ini",
    ".cfg",
}
SECRET_VALUE_RE = re.compile(
    r"""(?ix)
    \b(token|api[_-]?key|secret|password)\b
    \s*[:=]\s*
    ["']?
    ([A-Za-z0-9_\-\/+=]{8,})
    ["']?
    """
)
HIGH_ENTROPY_RE = re.compile(r"\b(?:ghp|github_pat|sk|AIza)[A-Za-z0-9_\-]{8,}\b")
DANGEROUS_API_PATTERNS = {
    "pickle.loads": re.compile(r"\bpickle\.loads\s*\("),
    "pickle.load": re.compile(r"\bpickle\.load\s*\("),
    "marshal.loads": re.compile(r"\bmarshal\.loads\s*\("),
    "marshal.load": re.compile(r"\bmarshal\.load\s*\("),
    "eval": re.compile(r"(?<!\w)eval\s*\("),
    "exec": re.compile(r"(?<!\w)exec\s*\("),
}
PLACEHOLDER_MARKERS = (
    "example",
    "placeholder",
    "changeme",
    "your_",
    "your-",
    "<",
    "dummy",
    "sample",
)


@dataclass(slots=True)
class Finding:
    path: Path
    message: str


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name in {"Dockerfile", ".gitignore"}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def check_required_files() -> list[str]:
    errors: list[str] = []
    if not (ROOT / "SECURITY.md").exists():
        errors.append("Missing SECURITY.md")
    if not any(ROOT.glob("LICENSE*")):
        errors.append("Missing LICENSE file")
    lock_candidates = ["uv.lock", "poetry.lock", "requirements.txt"]
    if not any((ROOT / name).exists() for name in lock_candidates):
        errors.append("Missing lock or requirements file (uv.lock, poetry.lock, or requirements.txt)")
    return errors


def check_secret_patterns(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in files:
        if not is_text_file(path):
            continue
        text = read_text(path)
        for match in SECRET_VALUE_RE.finditer(text):
            value = match.group(2)
            if any(marker in value.lower() for marker in PLACEHOLDER_MARKERS):
                continue
            findings.append(Finding(path.relative_to(ROOT), f"Possible hardcoded secret pattern: {match.group(0)!r}"))
        for match in HIGH_ENTROPY_RE.finditer(text):
            findings.append(Finding(path.relative_to(ROOT), f"Possible high-entropy credential token: {match.group(0)!r}"))
    return findings


def check_dangerous_apis(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in files:
        if path.suffix != ".py":
            continue
        text = read_text(path)
        for label, pattern in DANGEROUS_API_PATTERNS.items():
            if pattern.search(text):
                findings.append(Finding(path.relative_to(ROOT), f"Dangerous API usage detected: {label}"))
    return findings


def check_validation_boundary(files: list[Path]) -> list[str]:
    candidate_texts: list[str] = []
    for path in files:
        if path.suffix != ".py":
            continue
        text = read_text(path)
        if "deserialize_" in text or "compat" in text.lower():
            candidate_texts.append(text)
    if not candidate_texts:
        return ["Validation boundary check: no deserializer/compatibility reader implementation found; skipping."]

    combined = "\n".join(candidate_texts)
    if "validate_" not in combined and "raise_for_errors" not in combined:
        return ["Validation boundary check: deserializer/compatibility code found without obvious validation call."]
    return ["Validation boundary check: deserializer/compatibility code appears to call validation paths."]


def check_test_presence() -> list[str]:
    errors: list[str] = []
    test_files = list((ROOT / "tests").glob("test_*.py"))
    if not test_files:
        errors.append("Missing pytest-style test files under tests/")
    content = "\n".join(read_text(path) for path in test_files)
    for marker in ("validate", "serialize", "compat"):
        if marker not in content.lower():
            errors.append(f"Tests do not appear to cover '{marker}' behavior")
    return errors


def check_workflows() -> list[str]:
    errors: list[str] = []
    workflows = list((ROOT / ".github" / "workflows").glob("*.yml"))
    if not workflows:
        return ["Missing .github/workflows configuration"]
    combined = "\n".join(read_text(path) for path in workflows)
    for marker in ("pytest", "ruff", "mypy"):
        if marker not in combined:
            errors.append(f"Workflow configuration does not appear to run {marker}")
    return errors


def check_example_presence() -> list[str]:
    expected = [
        ROOT / "examples" / "training_workflow.py",
        ROOT / "examples" / "evaluation_workflow.py",
        ROOT / "examples" / "artifact_binding_workflow.py",
    ]
    errors: list[str] = []
    for path in expected:
        if not path.exists():
            errors.append(f"Missing example workflow: {path.relative_to(ROOT)}")
    return errors


def main() -> int:
    files = iter_files()
    errors = check_required_files()
    errors.extend(check_test_presence())
    errors.extend(check_workflows())
    errors.extend(check_example_presence())

    secret_findings = check_secret_patterns(files)
    dangerous_findings = check_dangerous_apis(files)
    validation_notes = check_validation_boundary(files)

    if validation_notes:
        for note in validation_notes:
            print(f"[info] {note}")

    for finding in secret_findings:
        errors.append(f"{finding.path}: {finding.message}")
    for finding in dangerous_findings:
        errors.append(f"{finding.path}: {finding.message}")

    if errors:
        print("Repository security checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Repository security checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
