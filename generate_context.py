#!/usr/bin/env python3
"""
Gera arquivos CONTEXT.md por pacote a partir da AST do código-fonte.

Uso:
    python generate_context.py --src src --out context

Para cada subpasta dentro de --src, gera um context/<pasta>.md com:
- docstring do módulo
- classes, métodos (assinatura + 1ª linha da docstring)
- funções soltas
- imports locais (depende de / usado por)
"""

import argparse
import ast
from collections import defaultdict
from pathlib import Path


def get_signature(node) -> str:
    args = [a.arg for a in node.args.args]
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")
    for a in node.args.kwonlyargs:
        args.append(a.arg)
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({', '.join(args)})"


def get_docstring_summary(node) -> str:
    doc = ast.get_docstring(node)
    if not doc:
        return ""
    return doc.strip().split("\n")[0]


def extract_imports(tree: ast.Module, module_prefix: str, current_module: str) -> list:
    imports = []
    package_parts = current_module.split(".")[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                base = package_parts[: len(package_parts) - (node.level - 1)]
                resolved = base + (node.module.split(".") if node.module else [])
                imports.append(".".join(resolved))
            elif node.module and node.module.startswith(module_prefix):
                imports.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(module_prefix):
                    imports.append(alias.name)
    return imports


def parse_file(path: Path, module_prefix: str) -> dict:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    current_module = path_to_module(path, module_prefix)
    info = {
        "path": path,
        "docstring": get_docstring_summary(tree),
        "classes": [],
        "functions": [],
        "imports": extract_imports(tree, module_prefix, current_module),
    }

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) for b in node.bases]
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(
                        {
                            "signature": get_signature(item),
                            "doc": get_docstring_summary(item),
                        }
                    )
            info["classes"].append(
                {
                    "name": node.name,
                    "bases": bases,
                    "doc": get_docstring_summary(node),
                    "methods": methods,
                }
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info["functions"].append(
                {
                    "signature": get_signature(node),
                    "doc": get_docstring_summary(node),
                }
            )

    return info


def path_to_module(path: Path, module_prefix: str) -> str:
    parts = list(path.with_suffix("").parts)
    if module_prefix in parts:
        idx = parts.index(module_prefix)
        parts = parts[idx:]
    return ".".join(parts)


def build_used_by_map(files_info: list, module_prefix: str) -> dict:
    used_by = defaultdict(list)
    modules = {info["path"]: path_to_module(info["path"], module_prefix) for info in files_info}
    for info in files_info:
        importer = modules[info["path"]]
        for imp in info["imports"]:
            for other_path, other_module in modules.items():
                if other_path == info["path"]:
                    continue
                if imp == other_module or imp.startswith(other_module + "."):
                    used_by[other_module].append(importer)
    return used_by


def render_file_section(info: dict, module_name: str, used_by_map: dict) -> str:
    lines = [f"### `{info['path'].name}`"]
    if info["docstring"]:
        lines.append(f"> {info['docstring']}")
    lines.append("")

    used_by = sorted(set(used_by_map.get(module_name, [])))
    if used_by:
        lines.append(f"**Usado por:** {', '.join(f'`{u}`' for u in used_by)}")
        lines.append("")

    if info["imports"]:
        lines.append(f"**Depende de:** {', '.join(f'`{i}`' for i in sorted(set(info['imports'])))}")
        lines.append("")

    for cls in info["classes"]:
        bases = f"({', '.join(cls['bases'])})" if cls["bases"] else ""
        lines.append(f"**class `{cls['name']}{bases}`**")
        if cls["doc"]:
            lines.append(f"  {cls['doc']}")
        for m in cls["methods"]:
            doc = f" — {m['doc']}" if m["doc"] else " — ⚠️ *(sem docstring)*"
            lines.append(f"- `{m['signature']}`{doc}")
        lines.append("")

    for fn in info["functions"]:
        doc = f" — {fn['doc']}" if fn["doc"] else " — ⚠️ *(sem docstring)*"
        lines.append(f"- `{fn['signature']}`{doc}")

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default="src", help="Diretório raiz do código-fonte")
    parser.add_argument("--out", default="context", help="Diretório de saída dos .md")
    parser.add_argument("--prefix", default="src", help="Prefixo do módulo raiz (ex: 'src')")
    args = parser.parse_args()

    src_root = Path(args.src)
    out_root = Path(args.out)
    out_root.mkdir(exist_ok=True, parents=True)

    py_files = sorted(src_root.rglob("*.py"))
    files_info = [parse_file(p, args.prefix) for p in py_files]
    used_by_map = build_used_by_map(files_info, args.prefix)

    by_package = defaultdict(list)
    for info in files_info:
        package = info["path"].parent.name
        by_package[package].append(info)

    for package, infos in sorted(by_package.items()):
        out_path = out_root / f"{package}.md"
        sections = [f"# Contexto: `{package}/`\n"]
        for info in sorted(infos, key=lambda i: i["path"].name):
            module_name = path_to_module(info["path"], args.prefix)
            sections.append(render_file_section(info, module_name, used_by_map))
        out_path.write_text("\n".join(sections), encoding="utf-8")
        print(f"Gerado: {out_path}")


if __name__ == "__main__":
    main()
