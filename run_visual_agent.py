# run_visual_agent.py
# Usage:
#   python run_visual_agent.py inputs/screenshot.png
#   python run_visual_agent.py inputs/screenshot.png --save
#   python run_visual_agent.py inputs/screenshot.png --quiet

import sys
import os
import json
import argparse
from datetime import datetime
from rich.console import Console

console = Console()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Dark Guard Visual Agent — Detects visual dark patterns in screenshots"
    )
    parser.add_argument(
        "image_file",
        help="Path to screenshot image (.png, .jpg, .webp)"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save detection report as JSON to outputs/ folder"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Show only final results, not step-by-step agent activity"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not os.path.exists(args.image_file):
        console.print(f"[red]Error: File not found: {args.image_file}[/red]")
        sys.exit(1)

    from utils.output_formatter import (
        print_visual_header,
        print_visual_detection_summary
    )
    from agents.visual_agent import run_visual_agent

    print_visual_header(args.image_file)

    start_time = datetime.now()

    result = run_visual_agent(
        image_path=args.image_file,
        verbose=not args.quiet
    )

    elapsed = (datetime.now() - start_time).total_seconds()

    print_visual_detection_summary(result, args.image_file)

    console.print(
        f"[dim]Analysis completed in {elapsed:.1f}s | "
        f"Detected {len(result['detections'])} pattern(s)[/dim]"
    )
    console.print()

    if args.save:
        os.makedirs("outputs", exist_ok=True)
        timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"outputs/visual_report_{timestamp}.json"
        report = {
            "analyzed_file":     args.image_file,
            "analyzed_at":       datetime.now().isoformat(),
            "total_detected":    len(result["detections"]),
            "image_description": result.get("image_description", ""),
            "summary":           result.get("summary", ""),
            "detections":        result["detections"],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        console.print(f"[green]✅ Report saved:[/green] [cyan]{output_path}[/cyan]")


if __name__ == "__main__":
    main()