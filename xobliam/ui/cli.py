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
    """Print deletion candidates table."""
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


def print_deletion_summary(summary: dict[str, Any]) -> None:
    """Print deletion summary."""
    tier_counts = summary.get("tier_counts", {})

    table = Table(title="Deletion Summary")
    table.add_column("Tier", style="cyan")
    table.add_column("Count", justify="right", style="green")

    table.add_row("Very Safe (90-100)", str(tier_counts.get("very_safe", 0)))
    table.add_row("Likely Safe (70-89)", str(tier_counts.get("likely_safe", 0)))
    table.add_row("Review (50-69)", str(tier_counts.get("review", 0)))
    table.add_row("Keep (<50)", str(tier_counts.get("keep", 0)))

    console.print(table)
    console.print(f"\nTotal deletable: [green]{summary.get('deletable', 0)}[/green]")


def print_label_stats(stats: dict[str, Any], limit: int = 15) -> None:
    """Print label statistics."""
    # Print summary
    console.print(f"Total messages: [green]{stats['total_messages']:,}[/green]")
    console.print(
        f"Unlabeled: [yellow]{stats['unlabeled_count']:,}[/yellow] "
        f"({stats['unlabeled_percentage']:.1f}%)"
    )
    console.print()

    # Print label table
    table = Table(title="Label Statistics")
    table.add_column("Label", style="cyan", max_width=30)
    table.add_column("Count", justify="right", style="green")
    table.add_column("%", justify="right", style="dim")
    table.add_column("Read Rate", justify="right", style="yellow")

    labels = stats.get("labels", [])
    for label in labels[:limit]:
        table.add_row(
            label.get("label", "")[:30],
            str(label.get("count", 0)),
            f"{label.get('percentage', 0):.1f}%",
            f"{label.get('read_rate', 0):.1f}%",
        )

    console.print(table)


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
    """Print new label suggestions."""
    if not suggestions:
        print_info("No new label suggestions")
        return

    table = Table(title="Suggested New Labels")
    table.add_column("Label", style="cyan")
    table.add_column("Domain", style="dim")
    table.add_column("Count", justify="right", style="green")

    for suggestion in suggestions[:10]:
        table.add_row(
            suggestion.get("suggested_label", ""),
            suggestion.get("domain", ""),
            str(suggestion.get("message_count", 0)),
        )

    console.print(table)
