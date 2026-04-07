# utils/output_formatter.py

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.rule import Rule
from typing import List, Dict

console = Console()


def print_header(filename: str):
    console.print()
    console.print(Rule("[bold blue]DARK GUARD AI — NLP Agent[/bold blue]", style="blue"))
    console.print(f"[dim]Analyzing:[/dim] [cyan]{filename}[/cyan]")
    console.print(Rule(style="blue"))
    console.print()


def print_agent_step(step: str, detail: str = ""):
    """Print what the agent is currently doing."""
    console.print(f"  [bold blue]→[/bold blue] {step}", end="")
    if detail:
        console.print(f" [dim]{detail}[/dim]", end="")
    console.print()


def print_no_patterns():
    console.print(Panel(
        "[bold green]✓ No dark patterns detected[/bold green]\n"
        "[dim]This page appears to be clean.[/dim]",
        border_style="green"
    ))


def print_detection_summary(detections: List[Dict], input_file: str):
    """Print the full detection report to terminal."""

    console.print()
    console.print(Rule("[bold]DETECTION REPORT[/bold]", style="red" if detections else "green"))
    console.print()

    if not detections:
        print_no_patterns()
        return

    # ── Summary Box ────────────────────────────────────────────────────────
    total = len(detections)
    high   = sum(1 for d in detections if d["confidence"] >= 0.80)
    medium = sum(1 for d in detections if 0.55 <= d["confidence"] < 0.80)
    low    = sum(1 for d in detections if d["confidence"] < 0.55)

    summary_text = (
        f"[bold red]{total} dark pattern(s) detected[/bold red]\n\n"
        f"[red]● High confidence (≥80%):[/red]   {high}\n"
        f"[yellow]● Medium confidence (55-79%):[/yellow] {medium}\n"
        f"[dim]● Low confidence (<55%):[/dim]    {low}"
    )
    console.print(Panel(summary_text, title="[bold]Summary[/bold]", border_style="red"))
    console.print()

    # ── Per-Pattern Detail ─────────────────────────────────────────────────
    for i, det in enumerate(detections, 1):
        confidence = det["confidence"]
        color = "red" if confidence >= 0.80 else "yellow" if confidence >= 0.55 else "dim"

        # Build evidence list
        evidence_lines = "\n".join(
            f"  [dim]•[/dim] [italic]\"{e}\"[/italic]"
            for e in det.get("evidence", [])[:4]
        )

        content = (
            f"[bold]Pattern ID:[/bold]  {det['pattern_id']}\n"
            f"[bold]Confidence:[/bold]  [{color}]{confidence:.0%}[/{color}]\n"
            f"[bold]Risk Level:[/bold]  [{color}]{det.get('risk_level', 'unknown').upper()}[/{color}]\n\n"
            f"[bold]What was found:[/bold]\n{evidence_lines}\n\n"
            f"[bold]Why this is a dark pattern:[/bold]\n  {det.get('explanation', '')}\n\n"
            f"[bold]Prevention:[/bold]\n  [green]{det.get('prevention', '')}[/green]"
        )

        console.print(Panel(
            content,
            title=f"[bold {color}]#{i} — {det['pattern_name']} ({det['pattern_id']})[/bold {color}]",
            border_style=color
        ))
        console.print()

    # ── Summary Table ──────────────────────────────────────────────────────
    table = Table(
        title="All Detections at a Glance",
        box=box.ROUNDED,
        border_style="blue",
        show_lines=True
    )
    table.add_column("#",            style="bold", width=3)
    table.add_column("Pattern ID",   style="bold yellow", width=8)
    table.add_column("Pattern Name", style="bold", width=25)
    table.add_column("Confidence",   justify="center", width=12)
    table.add_column("Risk",         justify="center", width=8)

    for i, det in enumerate(detections, 1):
        conf  = det["confidence"]
        color = "red" if conf >= 0.80 else "yellow" if conf >= 0.55 else "dim"
        table.add_row(
            str(i),
            det["pattern_id"],
            det["pattern_name"],
            f"[{color}]{conf:.0%}[/{color}]",
            f"[{color}]{det.get('risk_level', '?').upper()}[/{color}]",
        )

    console.print(table)
    console.print()


def save_report(detections: List[Dict], input_file: str, output_path: str):
    """Save detection report as plain text file."""
    import json
    from datetime import datetime

    report = {
        "analyzed_file":  input_file,
        "analyzed_at":    datetime.now().isoformat(),
        "total_detected": len(detections),
        "detections":     detections,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)