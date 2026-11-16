from pathlib import Path

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


def resolve(root, url_path):
    root = Path(root).resolve()
    relative = "index.html" if url_path.split("?", 1)[0] == "/" else url_path.split("?", 1)[0].lstrip("/")
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise PermissionError(url_path)
    if not candidate.is_file():
        raise FileNotFoundError(url_path)
    return candidate


def read_asset(root, url_path):
    path = resolve(root, url_path)
    content_type = CONTENT_TYPES.get(path.suffix, "application/octet-stream")
    return path.read_bytes(), content_type