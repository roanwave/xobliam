"""CLI entrypoint for xobliam."""

import json
import os
import sys

import click
from dotenv import load_dotenv

from xobliam.analytics import (
    analyze_engagement_efficiency,
    analyze_time_patterns,
    calculate_coherence_scores,
    calculate_open_rate,
    find_redundant_labels,
    generate_recommendations,
    get_day_of_week_distribution,
    get_frequent_senders,
    get_label_health_summary,
    get_label_stats,
    suggest_new_labels,
)
from xobliam.fetcher import MessageCache, fetch_labels, fetch_messages
from xobliam.smart_delete import (
    delete_messages,
    find_deletion_candidates,
    get_deletion_summary,
)
from xobliam.taxonomy import get_category_stats
from xobliam.ui.cli import (
    confirm_action,
    console,
    create_progress,
    print_category_breakdown,
    print_coherence_analysis,
    print_deletion_candidates,
    print_deletion_summary,
    print_engagement_efficiency,
    print_error,
    print_header,
    print_info,
    print_label_health_summary,
    print_label_stats,
    print_new_label_suggestions,
    print_recommendations,
    print_redundant_labels,
    print_sender_table,
    print_stats_summary,
    print_success,
    print_time_pattern_heatmap,
    print_warning,
)

# Load environment variables
load_dotenv()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """xobliam - Gmail analytics dashboard with intelligent cleanup."""
    pass


@cli.command()
def ui():
    """Launch the Streamlit dashboard."""
    import subprocess

    app_path = os.path.join(os.path.dirname(__file__), "app.py")
    subprocess.run([sys.executable, "-m", "streamlit", "run", app_path])


@cli.command()
@click.option("--days", default=90, help="Number of days to analyze")
def stats(days: int):
    """Show quick email statistics."""
    print_header("xobliam - Email Statistics")

    cache = MessageCache()

    # Check if we have cached data
    if not cache.is_fresh(max_age_hours=24):
        print_warning("Cache is stale. Run 'xobliam fetch' to update.")

    messages = cache.get_cached_messages(since_days=days)

    if not messages:
        print_error("No messages found. Run 'xobliam fetch' first.")
        return

    print_info(f"Analyzing {len(messages)} messages from last {days} days\n")

    # Open rate
    open_rate = calculate_open_rate(messages)
    print_stats_summary(open_rate)
    console.print()

    # Top senders
    senders = get_frequent_senders(messages, top_n=10)
    print_sender_table(senders)
    console.print()

    # Time patterns
    patterns = analyze_time_patterns(messages)
    print_time_pattern_heatmap(patterns)
    console.print()

    # Day of week
    dow = get_day_of_week_distribution(messages)
    print_info(f"Busiest day: {dow['busiest_day']} ({dow['busiest_count']} emails)")
    print_info(f"Quietest day: {dow['quietest_day']} ({dow['quietest_count']} emails)")


@cli.command()
@click.option("--days", default=90, help="Number of days to fetch")
@click.option("--force", is_flag=True, help="Force refresh even if cache is fresh")
def fetch(days: int, force: bool):
    """Fetch or refresh email data."""
    print_header("Fetching Email Data")

    cache = MessageCache()

    if cache.is_fresh() and not force:
        count = cache.get_message_count()
        print_info(f"Cache is fresh with {count} messages. Use --force to refresh.")
        return

    print_info(f"Fetching emails from last {days} days...")

    with create_progress() as progress:
        task = progress.add_task("Fetching...", total=100)

        def update_progress(current: int, total: int):
            pct = (current / total * 100) if total > 0 else 0
            progress.update(task, completed=pct)

        try:
            messages = fetch_messages(
                days=days,
                use_cache=False,
                progress_callback=update_progress,
            )
            progress.update(task, completed=100)
        except FileNotFoundError as e:
            print_error(str(e))
            return
        except Exception as e:
            print_error(f"Failed to fetch: {e}")
            return

    print_success(f"Fetched {len(messages)} messages")

    # Also fetch labels
    print_info("Fetching labels...")
    try:
        labels = fetch_labels(use_cache=False)
        print_success(f"Fetched {len(labels)} labels")
    except Exception as e:
        print_warning(f"Failed to fetch labels: {e}")


@cli.command()
@click.option("--output", "-o", default="analysis.json", help="Output file path")
@click.option("--days", default=90, help="Number of days to analyze")
def export(output: str, days: int):
    """Export analytics to JSON."""
    print_header("Exporting Analytics")

    cache = MessageCache()
    messages = cache.get_cached_messages(since_days=days)

    if not messages:
        print_error("No messages found. Run 'xobliam fetch' first.")
        return

    print_info(f"Analyzing {len(messages)} messages...")

    # Gather all analytics
    analysis = {
        "message_count": len(messages),
        "days": days,
        "open_rate": calculate_open_rate(messages),
        "time_patterns": analyze_time_patterns(messages),
        "day_distribution": get_day_of_week_distribution(messages),
        "top_senders": get_frequent_senders(messages, top_n=50),
        "label_stats": get_label_stats(messages),
        "category_stats": get_category_stats(messages),
        "redundant_labels": find_redundant_labels(messages),
        "deletion_summary": get_deletion_summary(messages),
    }

    with open(output, "w") as f:
        json.dump(analysis, f, indent=2, default=str)

    print_success(f"Exported to {output}")


@cli.command("delete")
@click.option("--dry-run", is_flag=True, default=True, help="Simulate without deleting")
@click.option("--execute", is_flag=True, help="Actually delete messages")
@click.option("--min-score", default=80, help="Minimum safety score (0-100)")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
@click.option("--limit", default=100, help="Maximum messages to delete")
def delete_cmd(dry_run: bool, execute: bool, min_score: int, confirm: bool, limit: int):
    """Find and delete safe emails."""
    print_header("Smart Delete")

    # If --execute is passed, it's not a dry run
    if execute:
        dry_run = False

    cache = MessageCache()
    messages = cache.get_cached_messages()

    if not messages:
        print_error("No messages found. Run 'xobliam fetch' first.")
        return

    # Find candidates
    print_info(f"Finding candidates with score >= {min_score}...")
    candidates = find_deletion_candidates(messages, min_score=min_score)

    if not candidates:
        print_info("No deletion candidates found matching criteria.")
        return

    # Show summary
    summary = get_deletion_summary(messages)
    print_deletion_summary(summary)
    console.print()

    # Show top candidates
    print_deletion_candidates(candidates, limit=20)
    console.print()

    # Limit candidates
    to_delete = candidates[:limit]
    print_info(f"Selected {len(to_delete)} messages for deletion")

    if dry_run:
        print_warning("DRY RUN - No messages will be deleted")
        print_info("Use --execute to actually delete messages")
        return

    # Confirm
    if not confirm:
        if not confirm_action(f"Delete {len(to_delete)} messages?"):
            print_info("Cancelled")
            return

    # Execute deletion
    print_info("Deleting messages...")
    message_ids = [c["message_id"] for c in to_delete]

    with create_progress() as progress:
        task = progress.add_task("Deleting...", total=len(message_ids))

        def update_progress(current: int, total: int):
            progress.update(task, completed=current)

        result = delete_messages(
            message_ids,
            cache=cache,
            dry_run=False,
            progress_callback=update_progress,
        )

    if result["success"]:
        print_success(f"Deleted {result['deleted']} messages")
    else:
        print_warning(f"Deleted {result['deleted']}, failed {result['failed']}")
        if result.get("errors"):
            for error in result["errors"][:5]:
                print_error(f"  {error['message_id']}: {error['error']}")


@cli.command()
@click.option("--days", default=90, help="Number of days to analyze")
@click.option("--show-system", is_flag=True, help="Include system labels in output")
@click.option("--full", is_flag=True, help="Show full analysis (coherence, engagement)")
def labels(days: int, show_system: bool, full: bool):
    """Analyze labels and show optimization recommendations."""
    print_header("Label Optimization Analysis")

    cache = MessageCache()
    messages = cache.get_cached_messages(since_days=days)

    if not messages:
        print_error("No messages found. Run 'xobliam fetch' first.")
        return

    # Get all labels from cache (including abandoned ones with 0 messages)
    all_labels = cache.get_cached_labels()

    print_info(f"Analyzing {len(messages)} messages from last {days} days...\n")

    # 1. Label Health Summary (always show)
    health = get_label_health_summary(messages, all_labels=all_labels)
    print_label_health_summary(health)

    # 2. Actionable Recommendations (always show)
    recommendations = generate_recommendations(messages, all_labels=all_labels)
    print_recommendations(recommendations)

    # 3. Label stats table
    console.print()
    label_stats = get_label_stats(messages, all_labels=all_labels)
    print_label_stats(label_stats, show_system=show_system)

    if full:
        # 4. Coherence Analysis
        coherence = calculate_coherence_scores(messages)
        print_coherence_analysis(coherence)

        # 5. Engagement Efficiency
        engagement = analyze_engagement_efficiency(messages)
        print_engagement_efficiency(engagement)

        # 6. Redundant label pairs (detailed)
        console.print()
        redundant = find_redundant_labels(messages, threshold=0.80)
        print_redundant_labels(redundant)

    # 7. New label suggestions (filtered to high-engagement only)
    console.print()
    suggestions = suggest_new_labels(messages)
    if suggestions:
        print_new_label_suggestions(suggestions)


@cli.command()
@click.option("--days", default=90, help="Number of days to analyze")
def taxonomy(days: int):
    """Show email taxonomy breakdown."""
    print_header("Email Taxonomy")

    cache = MessageCache()
    messages = cache.get_cached_messages(since_days=days)

    if not messages:
        print_error("No messages found. Run 'xobliam fetch' first.")
        return

    print_info(f"Classifying {len(messages)} messages...\n")

    stats = get_category_stats(messages)
    print_category_breakdown(stats)


@cli.command()
def auth():
    """Authenticate with Gmail (or re-authenticate)."""
    print_header("Gmail Authentication")

    from xobliam.auth import get_gmail_service, revoke_credentials

    # Check for existing credentials
    from xobliam.auth.credentials import load_credentials

    existing = load_credentials()
    if existing and existing.valid:
        if confirm_action("Already authenticated. Re-authenticate?"):
            revoke_credentials()
        else:
            print_info("Keeping existing authentication")
            return

    print_info("Opening browser for Google authentication...")

    try:
        service = get_gmail_service()
        # Test the connection
        profile = service.users().getProfile(userId="me").execute()
        print_success(f"Authenticated as {profile.get('emailAddress')}")
    except FileNotFoundError as e:
        print_error(str(e))
    except Exception as e:
        print_error(f"Authentication failed: {e}")


@cli.command()
def clear():
    """Clear cached data."""
    print_header("Clear Cache")

    if not confirm_action("Clear all cached data?"):
        print_info("Cancelled")
        return

    cache = MessageCache()
    cache.clear()
    print_success("Cache cleared")


if __name__ == "__main__":
    cli()
