"""Validate notebooks, or execute copies using this Python interpreter.

The old generator with fabricated KPIs has been retired. Source notebooks,
datasets and existing evidence are never overwritten by this command.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run all cells and save separate executed copies")
    parser.add_argument("--timeout", type=int, default=300, help="Maximum seconds per cell")
    args = parser.parse_args()
    import nbformat

    sources = sorted((ROOT / "notebooks").glob("[0-9][0-9]_*.ipynb"))
    if not sources:
        raise FileNotFoundError("No source notebooks found")
    notebooks = []
    for path in sources:
        notebook = nbformat.read(path, as_version=4)
        nbformat.validate(notebook)
        notebooks.append((path, notebook))
        print(f"VALID: {path.name}", flush=True)
    if not args.execute:
        print("Validation only. Add --execute to run every cell.")
        return

    from nbclient import NotebookClient
    from jupyter_client import KernelManager
    from jupyter_client.kernelspec import KernelSpec

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output = ROOT / "data/notebook_runs" / stamp
    output.mkdir(parents=True, exist_ok=False)
    summary = {"started_at": stamp, "python": sys.executable, "notebooks": [], "status": "running"}
    summary_path = output / "execution.json"
    try:
        for path, notebook in notebooks:
            started = time.perf_counter()
            # An explicit kernel spec avoids silently using a global Python/kernel.
            manager = KernelManager()
            manager._kernel_spec = KernelSpec(
                argv=[sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
                display_name="Project Python", language="python",
            )
            client = NotebookClient(notebook, km=manager, timeout=args.timeout, startup_timeout=45,
                                    resources={"metadata": {"path": str(ROOT / "notebooks")}},
                                    allow_errors=False)
            status = "failed"
            try:
                print(f"RUN: {path.name}", flush=True)
                with client.setup_kernel(cleanup_kc=True):
                    client.execute()
                status = "passed"
            finally:
                nbformat.write(notebook, output / path.name)
                summary["notebooks"].append({
                    "file": path.name, "status": status,
                    "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "elapsed_s": round(time.perf_counter() - started, 3),
                    "executed_cells": sum(c.cell_type == "code" and c.execution_count is not None for c in notebook.cells),
                })
                summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(f"PASS: {path.name}", flush=True)
        summary["status"] = "passed"
    except Exception:
        summary["status"] = "failed"
        raise
    finally:
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"EVIDENCE: {output}", flush=True)


if __name__ == "__main__":
    main()
