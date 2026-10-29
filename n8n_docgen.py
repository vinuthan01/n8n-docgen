#!/usr/bin/env python3
"""n8n-docgen: turn n8n workflow JSON exports into readable Markdown docs.

Standard library only. Usage:
    python n8n_docgen.py workflow.json -o WORKFLOW.md
"""
import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path

__version__ = "0.1.0"

SECRET_KEY = re.compile(r"(api[_-]?key|token|secret|password|passwd|authorization|bearer)", re.I)
TRIGGER_NAMES = {"webhook", "start", "cron", "interval"}


def load_workflow(path):
    """Read an n8n workflow export and check it looks like one."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list) and len(data) == 1:
        data = data[0]
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), list):
        raise ValueError(f"{path}: not an n8n workflow export (no 'nodes' list)")
    return data


def short_type(node_type):
    return (node_type or "unknown").rsplit(".", 1)[-1]


def is_trigger(node):
    s = short_type(node.get("type")).lower()
    return s.endswith("trigger") or s in TRIGGER_NAMES


def build_edges(workflow):
    """Return a list of (source, target, output_index, connection_type)."""
    edges = []
    for src, outputs in (workflow.get("connections") or {}).items():
        for conn_type, branches in (outputs or {}).items():
            for idx, targets in enumerate(branches or []):
                for t in targets or []:
                    edges.append((src, t.get("node"), idx, conn_type))
    return edges


def ordered_nodes(workflow, edges):
    """Nodes in execution-ish order: walk from triggers, then leftovers."""
    nodes = {n.get("name"): n for n in workflow["nodes"]}
    seen, order = set(), []
    queue = deque(n["name"] for n in workflow["nodes"] if is_trigger(n))
    while queue:
        name = queue.popleft()
        if name in seen or name not in nodes:
            continue
        seen.add(name)
        order.append(nodes[name])
        queue.extend(dst for src, dst, _, _ in edges if src == name)
    order.extend(n for n in workflow["nodes"] if n.get("name") not in seen)
    return order


def find_hardcoded_secrets(params, path=""):
    """Yield dotted paths of secret-looking parameters holding literal values."""
    if isinstance(params, dict):
        for key, value in params.items():
            here = f"{path}.{key}" if path else str(key)
            if (SECRET_KEY.search(str(key)) and isinstance(value, str)
                    and value.strip() and not value.startswith("=")):
                yield here
            else:
                yield from find_hardcoded_secrets(value, here)
    elif isinstance(params, list):
        for i, value in enumerate(params):
            yield from find_hardcoded_secrets(value, f"{path}[{i}]")


def param_summary(node, limit=4, width=60):
    """A few top-level, non-secret scalar parameters, e.g. `method: POST`."""
    parts = []
    for key, value in (node.get("parameters") or {}).items():
        if SECRET_KEY.search(str(key)) or not isinstance(value, (str, int, float, bool)):
            continue
        text = str(value).replace("\n", " ")
        if len(text) > width:
            text = text[: width - 1] + "…"
        parts.append(f"`{key}: {text}`")
        if len(parts) == limit:
            break
    return ", ".join(parts)


def cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def mermaid(workflow, edges):
    ids = {n["name"]: f"n{i}" for i, n in enumerate(workflow["nodes"])}
    lines = ["flowchart LR"]
    for n in workflow["nodes"]:
        label = str(n["name"]).replace('"', "'")
        cls = ":::disabled" if n.get("disabled") else ""
        lines.append(f'    {ids[n["name"]]}["{label}"]{cls}')
    for src, dst, idx, conn_type in edges:
        if src in ids and dst in ids:
            label = conn_type if conn_type != "main" else (f"output {idx + 1}" if idx else "")
            arrow = f"-->|{label}|" if label else "-->"
            lines.append(f"    {ids[src]} {arrow} {ids[dst]}")
    lines.append("    classDef disabled stroke-dasharray: 5 5,color:#888")
    return "\n".join(lines)


def render(workflow):
    """Build the Markdown document for one workflow."""
    nodes = workflow["nodes"]
    edges = build_edges(workflow)
    order = ordered_nodes(workflow, edges)
    triggers = [n for n in nodes if is_trigger(n)]
    disabled = [n for n in nodes if n.get("disabled")]

    creds = sorted({
        f"{ctype} ({c.get('name', 'unnamed')})"
        for n in nodes for ctype, c in (n.get("credentials") or {}).items()
    })
    integrations = sorted({short_type(n.get("type")) for n in nodes if not is_trigger(n)})

    linked = {s for s, _, _, _ in edges} | {d for _, d, _, _ in edges}
    orphans = [n for n in nodes if len(nodes) > 1 and n["name"] not in linked]
    secrets = [(n["name"], p) for n in nodes for p in find_hardcoded_secrets(n.get("parameters"))]

    out = [f"# {workflow.get('name') or 'Untitled workflow'}", ""]
    out += ["> Generated by [n8n-docgen](https://github.com/vinuthan01/n8n-docgen). Do not edit by hand.", ""]
    out += ["## Overview", ""]
    out.append(f"- **Nodes:** {len(nodes)}" + (f" ({len(disabled)} disabled)" if disabled else ""))
    out.append("- **Triggers:** " + (", ".join(f"{n['name']} (`{short_type(n.get('type'))}`)" for n in triggers) or "none (run manually or from another workflow)"))
    out.append("- **Node types used:** " + (", ".join(f"`{i}`" for i in integrations) or "none"))
    out.append("- **Credentials:** " + (", ".join(creds) or "none"))
    if "active" in workflow:
        out.append(f"- **Active:** {'yes' if workflow['active'] else 'no'}")
    out += ["", "## Diagram", "", "```mermaid", mermaid(workflow, edges), "```", ""]

    out += ["## Steps", ""]
    for i, n in enumerate(order, 1):
        line = f"{i}. **{n['name']}** (`{short_type(n.get('type'))}`)"
        if n.get("disabled"):
            line += " *(disabled)*"
        out.append(line)
        if n.get("notes"):
            out.append(f"   - Note: {str(n['notes']).strip()}")
        summary = param_summary(n)
        if summary:
            out.append(f"   - Settings: {summary}")
        nexts = [f"{d}" + (f" (output {idx + 1})" if idx else "") for s, d, idx, _ in edges if s == n["name"]]
        if nexts:
            out.append("   - Goes to: " + ", ".join(nexts))
    out.append("")

    out += ["## Node reference", "", "| Node | Type | Disabled |", "| --- | --- | --- |"]
    for n in nodes:
        out.append(f"| {cell(n['name'])} | `{cell(short_type(n.get('type')))}` | {'yes' if n.get('disabled') else 'no'} |")
    out.append("")

    if orphans or disabled or secrets:
        out += ["## Warnings", ""]
        for n in orphans:
            out.append(f"- **{n['name']}** is not connected to anything.")
        for n in disabled:
            out.append(f"- **{n['name']}** is disabled and will not run.")
        for name, p in secrets:
            out.append(f"- **{name}** has a hardcoded value in `{p}`. Move it to an n8n credential.")
        out.append("")
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Turn n8n workflow JSON exports into Markdown docs.")
    parser.add_argument("files", nargs="+", help="one or more n8n workflow .json files")
    parser.add_argument("-o", "--output", help="write Markdown to this file instead of printing it")
    parser.add_argument("--version", action="version", version=f"n8n-docgen {__version__}")
    args = parser.parse_args(argv)

    docs = []
    for f in args.files:
        try:
            docs.append(render(load_workflow(f)))
        except (OSError, ValueError) as e:  # json.JSONDecodeError is a ValueError
            print(f"error: {e}", file=sys.stderr)
            return 1
    text = "\n---\n\n".join(docs)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
