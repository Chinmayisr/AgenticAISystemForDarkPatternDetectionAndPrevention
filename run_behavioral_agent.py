# run_behavioral_agent.py

import sys
import os
import json
import argparse
import subprocess
from datetime import datetime
from rich.console import Console

console = Console()


def _configure_utf8_output():
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


def parse_args():
    parser = argparse.ArgumentParser(
        description="Dark Guard Behavioral Agent — Detects Basket Sneaking, "
                    "Subscription Trap, SaaS Billing, and Nagging"
    )
    parser.add_argument("input_file", help="Path to behavioral JSON input file")
    parser.add_argument("--save",  action="store_true", help="Save JSON report to outputs/")
    parser.add_argument("--quiet", action="store_true", help="Suppress step-by-step output")
    return parser.parse_args()


def main():
    _configure_utf8_output()
    args = parse_args()

    if not os.path.exists(args.input_file):
        console.print(f"[red]Error: File not found: {args.input_file}[/red]")
        sys.exit(1)

    from utils.output_formatter import (
        print_behavioral_header,
        print_behavioral_detection_summary
    )
    try:
        from agents.behavioral_agent import run_behavioral_agent
    except ImportError:
        venv_python = os.path.join(os.path.dirname(__file__), "denv", "Scripts", "python.exe")
        current_python = os.path.abspath(sys.executable)

        if os.path.exists(venv_python) and os.path.abspath(venv_python) != current_python:
            console.print(
                "[yellow]Behavioral agent dependencies were not found in the current Python. "
                "Retrying with the local `denv` interpreter...[/yellow]"
            )
            raise SystemExit(
                subprocess.call([venv_python, __file__, *sys.argv[1:]])
            )

        console.print(
            "[red]Behavioral agent dependencies are missing for this interpreter.[/red]"
        )
        console.print(
            "[dim]Use `denv\\Scripts\\python run_behavioral_agent.py ...` "
            "or install requirements into the current Python environment.[/dim]"
        )
        raise

    print_behavioral_header(args.input_file)

    start_time = datetime.now()
    result     = run_behavioral_agent(args.input_file, verbose=not args.quiet)
    elapsed    = (datetime.now() - start_time).total_seconds()

    print_behavioral_detection_summary(result, args.input_file)

    console.print(
        f"[dim]Analysis completed in {elapsed:.1f}s | "
        f"Detected {len(result['detections'])} pattern(s)[/dim]"
    )
    console.print()

    if args.save:
        os.makedirs("outputs", exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"outputs/behavioral_report_{ts}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "analyzed_file":   args.input_file,
                "analyzed_at":     datetime.now().isoformat(),
                "total_detected":  len(result["detections"]),
                "session_summary": result.get("session_summary", ""),
                "detections":      result["detections"],
            }, f, indent=2, ensure_ascii=False)
        console.print(f"[green]✅ Report saved:[/green] [cyan]{path}[/cyan]")


if __name__ == "__main__":
    main()
