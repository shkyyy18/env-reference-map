# Literal environment references / 环境变量引用

Create a values-free `keys.json` using valid JSON double quotes:

```json
["APP_MODE", "CACHE_URL"]
```

```sh
env-reference-map src --keys keys.json --html report.html --json report.json
```

Only `.py` files, simple `import os` aliases and `from os import environ/getenv` aliases.
Recognizes getenv, environ subscript, get, setdefault and pop. Direct writes are labelled.
No source execution; defaults are not exported. Literal reference names and source-relative paths
are exported. Dynamic key expressions are unresolved, not interpreted or shown. No .env is opened.

No scope/dataflow resolution: rebinding and shadowing can mislead the static inventory. Declared
but not observed does not prove a variable unused. Wrappers and dynamic imports may be missed.
Max 8 MiB/file, 16 MiB project text, 2,000 Python files, 200,000 AST nodes/file. Common dependency
folders and symlink directories skipped; symlink Python files listed as skipped. Invalid Python
rejects the entire analysis. Findings = undeclared literal names + unresolved uses + skipped files.

只提供键名清单，不要提供真实 .env。该工具不是完整静态分析器，也不是凭据检测器。
