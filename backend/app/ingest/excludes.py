"""what the rest walk reads and does not read. a map that names what it did not
read beats one that ran out of time: skipped paths are reported, never hidden."""

import fnmatch

# dependency folders, build output, binaries, media, env files, secret patterns
DEFAULT_EXCLUDED_DIRS = {
    "node_modules", ".venv", "venv", "__pycache__", ".git", ".svn", ".tox",
    "dist", "build", "target", "vendor", "coverage", ".next", ".nuxt",
    ".terraform", ".idea", ".vscode", " Pods".strip(),
}
DEFAULT_EXCLUDED_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".pdf", ".zip",
    ".tar", ".gz", ".tgz", ".7z", ".rar", ".exe", ".dll", ".so", ".dylib",
    ".bin", ".woff", ".woff2", ".ttf", ".otf", ".mp3", ".mp4", ".mov", ".lock",
    ".pyc", ".class", ".jar", ".wasm", ".glb", ".gltf", ".db", ".sqlite",
}
DEFAULT_EXCLUDED_FILES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "package-lock.json", "yarn.lock", "poetry.lock", "pdm.lock",
}
SECRET_FILE_PATTERN = ".env"

# priority: readme, manifests, configs, docs first; code after; the walk fills
# its budget from the front
PRIORITY_PREFIXES = [
    ("readme", 0), ("license", 9), ("changelog", 9), ("docs/", 1),
    ("package.json", 0), ("pyproject.toml", 0), ("requirements", 0),
    ("cargo.toml", 0), ("go.mod", 0), ("dockerfile", 1), ("docker-compose", 1),
    (".github/", 2), ("spec", 2), ("readme", 0),
]
CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".rb", ".java", ".kt", ".swift", ".md", ".txt", ".json", ".toml", ".yml", ".yaml", ".cfg", ".ini", ".sh"}


class Excludes:
    def __init__(self, beholderignore: str | None = None):
        self.patterns = [l.strip() for l in (beholderignore or "").splitlines() if l.strip() and not l.strip().startswith("#")]

    def is_excluded(self, path: str) -> bool:
        parts = path.split("/")
        name = parts[-1].lower()
        for p in self.patterns:
            if fnmatch.fnmatch(path, p) or fnmatch.fnmatch(name, p):
                return True
            if p.endswith("/") and (f"/{p}" in path or path.startswith(p)):
                return True  # directory pattern: anywhere in the path
        if any(d.lower() in DEFAULT_EXCLUDED_DIRS for d in parts[:-1]):
            return True
        if name in DEFAULT_EXCLUDED_FILES:
            return True
        if SECRET_FILE_PATTERN in name:
            return True
        dot = name.rfind(".")
        if dot > 0 and name[dot:] in DEFAULT_EXCLUDED_SUFFIXES:
            return True
        return False


def priority(path: str) -> int:
    """lower reads first."""
    low = path.lower()
    for prefix, rank in PRIORITY_PREFIXES:
        if low.startswith(prefix) or f"/{prefix}" in low:
            return rank
    name = low.rsplit("/", 1)[-1]
    dot = name.rfind(".")
    suffix = name[dot:] if dot > 0 else ""
    if suffix in CODE_SUFFIXES:
        return 5
    return 9


def select_tree(paths: list[str], excludes: Excludes, budget: int = 200) -> tuple[list[str], dict]:
    """returns (selected, report). the report names what was skipped and why:
    excluded by pattern, or unread because the budget filled."""
    kept = sorted((p for p in paths if not excludes.is_excluded(p)), key=priority)
    skipped = [p for p in paths if excludes.is_excluded(p)]
    selected = kept[:budget]
    unread_budget = kept[budget:]
    return selected, {
        "selected": len(selected),
        "skipped_excluded": skipped,
        "unread_budget": unread_budget,
    }
