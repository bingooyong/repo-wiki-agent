from __future__ import annotations

import csv
from pathlib import Path

from repo_wiki.core.contracts import RepositorySnapshot
from repo_wiki.generator.io import ensure_dir, write_json


def build_graph_artifacts(root: Path, snapshot: RepositorySnapshot) -> dict:
    graph_dir = root / ".repo-wiki" / "graph"
    ensure_dir(graph_dir)

    module_names = [m.name for m in snapshot.modules]
    by_name = {m.name: m for m in snapshot.modules}

    nodes = {}
    downstream = {name: [] for name in module_names}
    for module in snapshot.modules:
        nodes[module.name] = {
            "path": module.path,
            "owner": module.owner,
            "interfaces": module.interfaces,
            "models": module.data_models,
            "upstream": sorted(module.depends_on),
            "downstream": [],
        }
        for dep in module.depends_on:
            if dep in downstream:
                downstream[dep].append(module.name)

    for name, deps in downstream.items():
        nodes[name]["downstream"] = sorted(set(deps))

    impact_cache = {}
    for name in module_names:
        depth2 = set()
        for d in nodes[name]["downstream"]:
            for d2 in nodes.get(d, {}).get("downstream", []):
                depth2.add(d2)
        impact_cache[name] = {
            "upstream": nodes[name]["upstream"],
            "downstream": nodes[name]["downstream"],
            "depth2": sorted(depth2),
            "interfaces": nodes[name]["interfaces"],
            "models": nodes[name]["models"],
        }

    edges = [
        {"type": "DEPENDS_ON", "from": m.name, "to": dep}
        for m in snapshot.modules
        for dep in m.depends_on
        if dep in by_name
    ] + [
        {"type": "EXPOSES", "from": m.name, "to": interface}
        for m in snapshot.modules
        for interface in m.interfaces
    ] + [
        {"type": "USES", "from": m.name, "to": model}
        for m in snapshot.modules
        for model in m.data_models
    ] + [
        {"type": "BELONGS_TO", "from": endpoint.path, "to": endpoint.module}
        for endpoint in snapshot.endpoints
    ] + [
        {"type": "BELONGS_TO", "from": model.name, "to": model.module}
        for model in snapshot.data_models
    ]

    graph_payload = {
        "modules": nodes,
        "edges": edges,
        "consistency": {
            "orphan_modules": sorted(
                [
                    name
                    for name, node in nodes.items()
                    if not node["upstream"] and not node["downstream"]
                ]
            ),
            "self_dependencies": sorted(
                [name for name, node in nodes.items() if name in set(node["upstream"])]
            ),
            "broken_dependencies": sorted(
                [
                    dep
                    for node in nodes.values()
                    for dep in node["upstream"]
                    if dep not in nodes
                ]
            ),
        },
    }

    write_json(graph_dir / "knowledge_graph.json", graph_payload)
    write_json(graph_dir / "impact_cache.json", impact_cache)

    with (graph_dir / "dep_matrix.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["module", *module_names])
        for src in module_names:
            row = [src]
            src_deps = set(nodes[src]["upstream"])
            for dst in module_names:
                row.append("DEPENDS_ON" if dst in src_deps else "")
            writer.writerow(row)

    return {
        "knowledge_graph": str(graph_dir / "knowledge_graph.json"),
        "impact_cache": str(graph_dir / "impact_cache.json"),
        "dep_matrix": str(graph_dir / "dep_matrix.csv"),
    }
