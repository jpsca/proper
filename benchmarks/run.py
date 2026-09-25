"""Run the Proper server benchmarks.

    uv run python -m benchmarks.run [--duration 10s] [--connections 64] [--workers 4]
                                    [--only uvicorn,granian-rsgi] [--ft-python .venv-ft/bin/python]

For each Python (GIL and free-threaded) it starts Granian, waits for it,
warms it up, runs bombardier against each endpoint, samples the RSS of the whole
process tree, stops the server and prints a Markdown table. Results are also
written as JSON to `benchmarks/results/`.
"""
import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).parent
ROOT = HERE.parent
RESULTS = HERE / "results"
PORT = 8123
ENDPOINTS = ("/plaintext", "/json", "/fortunes")
BOMBARDIER = shutil.which("bombardier") or str(Path.home() / "go/bin/bombardier")


@dataclass
class Config:
    name: str
    argv: list[str]
    python: str = sys.executable
    env: dict = field(default_factory=dict)


def configs(workers: int, ft_python: str | None) -> list[Config]:
    def granian(name, python=sys.executable):
        return Config(name, [
            python, "-m", "granian", "benchmarks.rsgi:app",
            "--interface", "rsgi",
            "--host", "127.0.0.1", "--port", str(PORT),
            "--workers", str(workers), "--log-level", "warning",
            "--no-access-log",
        ], python=python)

    out = [granian("granian rsgi")]
    if ft_python:
        out.append(granian("granian rsgi 3.14t", python=ft_python))
    return out


def wait_port(port: int, proc: subprocess.Popen, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early with {proc.returncode}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("server did not start")


def tree_rss_kb(pid: int) -> int:
    """RSS in kB of `pid` and all its descendants."""
    out = subprocess.run(
        ["ps", "-e", "-o", "pid=,ppid=,rss="], capture_output=True, text=True
    ).stdout
    children: dict[int, list[int]] = {}
    rss: dict[int, int] = {}
    for line in out.splitlines():
        p, pp, r = line.split()
        children.setdefault(int(pp), []).append(int(p))
        rss[int(p)] = int(r)
    total, stack = 0, [pid]
    while stack:
        p = stack.pop()
        total += rss.get(p, 0)
        stack.extend(children.get(p, []))
    return total


def bombard(url: str, duration: str, connections: int) -> dict:
    out = subprocess.run(
        [BOMBARDIER, "-c", str(connections), "-d", duration, "-l",
         "--print", "r", "--format", "json", url],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(out)["result"]
    lat = data["latency"]
    return {
        "rps": data["rps"]["mean"],
        "p50_ms": lat["percentiles"]["50"] / 1000,
        "p99_ms": lat["percentiles"]["99"] / 1000,
        "errors": data["others"] + sum(e["count"] for e in data.get("errors", [])),
        "non2xx": data["req1xx"] + data["req3xx"] + data["req4xx"] + data["req5xx"],
    }


def run_config(cfg: Config, duration: str, connections: int) -> dict:
    env = {**os.environ, "PYTHONPATH": str(ROOT), **cfg.env}
    proc = subprocess.Popen(
        cfg.argv, cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True,
    )
    result: dict = {"name": cfg.name, "endpoints": {}}
    try:
        wait_port(PORT, proc)
        time.sleep(1.0)
        base = f"http://127.0.0.1:{PORT}"
        for ep in ENDPOINTS:
            bombard(base + ep, "2s", connections)  # warm-up
            result["endpoints"][ep] = bombard(base + ep, duration, connections)
            print(f"  {cfg.name:28} {ep:11} {result['endpoints'][ep]['rps']:>10.0f} rps", flush=True)
        result["rss_mb"] = tree_rss_kb(proc.pid) / 1024
    finally:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
        if "Traceback" in err:
            print(err[-2000:], file=sys.stderr)
    return result


def markdown(results: list[dict], meta: dict) -> str:
    lines = [
        f"Workers: {meta['workers']}, connections: {meta['connections']}, "
        f"duration: {meta['duration']} per endpoint, host: {meta['host']}",
        "",
        "| server | plaintext rps | json rps | fortunes rps | fortunes p50 ms | fortunes p99 ms | RSS MB |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        e = r["endpoints"]
        f = e["/fortunes"]
        lines.append(
            f"| {r['name']} | {e['/plaintext']['rps']:,.0f} | {e['/json']['rps']:,.0f} "
            f"| {f['rps']:,.0f} | {f['p50_ms']:.2f} | {f['p99_ms']:.2f} | {r['rss_mb']:.0f} |"
        )
    bad = [(r["name"], ep, v["non2xx"]) for r in results for ep, v in r["endpoints"].items() if v["non2xx"]]
    if bad:
        lines += ["", "Non-2xx responses:"] + [f"- {n} {ep}: {c}" for n, ep, c in bad]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", default="10s")
    ap.add_argument("--connections", type=int, default=64)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", default="", help="comma-separated substrings of config names")
    ap.add_argument("--ft-python", default=str(ROOT / ".venv-ft/bin/python"))
    args = ap.parse_args()

    ft = args.ft_python if Path(args.ft_python).exists() else None
    cfgs = configs(args.workers, ft)
    if args.only:
        keys = [k.strip() for k in args.only.split(",")]
        cfgs = [c for c in cfgs if any(k in c.name for k in keys)]

    meta = {
        "workers": args.workers, "connections": args.connections,
        "duration": args.duration, "host": os.uname().nodename,
        "cpus": os.cpu_count(), "when": datetime.now(timezone.utc).isoformat(),
    }
    results = []
    for cfg in cfgs:
        print(f"== {cfg.name}", flush=True)
        results.append(run_config(cfg, args.duration, args.connections))

    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (RESULTS / f"{stamp}.json").write_text(json.dumps({"meta": meta, "results": results}, indent=2))
    report = markdown(results, meta)
    (RESULTS / f"{stamp}.md").write_text(report)
    print("\n" + report)


if __name__ == "__main__":
    main()
