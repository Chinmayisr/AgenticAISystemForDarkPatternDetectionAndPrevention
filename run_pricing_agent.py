# run_pricing_agent.py
# Usage:
#   python run_pricing_agent.py inputs/pricing/swiggy_order.json
#   python run_pricing_agent.py inputs/pricing/swiggy_order.json --save
#   python run_pricing_agent.py inputs/pricing/swiggy_order.json --quiet

import sys
import os
import json
import argparse
import subprocess
from datetime import datetime
from rich.console import Console

console = Console()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Dark Guard Pricing Agent — Detects Bait & Switch and Drip Pricing"
    )
    parser.add_argument(
        "input_file",
        help="Path to JSON file with purchase funnel price data"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save detection report as JSON to outputs/ folder"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Show only final results, suppress step-by-step activity"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not os.path.exists(args.input_file):
        console.print(f"[red]Error: File not found: {args.input_file}[/red]")
        sys.exit(1)

    from utils.output_formatter import (
        print_pricing_header,
        print_pricing_detection_summary
    )
    try:
        from agents.pricing_agent import run_pricing_agent
    except ImportError:
        venv_python = os.path.join(os.path.dirname(__file__), "denv", "Scripts", "python.exe")
        current_python = os.path.abspath(sys.executable)

        if os.path.exists(venv_python) and os.path.abspath(venv_python) != current_python:
            console.print(
                "[yellow]Pricing agent dependencies were not found in the current Python. "
                "Retrying with the local `denv` interpreter...[/yellow]"
            )
            raise SystemExit(
                subprocess.call([venv_python, __file__, *sys.argv[1:]])
            )

        console.print(
            "[red]Pricing agent dependencies are missing for this interpreter.[/red]"
        )
        console.print(
            "[dim]Use `denv\\Scripts\\python run_pricing_agent.py ...` "
            "or install requirements into the current Python environment.[/dim]"
        )
        raise

    print_pricing_header(args.input_file)

    start_time = datetime.now()

    result = run_pricing_agent(
        input_file=args.input_file,
        verbose=not args.quiet
    )

    elapsed = (datetime.now() - start_time).total_seconds()

    print_pricing_detection_summary(result, args.input_file)

    console.print(
        f"[dim]Analysis completed in {elapsed:.1f}s | "
        f"Detected {len(result['detections'])} pattern(s)[/dim]"
    )
    console.print()

    if args.save:
        os.makedirs("outputs", exist_ok=True)
        timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"outputs/pricing_report_{timestamp}.json"
        report = {
            "analyzed_file":              args.input_file,
            "analyzed_at":                datetime.now().isoformat(),
            "total_detected":             len(result["detections"]),
            "funnel_summary":             result.get("funnel_summary", ""),
            "total_unexplained_increase": result.get("total_unexplained_increase", 0.0),
            "detections":                 result["detections"],
            "analysis_context": {
                k: v for k, v in result.get("analysis_context", {}).items()
                if k != "stage_summaries"
            }
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        console.print(f"[green]✅ Report saved:[/green] [cyan]{output_path}[/cyan]")


if __name__ == "__main__":
    main()
