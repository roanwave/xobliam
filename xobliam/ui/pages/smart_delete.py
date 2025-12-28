"""Smart Delete page for Streamlit UI."""

import streamlit as st
import pandas as pd

from xobliam.fetcher import MessageCache
from xobliam.smart_delete import (
    calculate_safety_score,
    delete_messages,
    filter_unlabeled_messages,
    find_deletion_candidates,
    get_bulk_delete_recommendations,
    get_deletion_summary,
    get_safety_tier,
    get_score_breakdown,
)


def render():
    """Render the smart delete page."""
    st.title("Smart Delete")
    st.caption("Identify and safely delete unwanted emails")

    # Load data
    cache = MessageCache()
    messages = cache.get_cached_messages(since_days=90)

    if not messages:
        st.warning("No email data available. Click 'Refresh Data' in the sidebar.")
        return

    # Summary
    summary = get_deletion_summary(messages)
    unlabeled_count = summary.get("unlabeled_count", 0)

    st.info(
        f"Analyzing **{unlabeled_count:,} unlabeled emails** for safe deletion. "
        f"Emails you've organized with labels are protected."
    )

    st.subheader("Deletion Summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Very Safe",
            summary["tier_counts"].get("very_safe", 0),
            help="Score 90-100: Safe to bulk delete",
        )

    with col2:
        st.metric(
            "Likely Safe",
            summary["tier_counts"].get("likely_safe", 0),
            help="Score 70-89: Quick review recommended",
        )

    with col3:
        st.metric(
            "Review",
            summary["tier_counts"].get("review", 0),
            help="Score 50-69: Individual attention needed",
        )

    with col4:
        st.metric(
            "Keep",
            summary["tier_counts"].get("keep", 0),
            help="Score <50: Keep these emails",
        )

    st.divider()

    # Tabs
    tab1, tab2, tab3 = st.tabs(["Candidates", "Bulk Delete", "Execute"])

    with tab1:
        render_candidates(messages)

    with tab2:
        render_bulk_recommendations(messages)

    with tab3:
        render_execution(messages, cache)


def render_candidates(messages: list):
    """Render deletion candidates grouped by sender."""
    from collections import defaultdict

    st.subheader("Deletion Candidates")

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        min_score = st.slider("Minimum score", 0, 100, 70)

    with col2:
        tier_filter = st.selectbox(
            "Filter by tier",
            ["All", "Very Safe (90+)", "Likely Safe (70-89)", "Review (50-69)"],
        )

    with col3:
        view_mode = st.selectbox("View", ["Grouped by Sender", "Flat List"])

    # Get candidates
    candidates = find_deletion_candidates(messages, min_score=min_score)

    # Apply tier filter
    if tier_filter == "Very Safe (90+)":
        candidates = [c for c in candidates if c["score"] >= 90]
    elif tier_filter == "Likely Safe (70-89)":
        candidates = [c for c in candidates if 70 <= c["score"] < 90]
    elif tier_filter == "Review (50-69)":
        candidates = [c for c in candidates if 50 <= c["score"] < 70]

    if not candidates:
        st.info("No candidates matching your criteria.")
        return

    st.write(f"Found **{len(candidates)}** candidates")

    if view_mode == "Flat List":
        # Original flat dataframe view
        df_data = []
        for c in candidates[:500]:
            tier = c.get("tier", {})
            df_data.append({
                "Score": c["score"],
                "Tier": tier.get("label", ""),
                "From": c.get("sender", "")[:40],
                "Subject": (c.get("subject", "") or "")[:50],
                "Date": c.get("date", "")[:10],
            })

        df = pd.DataFrame(df_data)
        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            height=400,
        )
    else:
        # Grouped by sender view
        by_sender: dict[str, list[dict]] = defaultdict(list)
        for c in candidates:
            sender = c.get("sender", "unknown")
            by_sender[sender].append(c)

        # Sort by count
        sorted_senders = sorted(by_sender.items(), key=lambda x: len(x[1]), reverse=True)

        st.write(f"From **{len(sorted_senders)}** unique senders")
        st.divider()

        for sender, sender_candidates in sorted_senders:
            avg_score = sum(c.get("score", 0) for c in sender_candidates) / len(sender_candidates)
            count = len(sender_candidates)

            # Determine tier color
            if avg_score >= 90:
                tier_emoji = "🟢"
            elif avg_score >= 70:
                tier_emoji = "🟡"
            else:
                tier_emoji = "🟠"

            # Sample subjects for preview
            sample_subjects = [
                (c.get("subject", "") or "(no subject)")[:40]
                for c in sender_candidates[:3]
            ]
            preview = ", ".join(f'"{s}"' for s in sample_subjects)
            if count > 3:
                preview += f" ... +{count - 3} more"

            with st.expander(
                f"{tier_emoji} **{sender}** — {count} emails (avg score: {avg_score:.0f})"
            ):
                st.caption(f"Preview: {preview}")
                st.divider()

                # Show all emails from this sender
                sender_df = pd.DataFrame([
                    {
                        "Score": c["score"],
                        "Subject": (c.get("subject", "") or "")[:60],
                        "Date": c.get("date", "")[:10],
                    }
                    for c in sender_candidates
                ])

                st.dataframe(
                    sender_df,
                    width="stretch",
                    hide_index=True,
                    height=min(200, 35 * len(sender_candidates) + 40),
                )

    # Score breakdown for selected email
    st.divider()
    st.subheader("Score Breakdown")

    if candidates:
        selected_idx = st.selectbox(
            "Select email to analyze",
            range(min(len(candidates), 100)),
            format_func=lambda i: f"{candidates[i]['sender'][:30]} - {(candidates[i].get('subject', '') or '')[:40]}",
        )

        if selected_idx is not None:
            selected = candidates[selected_idx]

            # Find original message
            original = next(
                (m for m in messages if m.get("message_id") == selected["message_id"]),
                None,
            )

            if original:
                breakdown = get_score_breakdown(original)

                col1, col2 = st.columns([1, 2])

                with col1:
                    score = breakdown["score"]
                    tier = get_safety_tier(score)

                    st.metric("Safety Score", score)
                    st.write(f"**Tier:** {tier['label']}")

                with col2:
                    st.write("**Scoring factors:**")

                    for factor in breakdown["factors"]:
                        impact = factor["impact"]
                        if impact > 0:
                            st.write(f"- {factor['factor']}: **+{impact}**")
                        elif impact < 0:
                            st.write(f"- {factor['factor']}: **{impact}**")


def render_bulk_recommendations(messages: list):
    """Render bulk delete recommendations."""
    st.subheader("Bulk Delete Recommendations")
    st.caption("Senders whose emails are consistently safe to delete")

    recommendations = get_bulk_delete_recommendations(messages)

    if not recommendations:
        st.info("No bulk delete recommendations found.")
        return

    for rec in recommendations[:20]:
        with st.expander(
            f"**{rec['sender'][:40]}** - {rec['count']} emails "
            f"(avg score: {rec['avg_score']:.0f})"
        ):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Emails", rec["count"])

            with col2:
                st.metric("Avg Score", f"{rec['avg_score']:.1f}")

            with col3:
                st.metric("Min Score", rec["min_score"])

            st.success(rec["recommendation"])


def render_execution(messages: list, cache: MessageCache):
    """Render deletion execution interface with sender selection."""
    from collections import defaultdict

    st.subheader("Execute Deletion")

    st.warning(
        "**Warning:** Deleted emails will be moved to Trash. "
        "You can recover them from Trash within 30 days."
    )

    # Get candidates
    min_score = st.slider("Minimum safety score", 70, 100, 90, key="exec_score")
    candidates = find_deletion_candidates(messages, min_score=min_score)

    if not candidates:
        st.info(f"No emails with safety score >= {min_score}")
        return

    # Group by sender
    by_sender: dict[str, list[dict]] = defaultdict(list)
    for c in candidates:
        sender = c.get("sender", "unknown")
        by_sender[sender].append(c)

    sorted_senders = sorted(by_sender.items(), key=lambda x: len(x[1]), reverse=True)

    st.write(f"**{len(candidates)} emails** from **{len(sorted_senders)} senders** ready for deletion")

    st.divider()

    # Select/deselect all
    col1, col2 = st.columns(2)
    with col1:
        select_all = st.checkbox("Select all senders", value=True, key="select_all")

    # Sender selection with checkboxes
    st.subheader("Select Senders to Delete")

    selected_message_ids = []

    for sender, sender_candidates in sorted_senders:
        avg_score = sum(c.get("score", 0) for c in sender_candidates) / len(sender_candidates)
        count = len(sender_candidates)

        # Determine tier color
        if avg_score >= 90:
            tier_emoji = "🟢"
        elif avg_score >= 70:
            tier_emoji = "🟡"
        else:
            tier_emoji = "🟠"

        # Sample subjects
        sample_subjects = [(c.get("subject", "") or "(no subject)")[:30] for c in sender_candidates[:2]]
        preview = ", ".join(f'"{s}"' for s in sample_subjects)
        if count > 2:
            preview += f" +{count - 2} more"

        # Checkbox for this sender
        sender_key = f"sender_{sender[:50]}"
        is_selected = st.checkbox(
            f"{tier_emoji} **{sender}** — {count} emails (avg: {avg_score:.0f})",
            value=select_all,
            key=sender_key,
            help=preview,
        )

        if is_selected:
            selected_message_ids.extend([c["message_id"] for c in sender_candidates])

    st.divider()

    # Summary of selection
    selected_count = len(selected_message_ids)
    st.write(f"**Selected:** {selected_count} emails")

    if selected_count == 0:
        st.info("Select at least one sender to proceed.")
        return

    st.divider()

    # Execution buttons
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Dry Run", use_container_width=True):
            with st.spinner("Simulating deletion..."):
                result = delete_messages(
                    selected_message_ids,
                    cache=cache,
                    dry_run=True,
                )

            st.success(
                f"Dry run complete: Would delete {result['deleted']} emails"
            )

    with col2:
        # Confirmation checkbox
        confirm = st.checkbox("I confirm I want to delete these emails")

        if st.button(
            "Delete Emails",
            use_container_width=True,
            type="primary",
            disabled=not confirm,
        ):
            progress_bar = st.progress(0)
            status_text = st.empty()

            def update_progress(current: int, total: int):
                progress_bar.progress(current / total)
                status_text.text(f"Deleting {current} of {total}...")

            with st.spinner("Deleting emails..."):
                result = delete_messages(
                    selected_message_ids,
                    cache=cache,
                    dry_run=False,
                    progress_callback=update_progress,
                )

            progress_bar.progress(1.0)

            if result["success"]:
                st.success(f"Successfully deleted {result['deleted']} emails!")
                st.balloons()
            else:
                st.warning(
                    f"Deleted {result['deleted']} emails, "
                    f"failed {result['failed']}"
                )

                if result.get("errors"):
                    with st.expander("View errors"):
                        for error in result["errors"]:
                            st.write(f"- {error['message_id']}: {error['error']}")

            # Suggest refresh
            st.info("Click 'Refresh Data' in the sidebar to update the cache.")
