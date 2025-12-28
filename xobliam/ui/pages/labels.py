"""Labels page for Streamlit UI."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from xobliam.analytics import (
    analyze_engagement_efficiency,
    calculate_coherence_scores,
    find_label_overlaps,
    find_redundant_labels,
    find_split_candidates,
    generate_recommendations,
    get_label_health_summary,
    get_label_sender_breakdown,
    get_label_stats,
    suggest_new_labels,
)
from xobliam.fetcher import MessageCache, get_label_id_by_name, merge_labels


def render():
    """Render the labels page."""
    st.title("Label Optimization")
    st.caption("Analyze and optimize your Gmail labels")

    # Load data
    cache = MessageCache()
    messages = cache.get_cached_messages(since_days=90)

    if not messages:
        st.warning("No email data available. Click 'Refresh Data' in the sidebar.")
        return

    # Get all labels from cache (including abandoned ones)
    all_cached_labels = cache.get_cached_labels()

    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Health Summary",
        "All Labels",
        "Label Details",
        "Coherence",
        "Engagement",
        "Overlap & Merge",
    ])

    with tab1:
        render_health_summary(messages, all_cached_labels)

    with tab2:
        render_all_labels(messages, all_cached_labels)

    with tab3:
        render_label_details(messages, all_cached_labels)

    with tab4:
        render_coherence(messages)

    with tab5:
        render_engagement(messages)

    with tab6:
        render_overlap_and_merge(messages, cache)


def render_health_summary(messages: list, all_cached_labels: list):
    """Render label health summary and recommendations."""
    st.subheader("Label Health Summary")

    # Get health metrics
    health = get_label_health_summary(messages, all_labels=all_cached_labels)

    # Display metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Working Well",
            health["working_well"],
            help="Labels with >30% read rate",
        )

    with col2:
        st.metric(
            "Needs Attention",
            health["needs_attention"],
            help="Labels with <10% read rate and >20 emails",
        )

    with col3:
        st.metric(
            "Redundant Pairs",
            health["redundant_pairs"],
            help="Label pairs with >80% overlap",
        )

    with col4:
        st.metric(
            "Abandoned",
            health["abandoned"],
            help="Labels with 0 emails in timeframe",
        )

    st.info(f"Inbox average read rate: **{health['inbox_read_rate']:.1f}%**")

    st.divider()

    # Recommendations
    st.subheader("Actionable Recommendations")

    recommendations = generate_recommendations(messages, all_labels=all_cached_labels)

    if not recommendations:
        st.success("No issues found - your labels are well organized!")
        return

    for rec in recommendations[:15]:
        action = rec.get("action", "")
        label = rec.get("label", "")
        detail = rec.get("detail", "")
        impact = rec.get("impact", "low")

        # Color code by action type
        if action == "MERGE":
            icon = "🔴"
        elif action == "FIX":
            icon = "🟡"
        elif action == "REVIEW":
            icon = "🔵"
        elif action == "CLEANUP":
            icon = "⚪"
        elif action == "SPLIT":
            icon = "🟢"
        else:
            icon = "⚪"

        with st.expander(f"{icon} **{action}**: {label}"):
            st.write(detail)
            st.caption(f"Impact: {impact}")


def render_all_labels(messages: list, all_cached_labels: list):
    """Render complete label list with abandoned detection."""
    st.subheader("All User Labels")
    st.caption(
        "Complete list of your labels, including abandoned ones with 0 messages "
        "in the current timeframe."
    )

    # Get stats with all cached labels to include abandoned ones
    stats = get_label_stats(messages, all_labels=all_cached_labels)
    all_labels = stats["labels"]

    # Filter to user labels only (no system labels)
    user_labels = [l for l in all_labels if not l["is_system"]]

    # Summary metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total User Labels", len(user_labels))

    with col2:
        active_count = len([l for l in user_labels if l["count"] > 0])
        st.metric("Active Labels", active_count)

    with col3:
        abandoned_count = len([l for l in user_labels if l["count"] == 0])
        st.metric("Abandoned Labels", abandoned_count)

    st.divider()

    # Filter options
    col1, col2 = st.columns(2)

    with col1:
        show_filter = st.selectbox(
            "Show",
            ["All Labels", "Active Only", "Abandoned Only"],
            key="label_filter",
        )

    with col2:
        sort_by = st.selectbox(
            "Sort by",
            ["Count (High to Low)", "Count (Low to High)", "Name (A-Z)", "Read Rate"],
            key="label_sort",
        )

    # Apply filters
    if show_filter == "Active Only":
        filtered_labels = [l for l in user_labels if l["count"] > 0]
    elif show_filter == "Abandoned Only":
        filtered_labels = [l for l in user_labels if l["count"] == 0]
    else:
        filtered_labels = user_labels

    # Apply sorting
    if sort_by == "Count (High to Low)":
        filtered_labels = sorted(filtered_labels, key=lambda x: x["count"], reverse=True)
    elif sort_by == "Count (Low to High)":
        filtered_labels = sorted(filtered_labels, key=lambda x: x["count"])
    elif sort_by == "Name (A-Z)":
        filtered_labels = sorted(filtered_labels, key=lambda x: x["label"].lower())
    elif sort_by == "Read Rate":
        filtered_labels = sorted(filtered_labels, key=lambda x: x["read_rate"], reverse=True)

    if not filtered_labels:
        st.info("No labels match the current filter.")
        return

    st.write(f"Showing {len(filtered_labels)} labels")

    # Build dataframe with status column
    df_data = []
    for label in filtered_labels:
        status = "Abandoned" if label["count"] == 0 else "Active"
        df_data.append({
            "Label": label["label"],
            "Status": status,
            "Emails": label["count"],
            "Unread": label["unread"],
            "Read Rate (%)": label["read_rate"],
            "Unique Senders": label["unique_senders"],
        })

    df = pd.DataFrame(df_data)

    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "Read Rate (%)": st.column_config.ProgressColumn(
                min_value=0,
                max_value=100,
                format="%.1f%%",
            ),
        },
    )

    # Abandoned labels cleanup suggestion
    abandoned = [l for l in user_labels if l["count"] == 0]
    if abandoned:
        st.divider()
        st.warning(
            f"Found **{len(abandoned)} abandoned label(s)** with no messages in the "
            "last 90 days. Consider deleting these to clean up your Gmail."
        )

        with st.expander("View abandoned labels"):
            for label in abandoned:
                st.write(f"- {label['label']}")


def render_label_details(messages: list, all_cached_labels: list):
    """Render label details with sender breakdown."""
    st.subheader("Label Sender Breakdown")
    st.caption(
        "Select a label to see which senders are under it, ranked by volume."
    )

    # Get all user labels
    stats = get_label_stats(messages, all_labels=all_cached_labels)
    all_labels = stats["labels"]
    user_labels = [l for l in all_labels if not l["is_system"] and l["count"] > 0]

    if not user_labels:
        st.info("No labels with messages to analyze.")
        return

    # Label selector
    label_names = sorted([l["label"] for l in user_labels])
    selected_label = st.selectbox(
        "Select a label",
        label_names,
        key="label_details_selector",
    )

    if not selected_label:
        return

    # Get sender breakdown
    breakdown = get_label_sender_breakdown(messages, selected_label)

    if not breakdown["senders"]:
        st.info(f"No messages found for label '{selected_label}'.")
        return

    # Display label summary
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Emails", breakdown["total_count"])

    with col2:
        st.metric("Unread", breakdown["unread_count"])

    with col3:
        st.metric("Read Rate", f"{breakdown['read_rate']:.1f}%")

    with col4:
        st.metric("Unique Senders", breakdown["unique_senders"])

    st.divider()

    # Sender table
    st.subheader(f"Senders in '{selected_label}'")

    df_data = []
    for sender in breakdown["senders"]:
        df_data.append({
            "Sender": sender["sender"],
            "Emails": sender["count"],
            "Unread": sender["unread"],
            "Read Rate (%)": sender["read_rate"],
            "% of Label": sender["percentage"],
        })

    df = pd.DataFrame(df_data)

    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "Read Rate (%)": st.column_config.ProgressColumn(
                min_value=0,
                max_value=100,
                format="%.1f%%",
            ),
            "% of Label": st.column_config.ProgressColumn(
                min_value=0,
                max_value=100,
                format="%.1f%%",
            ),
        },
    )

    # Top sender chart
    if len(breakdown["senders"]) > 1:
        st.divider()
        top_senders = breakdown["senders"][:15]

        fig = px.bar(
            x=[s["sender"][:30] for s in top_senders],
            y=[s["count"] for s in top_senders],
            labels={"x": "Sender", "y": "Email Count"},
            title=f"Top Senders in '{selected_label}'",
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)


def render_coherence(messages: list):
    """Render label coherence analysis."""
    st.subheader("Label Coherence Analysis")
    st.caption(
        "Coherence measures how focused a label is. High coherence means emails "
        "are from similar senders. Low coherence means the label is too broad."
    )

    coherence = calculate_coherence_scores(messages)

    if not coherence:
        st.info("No labels to analyze.")
        return

    # Build dataframe
    df_data = []
    for label, data in coherence.items():
        df_data.append({
            "Label": label,
            "Coherence": data["coherence_score"],
            "Emails": data["count"],
            "Senders": data["unique_senders"],
            "Domains": data["unique_domains"],
            "Top Sender %": data["top_sender_pct"],
            "Assessment": data["assessment"],
        })

    df = pd.DataFrame(df_data)
    df = df.sort_values("Emails", ascending=False)

    # Chart
    fig = px.bar(
        df.head(20),
        x="Label",
        y="Coherence",
        color="Coherence",
        color_continuous_scale="RdYlGn",
        title="Coherence Score by Label (Top 20 by volume)",
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, width="stretch")

    # Table
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "Coherence": st.column_config.ProgressColumn(
                min_value=0,
                max_value=100,
                format="%d",
            ),
        },
    )

    # Split candidates
    low_coherence = df[df["Coherence"] < 40]
    if not low_coherence.empty:
        st.divider()
        st.warning(
            f"Found **{len(low_coherence)} labels** with low coherence (<40). "
            "These labels may be too broad and could benefit from splitting."
        )


def render_engagement(messages: list):
    """Render engagement efficiency analysis."""
    st.subheader("Engagement Efficiency")
    st.caption(
        "Compare each label's read rate to your inbox average to see which labels "
        "are working and which need attention."
    )

    engagement = analyze_engagement_efficiency(messages)
    inbox_avg = engagement["inbox_read_rate"]

    st.info(f"Your inbox average read rate: **{inbox_avg:.1f}%**")

    # Build dataframe
    df_data = []
    for label, data in engagement["labels"].items():
        df_data.append({
            "Label": label,
            "Read Rate": data["read_rate"],
            "vs Average": data["difference"],
            "Emails": data["count"],
            "Status": data["status"].replace("_", " ").title(),
        })

    df = pd.DataFrame(df_data)
    df = df.sort_values("Emails", ascending=False)

    # Split into categories
    above_avg = df[df["vs Average"] >= 10]
    below_avg = df[df["vs Average"] <= -10]

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Labels Above Average", len(above_avg))

    with col2:
        st.metric("Labels Below Average", len(below_avg))

    st.divider()

    # Chart
    top_labels = df.head(25)
    fig = px.bar(
        top_labels,
        x="Label",
        y="Read Rate",
        color="vs Average",
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0,
        title="Read Rate by Label (Top 25 by volume)",
    )
    fig.add_hline(
        y=inbox_avg,
        line_dash="dash",
        line_color="gray",
        annotation_text=f"Inbox avg: {inbox_avg:.1f}%",
    )
    fig.update_layout(height=450)
    st.plotly_chart(fig, width="stretch")

    # Table
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "Read Rate": st.column_config.ProgressColumn(
                min_value=0,
                max_value=100,
                format="%.1f%%",
            ),
            "vs Average": st.column_config.NumberColumn(
                format="%+.1f",
            ),
        },
    )

    # Needs attention
    needs_attention = engagement.get("needs_attention", [])
    if needs_attention:
        st.divider()
        st.warning(
            f"**{len(needs_attention)} labels need attention** (low read rate with significant volume). "
            "Consider unsubscribing from these senders."
        )
        for label in needs_attention[:10]:
            data = engagement["labels"].get(label, {})
            st.write(f"- **{label}**: {data.get('read_rate', 0):.0f}% read rate, {data.get('count', 0)} emails")


def render_overlap_and_merge(messages: list, cache: MessageCache):
    """Render label overlap analysis with merge execution."""
    st.subheader("Label Overlap & Merge")
    st.caption(
        "Find labels that frequently appear together and merge them directly."
    )

    # Threshold slider
    min_overlap = st.slider(
        "Minimum overlap %",
        min_value=50,
        max_value=100,
        value=80,
        step=5,
    )

    overlaps = find_label_overlaps(messages, min_overlap=min_overlap / 100)

    if not overlaps:
        st.success(f"No label pairs with >{min_overlap}% overlap found.")
        return

    st.write(f"Found **{len(overlaps)} overlapping pairs**")

    # Show merge candidates prominently
    merge_candidates = [o for o in overlaps if o["action"] == "MERGE"]

    if merge_candidates:
        st.warning(f"**{len(merge_candidates)} pairs** are near-identical and can be merged:")

        for i, overlap in enumerate(merge_candidates):
            label_a = overlap["label_a"]
            label_b = overlap["label_b"]
            overlap_pct = overlap["overlap_rate"]

            with st.expander(
                f"**{label_a}** + **{label_b}** ({overlap_pct:.0f}% overlap)"
            ):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(label_a, f"{overlap['count_a']} emails")
                with col2:
                    st.metric(label_b, f"{overlap['count_b']} emails")
                with col3:
                    st.metric("Shared", f"{overlap['overlap_count']} emails")

                st.divider()

                # Merge options
                st.write("**Merge Options:**")

                # Direction selection
                merge_key = f"merge_dir_{i}"
                merge_direction = st.radio(
                    "Keep which label?",
                    [label_a, label_b],
                    key=merge_key,
                    horizontal=True,
                )

                if merge_direction == label_a:
                    source_label = label_b
                    target_label = label_a
                else:
                    source_label = label_a
                    target_label = label_b

                delete_source = st.checkbox(
                    f"Delete '{source_label}' after merge",
                    key=f"delete_source_{i}",
                    value=True,
                )

                st.info(
                    f"This will move all emails from **{source_label}** to **{target_label}**"
                    + (f" and delete the '{source_label}' label." if delete_source else ".")
                )

                # Merge button with confirmation
                col_btn1, col_btn2 = st.columns([1, 3])

                with col_btn1:
                    if st.button("🔀 Merge Now", key=f"merge_btn_{i}", type="primary"):
                        st.session_state[f"confirm_merge_{i}"] = True

                # Confirmation dialog
                if st.session_state.get(f"confirm_merge_{i}", False):
                    st.warning(
                        f"⚠️ **Confirm merge?**\n\n"
                        f"This will:\n"
                        f"1. Add '{target_label}' to all emails in '{source_label}'\n"
                        f"2. Remove '{source_label}' from those emails\n"
                        + (f"3. Delete the '{source_label}' label entirely\n\n" if delete_source else "\n")
                        + "**This cannot be undone.**"
                    )

                    col_conf1, col_conf2, col_conf3 = st.columns([1, 1, 2])

                    with col_conf1:
                        if st.button("✅ Yes, Merge", key=f"confirm_yes_{i}", type="primary"):
                            # Execute merge
                            source_id = get_label_id_by_name(source_label, cache=cache)
                            target_id = get_label_id_by_name(target_label, cache=cache)

                            if not source_id or not target_id:
                                st.error("Could not find label IDs. Try refreshing data.")
                            else:
                                with st.spinner(f"Merging '{source_label}' into '{target_label}'..."):
                                    progress_bar = st.progress(0)
                                    status_text = st.empty()

                                    def update_progress(current, total):
                                        progress_bar.progress(min(1.0, current / total))
                                        status_text.text(f"Processing {current}/{total} emails...")

                                    result = merge_labels(
                                        source_label_id=source_id,
                                        target_label_id=target_id,
                                        delete_source=delete_source,
                                        cache=cache,
                                        progress_callback=update_progress,
                                    )

                                    progress_bar.empty()
                                    status_text.empty()

                                if result["success"]:
                                    st.success(
                                        f"✅ Merged successfully!\n\n"
                                        f"- {result['messages_modified']} emails updated\n"
                                        + (f"- '{source_label}' label deleted" if result.get("source_deleted") else "")
                                    )
                                    st.info("Refresh data to see updated labels.")
                                else:
                                    st.error(f"Merge failed: {result.get('error', 'Unknown error')}")

                            st.session_state[f"confirm_merge_{i}"] = False
                            st.rerun()

                    with col_conf2:
                        if st.button("❌ Cancel", key=f"confirm_no_{i}"):
                            st.session_state[f"confirm_merge_{i}"] = False
                            st.rerun()

    st.divider()

    # Full overlap table
    st.subheader("All Overlapping Pairs")

    df_data = []
    for overlap in overlaps:
        df_data.append({
            "Label A": overlap["label_a"],
            "Label B": overlap["label_b"],
            "Overlap %": overlap["overlap_rate"],
            "Shared Emails": overlap["overlap_count"],
            "A Count": overlap["count_a"],
            "B Count": overlap["count_b"],
            "Action": overlap["action"],
        })

    df = pd.DataFrame(df_data)

    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "Overlap %": st.column_config.ProgressColumn(
                min_value=0,
                max_value=100,
                format="%.0f%%",
            ),
        },
    )
