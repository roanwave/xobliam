"""Rich-based CLI output formatting."""

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.text import Text


console = Console()


def print_header(title: str) -> None:
    """Print a styled header."""
    console.print()
    console.print(Panel(title, style="bold blue"))
    console.print()


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[red]✗[/red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]![/yellow] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


def print_stats_summary(stats: dict[str, Any]) -> None:
    """Print email statistics summary."""
    table = Table(title="Email Statistics", show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Emails", str(stats.get("total", 0)))
    table.add_row("Read", str(stats.get("read", 0)))
    table.add_row("Unread", str(stats.get("unread", 0)))
    table.add_row("Open Rate", f"{stats.get('open_rate', 0):.1f}%")

    console.print(table)


def print_sender_table(
    senders: list[dict[str, Any]],
    title: str = "Top Senders",
    limit: int = 10,
) -> None:
    """Print a table of senders."""
    table = Table(title=title)
    table.add_column("Sender", style="cyan", max_width=40)
    table.add_column("Count", justify="right", style="green")
    table.add_column("Read Rate", justify="right", style="yellow")

    for sender in senders[:limit]:
        table.add_row(
            sender.get("sender", "")[:40],
            str(sender.get("count", 0)),
            f"{sender.get('read_rate', 0):.1f}%",
        )

    console.print(table)


def print_time_pattern_heatmap(patterns: dict[str, Any]) -> None:
    """Print a text-based time pattern visualization."""
    matrix = patterns.get("matrix", [])
    day_names = patterns.get("day_names", [])

    console.print("\n[bold]Email Activity Heatmap[/bold]")
    console.print("(Intensity based on email volume)\n")

    # Header row with hours
    header = "         "
    for h in range(0, 24, 3):
        header += f"{h:02d}  "
    console.print(header, style="dim")

    # Find max for normalization
    max_val = max(max(row) for row in matrix) if matrix else 1

    for day_idx, day_name in enumerate(day_names):
        row = f"{day_name[:3]:>8} "
        for hour in range(24):
            val = matrix[day_idx][hour]
            intensity = val / max_val if max_val > 0 else 0

            if intensity == 0:
                row += "·"
            elif intensity < 0.25:
                row += "░"
            elif intensity < 0.5:
                row += "▒"
            elif intensity < 0.75:
                row += "▓"
            else:
                row += "█"

        console.print(row)

    console.print(f"\nPeak: {patterns.get('peak_day', 'N/A')} at {patterns.get('peak_hour', 0):02d}:00")


def print_deletion_candidates(
    candidates: list[dict[str, Any]],
    limit: int = 20,
) -> None:
    """Print deletion candidates table (ungrouped, flat list)."""
    table = Table(title="Deletion Candidates")
    table.add_column("Score", justify="right", style="bold")
    table.add_column("Tier", style="dim")
    table.add_column("From", max_width=30)
    table.add_column("Subject", max_width=40)

    for candidate in candidates[:limit]:
        score = candidate.get("score", 0)
        tier = candidate.get("tier", {})

        # Color score based on tier
        tier_name = tier.get("name", "keep")
        if tier_name == "very_safe":
            score_style = "green"
        elif tier_name == "likely_safe":
            score_style = "yellow"
        elif tier_name == "review":
            score_style = "orange1"
        else:
            score_style = "red"

        table.add_row(
            Text(str(score), style=score_style),
            tier.get("label", ""),
            candidate.get("sender", "")[:30],
            (candidate.get("subject", "") or "")[:40],
        )

    console.print(table)
    if len(candidates) > limit:
        console.print(f"[dim]... and {len(candidates) - limit} more. Use --expand to see all.[/dim]")


def print_deletion_candidates_grouped(candidates: list[dict[str, Any]]) -> None:
    """Print deletion candidates grouped by sender in a tree view."""
    from collections import defaultdict

    if not candidates:
        return

    # Group by sender
    by_sender: dict[str, list[dict]] = defaultdict(list)
    for c in candidates:
        sender = c.get("sender", "unknown")
        by_sender[sender].append(c)

    # Sort senders by count (most emails first)
    sorted_senders = sorted(by_sender.items(), key=lambda x: len(x[1]), reverse=True)

    # Group by tier for header
    tier_counts: dict[str, int] = defaultdict(int)
    for c in candidates:
        tier_name = c.get("tier", {}).get("name", "keep")
        tier_counts[tier_name] += 1

    # Print tier summary header
    console.print()
    if tier_counts.get("very_safe", 0) > 0:
        console.print(f"[bold green]Very Safe (90-100):[/bold green] {tier_counts['very_safe']} emails")
    if tier_counts.get("likely_safe", 0) > 0:
        console.print(f"[bold yellow]Likely Safe (70-89):[/bold yellow] {tier_counts['likely_safe']} emails")
    if tier_counts.get("review", 0) > 0:
        console.print(f"[bold orange1]Review (50-69):[/bold orange1] {tier_counts['review']} emails")
    console.print()

    # Print tree view
    total_senders = len(sorted_senders)
    for idx, (sender, sender_candidates) in enumerate(sorted_senders):
        is_last = idx == total_senders - 1
        prefix = "└─" if is_last else "├─"
        child_prefix = "   " if is_last else "│  "

        # Get avg score for color
        avg_score = sum(c.get("score", 0) for c in sender_candidates) / len(sender_candidates)
        if avg_score >= 90:
            score_style = "green"
        elif avg_score >= 70:
            score_style = "yellow"
        else:
            score_style = "orange1"

        # Sender line
        console.print(
            f"{prefix} [{score_style}]{sender}[/{score_style}] "
            f"([bold]{len(sender_candidates)}[/bold] emails, avg score: {avg_score:.0f})"
        )

        # Sample subjects (up to 3)
        subjects = []
        for c in sender_candidates[:3]:
            subj = (c.get("subject", "") or "(no subject)")[:35]
            subjects.append(f'"{subj}"')

        subject_line = ", ".join(subjects)
        if len(sender_candidates) > 3:
            subject_line += f", ... +{len(sender_candidates) - 3} more"

        console.print(f"{child_prefix}└─ [dim]{subject_line}[/dim]")

    console.print()
    console.print(f"[bold]Total:[/bold] {len(candidates)} emails from {total_senders} senders")


def print_deletion_summary(summary: dict[str, Any]) -> None:
    """Print deletion summary."""
    tier_counts = summary.get("tier_counts", {})
    unlabeled_count = summary.get("unlabeled_count", 0)
    total_messages = summary.get("total_messages", 0)

    # Show unlabeled filter info
    console.print(
        f"\n[blue]ℹ[/blue] Analyzing [bold]{unlabeled_count:,}[/bold] unlabeled emails "
        f"(of {total_messages:,} total). Labeled emails are protected.\n"
    )

    table = Table(title="Deletion Summary")
    table.add_column("Tier", style="cyan")
    table.add_column("Count", justify="right", style="green")

    table.add_row("Very Safe (90-100)", str(tier_counts.get("very_safe", 0)))
    table.add_row("Likely Safe (70-89)", str(tier_counts.get("likely_safe", 0)))
    table.add_row("Review (50-69)", str(tier_counts.get("review", 0)))
    table.add_row("Keep (<50)", str(tier_counts.get("keep", 0)))

    console.print(table)
    console.print(f"\nTotal deletable: [green]{summary.get('deletable', 0)}[/green]")


def print_label_stats(stats: dict[str, Any], show_system: bool = False) -> None:
    """Print label statistics.

    Args:
        stats: Label statistics from get_label_stats.
        show_system: If True, include system labels. Default False to reduce noise.
    """
    # Print summary
    console.print(f"Total messages: [green]{stats['total_messages']:,}[/green]")
    console.print(
        f"Unlabeled: [yellow]{stats['unlabeled_count']:,}[/yellow] "
        f"({stats['unlabeled_percentage']:.1f}%)"
    )
    console.print()

    # Filter labels
    all_labels = stats.get("labels", [])
    if show_system:
        labels = all_labels
    else:
        labels = [l for l in all_labels if not l.get("is_system", False)]

    if not labels:
        console.print("[dim]No user labels found.[/dim]")
        return

    # Print label table
    table = Table(title="Label Statistics")
    table.add_column("Label", style="cyan", max_width=40)
    table.add_column("Count", justify="right", style="green")
    table.add_column("%", justify="right", style="dim")
    table.add_column("Read Rate", justify="right", style="yellow")

    # Show all labels, highlight abandoned ones (0 messages)
    for label in labels:
        count = label.get("count", 0)
        label_name = label.get("label", "")[:40]

        # Highlight abandoned labels
        if count == 0:
            label_display = f"[dim]{label_name}[/dim] [red](abandoned)[/red]"
            count_display = "[dim]0[/dim]"
            pct_display = "[dim]0.0%[/dim]"
            rate_display = "[dim]—[/dim]"
        else:
            label_display = label_name
            count_display = str(count)
            pct_display = f"{label.get('percentage', 0):.1f}%"
            rate_display = f"{label.get('read_rate', 0):.1f}%"

        table.add_row(label_display, count_display, pct_display, rate_display)

    console.print(table)

    # Summary of abandoned labels
    abandoned = [l for l in labels if l.get("count", 0) == 0]
    if abandoned:
        console.print(
            f"\n[yellow]Found {len(abandoned)} abandoned label(s) with 0 messages "
            f"in this timeframe.[/yellow]"
        )


def print_category_breakdown(stats: dict[str, dict[str, Any]]) -> None:
    """Print category breakdown."""
    table = Table(title="Email Categories")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right", style="green")
    table.add_column("Read Rate", justify="right", style="yellow")
    table.add_column("Description", style="dim", max_width=40)

    for category, data in sorted(stats.items(), key=lambda x: x[1].get("count", 0), reverse=True):
        if data.get("count", 0) > 0:
            table.add_row(
                category,
                str(data.get("count", 0)),
                f"{data.get('read_rate', 0):.1f}%",
                data.get("description", "")[:40],
            )

    console.print(table)


def create_progress() -> Progress:
    """Create a progress bar for long operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    )


def confirm_action(message: str) -> bool:
    """Ask for user confirmation."""
    response = console.input(f"{message} [y/N]: ")
    return response.lower() in ("y", "yes")


def print_redundant_labels(redundant: list[dict[str, Any]]) -> None:
    """Print redundant label pairs."""
    if not redundant:
        print_info("No redundant label pairs found")
        return

    table = Table(title="Redundant Label Pairs")
    table.add_column("Label A", style="cyan")
    table.add_column("Label B", style="cyan")
    table.add_column("Co-occurrence", justify="right", style="yellow")

    for pair in redundant:
        table.add_row(
            pair.get("label_a", ""),
            pair.get("label_b", ""),
            f"{pair.get('co_occurrence_rate', 0):.1f}%",
        )

    console.print(table)


def print_new_label_suggestions(suggestions: list[dict[str, Any]]) -> None:
    """Print new label suggestions (filtered to high-engagement, non-marketing)."""
    if not suggestions:
        print_info("No label suggestions (only high-engagement, non-marketing emails qualify)")
        return

    table = Table(title="Suggested New Labels (High Engagement)")
    table.add_column("Label", style="cyan")
    table.add_column("Domain", style="dim")
    table.add_column("Count", justify="right", style="green")
    table.add_column("Read Rate", justify="right", style="yellow")

    for suggestion in suggestions[:10]:
        table.add_row(
            suggestion.get("suggested_label", ""),
            suggestion.get("domain", ""),
            str(suggestion.get("message_count", 0)),
            f"{suggestion.get('read_rate', 0):.0f}%",
        )

    console.print(table)


def print_label_health_summary(summary: dict[str, Any]) -> None:
    """Print label health summary."""
    console.print("\n[bold]Label Health Summary[/bold]\n")

    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Status")

    # Working well
    working = summary.get("working_well", 0)
    table.add_row(
        "Working well (>30% read)",
        str(working),
        "[green]✓[/green]" if working > 0 else "",
    )

    # Needs attention
    attention = summary.get("needs_attention", 0)
    table.add_row(
        "Needs attention (<10% read)",
        str(attention),
        "[yellow]![/yellow]" if attention > 0 else "[green]✓[/green]",
    )

    # Redundant pairs
    redundant = summary.get("redundant_pairs", 0)
    table.add_row(
        "Redundant pairs (>80% overlap)",
        str(redundant),
        "[yellow]![/yellow]" if redundant > 0 else "[green]✓[/green]",
    )

    # Abandoned
    abandoned = summary.get("abandoned", 0)
    table.add_row(
        "Abandoned (0 emails)",
        str(abandoned),
        "[dim]cleanup[/dim]" if abandoned > 0 else "[green]✓[/green]",
    )

    console.print(table)
    console.print(f"\nInbox average read rate: [cyan]{summary.get('inbox_read_rate', 0):.1f}%[/cyan]")


def print_recommendations(recommendations: list[dict[str, Any]]) -> None:
    """Print actionable recommendations."""
    if not recommendations:
        print_success("No issues found - your labels are well organized!")
        return

    console.print("\n[bold]Actionable Recommendations[/bold]\n")

    for rec in recommendations[:15]:
        action = rec.get("action", "")
        label = rec.get("label", "")
        reason = rec.get("reason", "")
        detail = rec.get("detail", "")

        # Color code by action type
        if action == "MERGE":
            action_style = "[red]MERGE[/red]"
        elif action == "FIX":
            action_style = "[yellow]FIX[/yellow]"
        elif action == "REVIEW":
            action_style = "[blue]REVIEW[/blue]"
        elif action == "CLEANUP":
            action_style = "[dim]CLEANUP[/dim]"
        elif action == "SPLIT":
            action_style = "[cyan]SPLIT[/cyan]"
        else:
            action_style = action

        console.print(f"  {action_style}: [bold]{label}[/bold]")
        console.print(f"    {detail}", style="dim")
        console.print()


def print_coherence_analysis(coherence: dict[str, dict[str, Any]], limit: int = 15) -> None:
    """Print label coherence analysis."""
    if not coherence:
        print_info("No labels to analyze")
        return

    console.print("\n[bold]Label Coherence Analysis[/bold]")
    console.print("[dim]High coherence = focused label, Low coherence = too broad[/dim]\n")

    table = Table(title="Coherence Scores")
    table.add_column("Label", style="cyan", max_width=30)
    table.add_column("Score", justify="right")
    table.add_column("Emails", justify="right", style="green")
    table.add_column("Senders", justify="right")
    table.add_column("Assessment", style="dim")

    # Sort by count (most emails first)
    sorted_labels = sorted(
        coherence.items(),
        key=lambda x: x[1].get("count", 0),
        reverse=True
    )[:limit]

    for label, data in sorted_labels:
        score = data.get("coherence_score", 0)

        # Color code score
        if score >= 70:
            score_display = f"[green]{score}[/green]"
        elif score >= 40:
            score_display = f"[yellow]{score}[/yellow]"
        else:
            score_display = f"[red]{score}[/red]"

        table.add_row(
            label[:30],
            score_display,
            str(data.get("count", 0)),
            str(data.get("unique_senders", 0)),
            data.get("assessment", ""),
        )

    console.print(table)


def print_engagement_efficiency(engagement: dict[str, Any], limit: int = 15) -> None:
    """Print engagement efficiency analysis."""
    labels = engagement.get("labels", {})
    inbox_avg = engagement.get("inbox_read_rate", 0)

    if not labels:
        print_info("No labels to analyze")
        return

    console.print(f"\n[bold]Engagement Efficiency[/bold] (inbox average: {inbox_avg:.1f}%)\n")

    # Sort by difference from average
    sorted_labels = sorted(
        labels.items(),
        key=lambda x: x[1].get("count", 0),
        reverse=True
    )[:limit]

    table = Table(title="Label Engagement vs Inbox Average")
    table.add_column("Label", style="cyan", max_width=30)
    table.add_column("Read Rate", justify="right")
    table.add_column("vs Avg", justify="right")
    table.add_column("Emails", justify="right", style="dim")
    table.add_column("Status")

    for label, data in sorted_labels:
        read_rate = data.get("read_rate", 0)
        diff = data.get("difference", 0)
        status = data.get("status", "")

        # Color code read rate
        if read_rate >= 50:
            rate_display = f"[green]{read_rate:.0f}%[/green]"
        elif read_rate >= 20:
            rate_display = f"[yellow]{read_rate:.0f}%[/yellow]"
        else:
            rate_display = f"[red]{read_rate:.0f}%[/red]"

        # Color code difference
        if diff >= 10:
            diff_display = f"[green]+{diff:.0f}[/green]"
        elif diff <= -10:
            diff_display = f"[red]{diff:.0f}[/red]"
        else:
            diff_display = f"{diff:.0f}"

        # Status indicator
        if status == "above_average":
            status_display = "[green]✓ working[/green]"
        elif status == "below_average":
            status_display = "[yellow]! review[/yellow]"
        else:
            status_display = ""

        table.add_row(
            label[:30],
            rate_display,
            diff_display,
            str(data.get("count", 0)),
            status_display,
        )

    console.print(table)

    # Summary
    working = engagement.get("working_well", [])
    attention = engagement.get("needs_attention", [])

    if working:
        console.print(f"\n[green]Labels working well:[/green] {', '.join(working[:5])}")
    if attention:
        console.print(f"[yellow]Labels needing attention:[/yellow] {', '.join(attention[:5])}")
