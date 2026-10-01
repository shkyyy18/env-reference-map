"""Deliberately narrow AST inventory, not dataflow analysis."""

import ast
import os
from pathlib import Path
from .common import text, load_json

SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}


def references(source, label):
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise ValueError("Python input cannot be parsed") from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > 200000:
        raise ValueError("AST too large")
    os_names, env_names, get_names = set(), set(), set()
    for n in nodes:
        if isinstance(n, ast.Import):
            os_names.update(a.asname or a.name for a in n.names if a.name == "os")
        if isinstance(n, ast.ImportFrom) and n.module == "os" and n.level == 0:
            for a in n.names:
                if a.name == "environ":
                    env_names.add(a.asname or a.name)
                if a.name == "getenv":
                    get_names.add(a.asname or a.name)

    def environ(n):
        return (isinstance(n, ast.Name) and n.id in env_names) or (
            isinstance(n, ast.Attribute)
            and n.attr == "environ"
            and isinstance(n.value, ast.Name)
            and n.value.id in os_names
        )

    found, unknown = [], []
    for n in nodes:
        arg = None
        matched = False
        access = "read"
        if isinstance(n, ast.Call):
            f = n.func
            matched = (isinstance(f, ast.Name) and f.id in get_names) or (
                isinstance(f, ast.Attribute)
                and (
                    (
                        f.attr == "getenv"
                        and isinstance(f.value, ast.Name)
                        and f.value.id in os_names
                    )
                    or (f.attr in {"get", "setdefault", "pop"} and environ(f.value))
                )
            )
            if matched:
                arg = (
                    n.args[0]
                    if n.args
                    else next((k.value for k in n.keywords if k.arg == "key"), None)
                )
                if isinstance(f, ast.Attribute) and f.attr in {"setdefault", "pop"}:
                    access = "read/write"
        elif isinstance(n, ast.Subscript) and environ(n.value):
            matched, arg = True, n.slice
            access = "write" if isinstance(n.ctx, (ast.Store, ast.Del)) else "read"
        if matched:
            item = {"file": label, "line": n.lineno, "access": access}
            if (
                isinstance(arg, ast.Constant)
                and isinstance(arg.value, str)
                and arg.value
            ):
                found.append({**item, "name": arg.value})
            else:
                unknown.append(
                    {
                        **item,
                        "reason": "nonliteral or missing key; expression not exported",
                    }
                )
    return found, unknown


def inspect(root, declared):
    base = Path(root)
    if base.is_symlink() or not base.is_dir():
        raise ValueError("Regular source directory required")
    if (
        not isinstance(declared, list)
        or any(not isinstance(k, str) or not k for k in declared)
        or len(declared) != len(set(declared))
    ):
        raise ValueError("Declaration must be a unique JSON string list")
    refs, unknown, skipped = [], [], []
    files = total = 0
    for folder, dirs, names in os.walk(base, followlinks=False):
        dirs[:] = sorted(
            d for d in dirs if d not in SKIP and not (Path(folder) / d).is_symlink()
        )
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            p = Path(folder) / name
            label = p.relative_to(base).as_posix()
            if p.is_symlink():
                skipped.append({"file": label, "reason": "symlink"})
                continue
            source = text(p)
            total += len(source.encode("utf-8"))
            files += 1
            if files > 2000 or total > 16 * 1024 * 1024:
                raise ValueError("Project scan limit")
            found, unresolved = references(source, label)
            refs.extend(found)
            unknown.extend(unresolved)
    observed = {x["name"] for x in refs}
    missing = [{"name": name} for name in sorted(observed - set(declared))]
    unused = [{"name": name} for name in sorted(set(declared) - observed)]
    return {
        "files_scanned": files,
        "references": refs,
        "unresolved": unknown,
        "not_declared": missing,
        "declared_not_observed": unused,
        "skipped_files": skipped,
        "finding_count": len(missing) + len(unknown) + len(skipped),
        "boundary": "No dataflow or scope resolution. Declared-not-observed is not proof unused. No .env values loaded. Findings count missing names + unresolved uses + skipped symlink files.",
    }


def configure(parser):
    parser.add_argument("root", nargs="?")
    parser.add_argument("--keys", help="JSON array of names ONLY, not an env file")


def run(args):
    if not args.root or not args.keys:
        raise ValueError("root and keys required")
    return inspect(args.root, load_json(text(args.keys)))


def demo():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "synthetic.py").write_text(
            'import os\nmode = os.getenv("APP_MODE")\ncache = os.environ["CACHE_URL"]\nkey = "DYNAMIC"\nother = os.getenv(key)\n',
            encoding="utf-8",
        )
        return inspect(tmp, ["APP_MODE", "LEGACY_FLAG"])
