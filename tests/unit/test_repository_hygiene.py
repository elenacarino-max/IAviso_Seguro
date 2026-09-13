"""Controles de cierre sobre los archivos que Git publicaría."""

import re
import subprocess
from pathlib import Path

_ROOT = Path(__file__).parents[2]
_SECRET_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"BEGIN (?:RSA|OPENSSH|EC) PRIVATE KEY"),
)
_PUBLIC_DOCUMENTATION = {
    "docs/ARQUITECTURA_E_INTEGRACIONES.md",
    "docs/GUIA_FUNCIONAL.md",
}


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def test_internal_and_runtime_artifacts_are_not_versioned():
    tracked = _tracked_files()

    tracked_docs = {path for path in tracked if path.startswith("docs/")}
    assert tracked_docs <= _PUBLIC_DOCUMENTATION
    assert ".env" not in tracked
    assert not any(
        Path(path).suffix.lower() in {".db", ".sqlite", ".sqlite3", ".log"}
        for path in tracked
    )


def test_tracked_text_has_no_recognizable_private_keys_or_google_api_keys():
    for relative_path in _tracked_files():
        path = _ROOT / relative_path
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        assert not any(pattern.search(content) for pattern in _SECRET_PATTERNS), (
            f"Posible secreto versionado en {relative_path}"
        )
