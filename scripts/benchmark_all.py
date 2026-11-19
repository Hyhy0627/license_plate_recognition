"""One command for regression, browser workflows, static checks and optional real AI timings."""
import argparse
import csv
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-ui", action="store_true")
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--video", type=Path)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=900, help="Maximum seconds per subprocess")
    args = parser.parse_args()
    if (args.image or args.video) and not args.real:
        parser.error("--image/--video require --real")
    if args.iterations < 1 or args.timeout < 1:
        parser.error("iterations and timeout must be positive")
    out = ROOT / "data/benchmarks" / datetime.now(timezone.utc).strftime("system_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True)
    npm = "npm.cmd" if os.name == "nt" else "npm"
    steps = [("python", [sys.executable, "-m", "pytest", "tests", "-q", f"--junitxml={out / 'python.xml'}"], ROOT),
             ("typescript", [npm, "exec", "--", "tsc", "--noEmit"], ROOT / "frontend"),
             ("eslint", [npm, "run", "lint"], ROOT / "frontend")]
    if not args.skip_ui:
        steps.append(("browser", [npm, "test"], ROOT / "benchmark"))
    if args.real:
        command = [sys.executable, "scripts/benchmark_user_workflows.py", "--output", str(out / "real"), "--iterations", str(args.iterations)]
        for name in ("image", "video"):
            if getattr(args, name):
                command += [f"--{name}", str(getattr(args, name).resolve())]
        steps.append(("real_models", command, ROOT))
    results = []
    for name, command, cwd in steps:
        print(f"Running {name}...", flush=True)
        started = time.perf_counter()
        env = {**os.environ, "BENCHMARK_OUTPUT": str(out), "PYTHONUTF8": "1"}
        log = out / f"{name}.log"
        # Use an argument list and no shell. npm.cmd needs the Windows command processor.
        try:
            with log.open("w", encoding="utf-8") as stream:
                completed = subprocess.run(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=args.timeout)
            code = completed.returncode
        except (OSError, subprocess.TimeoutExpired) as error:
            with log.open("a", encoding="utf-8") as stream:
                stream.write(str(error))
            code = -1
        results.append({"step": name, "passed": code == 0, "exit_code": code,
                        "seconds": round(time.perf_counter() - started, 3), "log": log.name})
        print(f"{name}: {'PASS' if code == 0 else 'FAIL'}", flush=True)
    cases = []
    if (out / "python.xml").exists():
        for case in ET.parse(out / "python.xml").iter("testcase"):
            status = "failed" if case.find("failure") is not None or case.find("error") is not None else "skipped" if case.find("skipped") is not None else "passed"
            cases.append({"suite": case.get("classname"), "name": case.get("name"), "status": status, "seconds": float(case.get("time", 0))})
    report = {"passed": all(step["passed"] for step in results), "python": sys.version,
              "platform": platform.platform(), "steps": results, "python_cases": cases,
              "ui": "skipped by request" if args.skip_ui else "mocked API; real browser interactions",
              "real_models": "enabled" if args.real else "not run", "accuracy": "See labeled offline benchmark; not inferred from workflow success"}
    report["counts"] = {status: sum(c["status"] == status for c in cases) for status in ("passed", "failed", "skipped")}
    if (out / "browser.json").exists():
        browser = json.loads((out / "browser.json").read_text(encoding="utf-8"))
        report["browser_stats"] = browser.get("stats", {})
    real = {}
    if (out / "real/real_models.json").exists():
        real = json.loads((out / "real/real_models.json").read_text(encoding="utf-8"))
        report["real_measurements"] = real
    (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "python_cases.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["suite", "name", "status", "seconds"])
        writer.writeheader()
        writer.writerows(cases)
    rows = "".join(f"<tr><td>{html.escape(step['step'])}</td><td>{'PASS' if step['passed'] else 'FAIL'}</td><td>{step['seconds']}</td><td><a href='{step['log']}'>log</a></td></tr>" for step in results)
    case_rows = "".join(f"<tr><td>{html.escape(str(c['suite']))}</td><td>{html.escape(str(c['name']))}</td><td>{c['status']}</td><td>{c['seconds']}</td></tr>" for c in cases)
    timing_rows = "".join(f"<tr><td>{html.escape(name)}</td><td>{s['n']}</td><td>{s['mean_ms']:.1f}</td><td>{s['p50_ms']:.1f}</td><td>{s['p95_ms']:.1f}</td><td>{s['max_ms']:.1f}</td></tr>" for name, s in real.get("timings", {}).items())
    document = f"""<!doctype html><meta charset='utf-8'><title>PlateSight benchmark</title>
<style>body{{font:15px system-ui;max-width:1200px;margin:32px auto;padding:0 20px}}table{{border-collapse:collapse;width:100%;margin:20px 0}}td,th{{padding:8px;border:1px solid #ccd;text-align:left}}a{{color:#087d93}}</style>
<h1>PlateSight: {'PASS' if report['passed'] else 'FAIL'}</h1><p>UI: {html.escape(report['ui'])}. Real AI: {report['real_models']}.</p>
<p>Thời gian pytest/browser gồm thiết lập và chờ UI; không đại diện tốc độ model. Ca bị bỏ qua không được tính là đạt.</p>
<table><tr><th>Nhóm</th><th>Kết quả</th><th>Giây</th><th>Bằng chứng</th></tr>{rows}</table>
<p><a href='summary.json'>JSON</a> · <a href='python_cases.csv'>CSV</a> · <a href='browser/index.html'>Browser report</a> · <a href='real/real_models.json'>Real model timings (nếu bật)</a></p>
<h2>Thời gian model/API thật</h2><table><tr><th>Thao tác</th><th>N</th><th>Mean ms</th><th>P50 ms</th><th>P95 ms</th><th>Max ms</th></tr>{timing_rows}</table>
<h2>Python ({len(cases)} ca)</h2><table><tr><th>Suite</th><th>Case</th><th>Status</th><th>Giây</th></tr>{case_rows}</table>"""
    (out / "report.html").write_text(document, encoding="utf-8")
    print(f"Report: {out / 'report.html'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
