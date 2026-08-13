#!/usr/bin/env python3
"""Find unused imports in companion Python files (heuristic).

This script is conservative: it skips star imports and imports used in the
same file. It also performs a text search to catch string-based or annotation
uses.
"""
import ast
import json
import re
from pathlib import Path


def analyze_file(path: Path):
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    name = alias.asname
                else:
                    name = alias.name.split(".")[0]
                imports.append((node.lineno, node.col_offset, "import", alias.name, name, src.splitlines()[node.lineno-1]))
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            # skip star imports
            if any(alias.name == "*" for alias in node.names):
                continue
            for alias in node.names:
                asname = alias.asname or alias.name
                imports.append((node.lineno, node.col_offset, "from", node.module, asname, src.splitlines()[node.lineno-1]))

    used = set()

    # gather used names from AST (Name nodes)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)

    results = []

    for lineno, col, kind, modname, localname, line_text in imports:
        # skip future imports and typing-only pattern
        if modname in {"__future__"}:
            continue

        # simple heuristic: check whole-file text for occurrences beyond the import line
        pattern = re.compile(r"\\b% s\\b" % re.escape(localname))
        occurrences = [m for m in pattern.finditer(src)]
        occurrences_non_import = [m for m in occurrences if src.count("\n", 0, m.start()) + 1 != lineno]

        ast_used = localname in used

        if ast_used or occurrences_non_import:
            continue

        results.append({
            "file": str(path),
            "lineno": lineno,
            "kind": kind,
            "module": modname,
            "name": localname,
            "line": line_text.strip(),
        })

    return results


def main():
    base = Path(__file__).resolve().parent.parent / "companion"
    out = []
    for path in sorted(base.glob("*.py")):
        out.extend(analyze_file(path))

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
