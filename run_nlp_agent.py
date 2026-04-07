# run_nlp_agent.py
# Entry point — run this from the terminal.
# Usage:
#   python run_nlp_agent.py inputs/sample_page.txt
#   python run_nlp_agent.py inputs/sample_page.txt --save

import asyncio
import sys
import os
import argparse
from datetime import datetime
from rich.console import Console

console = Console()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Dark Guard NLP Agent — Detects dark patterns in webpage text"
    )
    parser.add_argument(
        "input_file",
        help="Path to the text file containing webpage content"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save detection report as JSON to outputs/ folder"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress step-by-step agent activity, show only final results"
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    # ── Validate input file ────────────────────────────────────────────────
    if not os.path.exists(args.input_file):
        console.print(f"[red]Error: File not found: {args.input_file}[/red]")
        sys.exit(1)

    # ── Imports ────────────────────────────────────────────────────────────
    from utils.text_extractor import TextExtractor
    from utils.output_formatter import (
        print_header, print_detection_summary,
        print_agent_step, save_report, console
    )
    from agents.nlp_agent import run_nlp_agent

    # ── Load and clean input ───────────────────────────────────────────────
    print_header(args.input_file)

    extractor = TextExtractor()
    raw_text  = extractor.load_from_file(args.input_file)
    clean_text = extractor.clean(raw_text)

    print_agent_step("Loaded input file", f"{len(raw_text)} chars raw → {len(clean_text)} chars cleaned")
    console.print()

    # ── Run NLP Agent ──────────────────────────────────────────────────────
    start_time = datetime.now()

    result = await run_nlp_agent(
        text=clean_text,
        verbose=not args.quiet
    )

    elapsed = (datetime.now() - start_time).total_seconds()

    # ── Print results ──────────────────────────────────────────────────────
    console.print()
    print_detection_summary(result["detections"], args.input_file)

    # ── Show summary stats ─────────────────────────────────────────────────
    console.print(
        f"[dim]Analysis completed in {elapsed:.1f}s | "
        f"Detected {len(result['detections'])} pattern(s)[/dim]"
    )
    console.print()

    # ── Optionally save report ─────────────────────────────────────────────
    if args.save:
        os.makedirs("outputs", exist_ok=True)
        timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"outputs/report_{timestamp}.json"
        save_report(result["detections"], args.input_file, output_path)
        console.print(f"[green]✅ Report saved to:[/green] [cyan]{output_path}[/cyan]")
        console.print()


if __name__ == "__main__":
    asyncio.run(main())