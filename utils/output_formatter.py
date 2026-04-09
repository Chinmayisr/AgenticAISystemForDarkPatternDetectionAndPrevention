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

# Append these functions to utils/output_formatter.py

def print_visual_header(image_path: str):
    console.print()
    console.print(Rule("[bold blue]DARK GUARD AI — Visual Agent[/bold blue]", style="blue"))
    console.print(f"[dim]Analyzing image:[/dim] [cyan]{image_path}[/cyan]")
    console.print(Rule(style="blue"))
    console.print()


def print_visual_detection_summary(result: dict, image_path: str):
    """Print visual agent detection results."""
    detections = result.get("detections", [])
    img_desc   = result.get("image_description", "")
    summary    = result.get("summary", "")

    console.print()
    console.print(Rule("[bold]VISUAL DETECTION REPORT[/bold]",
                       style="red" if detections else "green"))
    console.print()

    # Image description box
    if img_desc:
        console.print(Panel(
            f"[dim]{img_desc}[/dim]",
            title="[bold]Screenshot Description[/bold]",
            border_style="blue"
        ))
        console.print()

    error = result.get("error")
    if error:
        console.print(Panel(
            f"[bold red]⚠️ Visual agent error:[/bold red]\n{error}",
            title="[bold]Visual Agent Error[/bold]",
            border_style="red"
        ))
        console.print()
        return

    if not detections:
        console.print(Panel(
            "[bold green]✓ No visual dark patterns detected[/bold green]\n"
            "[dim]This screenshot appears to be clean.[/dim]",
            border_style="green"
        ))
        return

    # Summary panel
    total  = len(detections)
    high   = sum(1 for d in detections if d.get("confidence", 0) >= 0.80)
    medium = sum(1 for d in detections if 0.55 <= d.get("confidence", 0) < 0.80)
    low    = sum(1 for d in detections if d.get("confidence", 0) < 0.55)

    console.print(Panel(
        f"[bold red]{total} visual dark pattern(s) detected[/bold red]\n\n"
        f"[red]● High (≥80%):[/red]    {high}\n"
        f"[yellow]● Medium (55-79%):[/yellow] {medium}\n"
        f"[dim]● Low (<55%):[/dim]     {low}",
        title="[bold]Summary[/bold]",
        border_style="red"
    ))
    console.print()

    # Per-detection panels
    for i, det in enumerate(detections, 1):
        confidence = det.get("confidence", 0)
        color      = "red" if confidence >= 0.80 else "yellow" if confidence >= 0.55 else "dim"

        # Build visual evidence section
        evidence_items = det.get("visual_evidence", [])
        evidence_text  = ""
        for ev in evidence_items[:4]:
            element     = ev.get("element", "")
            observation = ev.get("observation", "")
            location    = ev.get("location", "")
            evidence_text += (
                f"  [dim]•[/dim] [bold]{element}[/bold]"
                f"{' (' + location + ')' if location else ''}\n"
                f"    [italic]{observation}[/italic]\n"
            )

        content = (
            f"[bold]Pattern ID:[/bold]   {det.get('pattern_id')}\n"
            f"[bold]Confidence:[/bold]   [{color}]{confidence:.0%}[/{color}]\n"
            f"[bold]Risk Level:[/bold]   [{color}]{det.get('risk_level', '?').upper()}[/{color}]\n\n"
            f"[bold]Visual Evidence Observed:[/bold]\n{evidence_text}\n"
            f"[bold]Why this is a dark pattern:[/bold]\n  {det.get('explanation', '')}\n\n"
            f"[bold]What you should do:[/bold]\n  [green]{det.get('prevention', '')}[/green]"
        )

        console.print(Panel(
            content,
            title=f"[bold {color}]#{i} — {det.get('pattern_name')} ({det.get('pattern_id')})[/bold {color}]",
            border_style=color
        ))
        console.print()

    # Summary table
    table = Table(
        title="All Visual Detections",
        box=box.ROUNDED,
        border_style="blue",
        show_lines=True
    )
    table.add_column("#",            style="bold", width=3)
    table.add_column("Pattern ID",   style="bold yellow", width=8)
    table.add_column("Pattern Name", style="bold", width=28)
    table.add_column("Confidence",   justify="center", width=12)
    table.add_column("Risk",         justify="center", width=8)

    for i, det in enumerate(detections, 1):
        conf  = det.get("confidence", 0)
        color = "red" if conf >= 0.80 else "yellow" if conf >= 0.55 else "dim"
        table.add_row(
            str(i),
            det.get("pattern_id", ""),
            det.get("pattern_name", ""),
            f"[{color}]{conf:.0%}[/{color}]",
            f"[{color}]{det.get('risk_level', '?').upper()}[/{color}]"
        )

    console.print(table)
    console.print()     

    # Append to utils/output_formatter.py

def print_pricing_header(input_file: str):
    console.print()
    console.print(Rule("[bold blue]DARK GUARD AI — Pricing Agent[/bold blue]", style="blue"))
    console.print(f"[dim]Analyzing:[/dim] [cyan]{input_file}[/cyan]")
    console.print(Rule(style="blue"))
    console.print()


def print_pricing_detection_summary(result: dict, input_file: str):
    """Print full pricing agent detection report."""
    detections   = result.get("detections", [])
    ctx          = result.get("analysis_context", {})
    summary      = result.get("funnel_summary", "")
    unexplained  = result.get("total_unexplained_increase", 0.0)

    console.print()
    console.print(Rule(
        "[bold]PRICING DETECTION REPORT[/bold]",
        style="red" if detections else "green"
    ))
    console.print()

    # ── Funnel progression table ───────────────────────────────────────────
    progression = ctx.get("total_progression", [])
    if progression:
        prog_table = Table(
            title="Price Progression Across Funnel",
            box=box.ROUNDED,
            border_style="blue"
        )
        prog_table.add_column("Stage",          style="bold", width=16)
        prog_table.add_column("Item Subtotal",  justify="right", width=16)
        prog_table.add_column("Fees Total",     justify="right", width=14)
        prog_table.add_column("Displayed Total",justify="right", width=16)
        prog_table.add_column("Change",         justify="right", width=10)

        prev_total = None
        for p in progression:
            displayed = p["displayed_total"]
            change    = ""
            if prev_total is not None:
                diff  = displayed - prev_total
                color = "red" if diff > 0 else "green" if diff < 0 else "dim"
                change = f"[{color}]{'+' if diff > 0 else ''}{diff:.2f}[/{color}]"
            prog_table.add_row(
                p["stage"],
                f"{p['item_subtotal']:.2f}",
                f"{p['fees_total']:.2f}",
                f"[bold]{displayed:.2f}[/bold]",
                change
            )
            prev_total = displayed

        console.print(prog_table)
        console.print()

    # ── No patterns found ─────────────────────────────────────────────────
    if not detections:
        console.print(Panel(
            "[bold green]✓ No pricing dark patterns detected[/bold green]\n"
            "[dim]Prices are consistent and all fees were disclosed early.[/dim]",
            border_style="green"
        ))
        if summary:
            console.print(Panel(
                f"[dim]{summary}[/dim]",
                title="[bold]Funnel Summary[/bold]",
                border_style="blue"
            ))
        return

    # ── Summary panel ──────────────────────────────────────────────────────
    total  = len(detections)
    high   = sum(1 for d in detections if d.get("confidence", 0) >= 0.80)
    medium = sum(1 for d in detections if 0.55 <= d.get("confidence", 0) < 0.80)

    console.print(Panel(
        f"[bold red]{total} pricing dark pattern(s) detected[/bold red]\n\n"
        f"[red]● High confidence (≥80%):[/red]    {high}\n"
        f"[yellow]● Medium confidence (55-79%):[/yellow] {medium}\n"
        + (f"\n[bold]Total unexplained increase:[/bold] [red]{unexplained:.2f}[/red]"
           if unexplained else ""),
        title="[bold]Summary[/bold]",
        border_style="red"
    ))
    console.print()

    # ── Per-detection panels ───────────────────────────────────────────────
    for i, det in enumerate(detections, 1):
        confidence = det.get("confidence", 0)
        color      = "red" if confidence >= 0.80 else "yellow" if confidence >= 0.55 else "dim"
        evidence   = det.get("price_evidence", {})

        # Build price evidence section
        ev_lines = []
        if evidence.get("reference_price") is not None:
            ev_lines.append(
                f"  [dim]•[/dim] Reference price: [bold]{evidence['reference_price']:.2f}[/bold]"
            )
        if evidence.get("final_price") is not None:
            ev_lines.append(
                f"  [dim]•[/dim] Final price:     [bold red]{evidence['final_price']:.2f}[/bold red]"
            )
        if evidence.get("difference") is not None:
            ev_lines.append(
                f"  [dim]•[/dim] Difference:      [bold red]+{evidence['difference']:.2f} "
                f"({evidence.get('difference_pct', 0):.1f}%)[/bold red]"
            )
        if evidence.get("injected_fees"):
            ev_lines.append(f"  [dim]•[/dim] Hidden fees injected:")
            for fee in evidence["injected_fees"]:
                ev_lines.append(
                    f"       [red]- {fee.get('fee_name', fee.get('name','?'))}: "
                    f"{fee.get('amount', 0):.2f}[/red]"
                )
        if evidence.get("affected_stages"):
            ev_lines.append(
                f"  [dim]•[/dim] Stages affected: "
                f"{' → '.join(evidence['affected_stages'])}"
            )

        content = (
            f"[bold]Pattern ID:[/bold]   {det.get('pattern_id')}\n"
            f"[bold]Confidence:[/bold]   [{color}]{confidence:.0%}[/{color}]\n"
            f"[bold]Risk Level:[/bold]   [{color}]{det.get('risk_level','?').upper()}[/{color}]\n\n"
            f"[bold]Price Evidence:[/bold]\n"
            + "\n".join(ev_lines) + "\n\n"
            f"[bold]What happened:[/bold]\n  {det.get('explanation', '')}\n\n"
            f"[bold]What you should do:[/bold]\n  [green]{det.get('prevention', '')}[/green]"
        )

        console.print(Panel(
            content,
            title=f"[bold {color}]#{i} — {det.get('pattern_name')} ({det.get('pattern_id')})[/bold {color}]",
            border_style=color
        ))
        console.print()

    # ── Summary table ──────────────────────────────────────────────────────
    table = Table(
        title="All Pricing Detections",
        box=box.ROUNDED,
        border_style="blue",
        show_lines=True
    )
    table.add_column("#",            style="bold", width=3)
    table.add_column("Pattern ID",   style="bold yellow", width=8)
    table.add_column("Pattern Name", style="bold", width=20)
    table.add_column("Confidence",   justify="center", width=12)
    table.add_column("Risk",         justify="center", width=8)

    for i, det in enumerate(detections, 1):
        conf  = det.get("confidence", 0)
        color = "red" if conf >= 0.80 else "yellow" if conf >= 0.55 else "dim"
        table.add_row(
            str(i),
            det.get("pattern_id", ""),
            det.get("pattern_name", ""),
            f"[{color}]{conf:.0%}[/{color}]",
            f"[{color}]{det.get('risk_level','?').upper()}[/{color}]"
        )

    console.print(table)

    # ── Funnel summary ─────────────────────────────────────────────────────
    if summary:
        console.print()
        console.print(Panel(
            f"[dim]{summary}[/dim]",
            title="[bold]Funnel Analysis Summary[/bold]",
            border_style="blue"
        ))
    console.print()   


def print_behavioral_header(input_file: str):
    console.print()
    console.print(Rule("[bold blue]DARK GUARD AI — Behavioral Agent[/bold blue]", style="blue"))
    console.print(f"[dim]Analyzing session:[/dim] [cyan]{input_file}[/cyan]")
    console.print(Rule(style="blue"))
    console.print()


def print_behavioral_detection_summary(result: dict, input_file: str):
    detections = result.get("detections", [])
    summary = result.get("session_summary", "")

    console.print()
    console.print(Rule(
        "[bold]BEHAVIORAL DETECTION REPORT[/bold]",
        style="red" if detections else "green"
    ))
    console.print()

    if not detections:
        console.print(Panel(
            "[bold green]✓ No behavioral dark patterns detected[/bold green]\n"
            "[dim]This session appears behaviorally clean.[/dim]",
            border_style="green"
        ))
        if summary:
            console.print(Panel(
                f"[dim]{summary}[/dim]",
                title="[bold]Session Summary[/bold]",
                border_style="blue"
            ))
        console.print()
        return

    total = len(detections)
    high = sum(1 for d in detections if d.get("confidence", 0) >= 0.80)
    medium = sum(1 for d in detections if 0.55 <= d.get("confidence", 0) < 0.80)

    console.print(Panel(
        f"[bold red]{total} behavioral dark pattern(s) detected[/bold red]\n\n"
        f"[red]● High confidence (≥80%):[/red]    {high}\n"
        f"[yellow]● Medium confidence (55-79%):[/yellow] {medium}",
        title="[bold]Summary[/bold]",
        border_style="red"
    ))
    console.print()

    for i, det in enumerate(detections, 1):
        confidence = det.get("confidence", 0)
        color = "red" if confidence >= 0.80 else "yellow" if confidence >= 0.55 else "dim"
        evidence = det.get("behavioral_evidence", {})

        signals = evidence.get("signals_found", [])
        evidence_lines = "\n".join(
            f"  [dim]•[/dim] {signal}" for signal in signals[:5]
        )
        if evidence.get("key_metric"):
            evidence_lines += (
                ("\n" if evidence_lines else "") +
                f"  [dim]•[/dim] Key metric: [bold]{evidence['key_metric']}[/bold]"
            )
        if evidence.get("affected_items"):
            evidence_lines += (
                ("\n" if evidence_lines else "") +
                f"  [dim]•[/dim] Affected items: {', '.join(evidence['affected_items'])}"
            )

        content = (
            f"[bold]Pattern ID:[/bold]   {det.get('pattern_id')}\n"
            f"[bold]Confidence:[/bold]   [{color}]{confidence:.0%}[/{color}]\n"
            f"[bold]Risk Level:[/bold]   [{color}]{det.get('risk_level', '?').upper()}[/{color}]\n\n"
            f"[bold]Behavioral Evidence:[/bold]\n"
            f"{evidence_lines}\n\n"
            f"[bold]What happened:[/bold]\n  {det.get('explanation', '')}\n\n"
            f"[bold]What you should do:[/bold]\n  [green]{det.get('prevention', '')}[/green]"
        )

        console.print(Panel(
            content,
            title=f"[bold {color}]#{i} — {det.get('pattern_name')} ({det.get('pattern_id')})[/bold {color}]",
            border_style=color
        ))
        console.print()

    if summary:
        console.print(Panel(
            f"[dim]{summary}[/dim]",
            title="[bold]Session Summary[/bold]",
            border_style="blue"
        ))
        console.print()

    # Append to utils/output_formatter.py

def print_behavioral_header(input_file: str):
    console.print()
    console.print(Rule("[bold blue]DARK GUARD AI — Behavioral Agent[/bold blue]", style="blue"))
    console.print(f"[dim]Analyzing:[/dim] [cyan]{input_file}[/cyan]")
    console.print(Rule(style="blue"))
    console.print()


def print_behavioral_detection_summary(result: dict, input_file: str):
    detections = result.get("detections", [])
    ctx        = result.get("analysis_context", {})
    summary    = result.get("session_summary", "")

    console.print()
    console.print(Rule(
        "[bold]BEHAVIORAL DETECTION REPORT[/bold]",
        style="red" if detections else "green"
    ))
    console.print()

    # ── Pre-analysis flags table ───────────────────────────────────────────
    flag_table = Table(
        title="Pre-Analysis Signals",
        box=box.ROUNDED,
        border_style="blue"
    )
    flag_table.add_column("Pattern",    style="bold", width=22)
    flag_table.add_column("Data Found", justify="center", width=12)
    flag_table.add_column("Triggered",  justify="center", width=12)
    flag_table.add_column("Severity",   justify="center", width=10)

    checks = {
        "DP02 - Basket Sneaking":   ctx.get("basket_sneaking", {}),
        "DP05 - Subscription Trap": ctx.get("subscription_trap", {}),
        "DP12 - SaaS Billing":      ctx.get("saas_billing", {}),
        "DP10 - Nagging":           ctx.get("nagging", {}),
    }
    for name, data in checks.items():
        has_data  = data.get("has_data", False)
        triggered = data.get("triggered", False)
        severity  = data.get("severity", data.get("overall_severity", "none"))
        color     = "red" if triggered else "green"
        sev_color = "red" if severity == "high" else "yellow" if severity == "medium" else "dim"
        flag_table.add_row(
            name,
            "[green]Yes[/green]" if has_data else "[dim]No[/dim]",
            f"[{color}]{'⚠ YES' if triggered else '✓ No'}[/{color}]",
            f"[{sev_color}]{severity.upper() if severity != 'none' else '—'}[/{sev_color}]"
        )

    console.print(flag_table)
    console.print()

    if not detections:
        console.print(Panel(
            "[bold green]✓ No behavioral dark patterns detected[/bold green]\n"
            "[dim]This session appears to be clean.[/dim]",
            border_style="green"
        ))
        if summary:
            console.print(Panel(f"[dim]{summary}[/dim]",
                                title="Session Summary", border_style="blue"))
        return

    total  = len(detections)
    high   = sum(1 for d in detections if d.get("confidence", 0) >= 0.80)
    medium = sum(1 for d in detections if 0.55 <= d.get("confidence", 0) < 0.80)

    console.print(Panel(
        f"[bold red]{total} behavioral dark pattern(s) detected[/bold red]\n\n"
        f"[red]● High confidence (≥80%):[/red]    {high}\n"
        f"[yellow]● Medium confidence (55-79%):[/yellow] {medium}",
        title="[bold]Summary[/bold]",
        border_style="red"
    ))
    console.print()

    for i, det in enumerate(detections, 1):
        confidence = det.get("confidence", 0)
        color      = "red" if confidence >= 0.80 else "yellow" if confidence >= 0.55 else "dim"
        evidence   = det.get("behavioral_evidence", {})

        signals = "\n".join(
            f"  [dim]•[/dim] {s}"
            for s in evidence.get("signals_found", [])[:5]
        )
        affected = ", ".join(evidence.get("affected_items", [])[:4])
        key_metric = evidence.get("key_metric", "")

        content = (
            f"[bold]Pattern ID:[/bold]   {det.get('pattern_id')}\n"
            f"[bold]Confidence:[/bold]   [{color}]{confidence:.0%}[/{color}]\n"
            f"[bold]Risk Level:[/bold]   [{color}]{det.get('risk_level','?').upper()}[/{color}]\n\n"
            + (f"[bold]Key Metric:[/bold]   [red]{key_metric}[/red]\n\n" if key_metric else "")
            + (f"[bold]Behavioral Signals:[/bold]\n{signals}\n\n" if signals else "")
            + (f"[bold]Items Involved:[/bold]   {affected}\n\n" if affected else "")
            + f"[bold]What happened:[/bold]\n  {det.get('explanation', '')}\n\n"
            + f"[bold]What you should do:[/bold]\n  [green]{det.get('prevention', '')}[/green]"
        )

        console.print(Panel(
            content,
            title=f"[bold {color}]#{i} — {det.get('pattern_name')} ({det.get('pattern_id')})[/bold {color}]",
            border_style=color
        ))
        console.print()

    table = Table(title="All Behavioral Detections", box=box.ROUNDED,
                  border_style="blue", show_lines=True)
    table.add_column("#",            style="bold",        width=3)
    table.add_column("Pattern ID",   style="bold yellow", width=8)
    table.add_column("Pattern Name", style="bold",        width=22)
    table.add_column("Confidence",   justify="center",    width=12)
    table.add_column("Risk",         justify="center",    width=8)

    for i, det in enumerate(detections, 1):
        conf  = det.get("confidence", 0)
        color = "red" if conf >= 0.80 else "yellow" if conf >= 0.55 else "dim"
        table.add_row(
            str(i),
            det.get("pattern_id", ""),
            det.get("pattern_name", ""),
            f"[{color}]{conf:.0%}[/{color}]",
            f"[{color}]{det.get('risk_level','?').upper()}[/{color}]"
        )

    console.print(table)

    if summary:
        console.print()
        console.print(Panel(f"[dim]{summary}[/dim]",
                            title="[bold]Session Analysis Summary[/bold]",
                            border_style="blue"))
    console.print()
