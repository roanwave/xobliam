"""Labels page for Streamlit UI."""

import streamlit as st
import pandas as pd
import plotly.express as px

from xobliam.analytics import (
    find_redundant_labels,
    find_split_candidates,
    get_label_stats,
    suggest_new_labels,
)
from xobliam.fetcher import MessageCache


def render():
    """Render the labels page."""
    st.title("Labels")
    st.caption("Label analysis and optimization suggestions")

    # Load data
    cache = MessageCache()
    messages = cache.get_cached_messages(since_days=90)

    if not messages:
        st.warning("No email data available. Click 'Refresh Data' in the sidebar.")
        return

    # Get all labels from cache (including abandoned ones)
    all_cached_labels = cache.get_cached_labels()

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Overview", "All Labels", "Redundancy Audit", "Suggestions"])

    with tab1:
        render_overview(messages, all_cached_labels)

    with tab2:
        render_all_labels(messages, all_cached_labels)

    with tab3:
        render_redundancy(messages)

    with tab4:
        render_suggestions(messages)


def render_overview(messages: list, all_cached_labels: list):
    """Render label overview."""
    st.subheader("Label Distribution")

    stats = get_label_stats(messages, all_labels=all_cached_labels)
    all_labels = stats["labels"]

    # Show unlabeled stats
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Messages", f"{stats['total_messages']:,}")
    with col2:
        st.metric(
            "Unlabeled",
            f"{stats['unlabeled_count']:,}",
            f"{stats['unlabeled_percentage']:.1f}%",
        )

    st.divider()

    # Filter to user labels and significant counts
    user_labels = [
        s for s in all_labels
        if not s["is_system"] and s["count"] > 0
    ]

    if not user_labels:
        st.info("No user-created labels found in your messages.")
        # Show system labels instead
        system_labels = [s for s in all_labels if s["count"] > 10]
        if system_labels:
            st.subheader("System Labels")
            df = pd.DataFrame(system_labels[:20])
            df = df[["label", "count", "read_rate"]]
            df.columns = ["Label", "Emails", "Read Rate (%)"]
            st.dataframe(df, width="stretch", hide_index=True)
        return

    # Treemap of labels
    df = pd.DataFrame(user_labels[:30])

    fig = px.treemap(
        df,
        path=["label"],
        values="count",
        color="read_rate",
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=50,
    )
    fig.update_layout(height=500)
    st.plotly_chart(fig, width="stretch")

    # Table view
    st.subheader("Label Statistics")

    table_df = pd.DataFrame(user_labels)
    table_df = table_df[["label", "count", "unread", "read_rate", "unique_senders"]]
    table_df.columns = ["Label", "Emails", "Unread", "Read Rate (%)", "Unique Senders"]

    st.dataframe(
        table_df,
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

    # Style abandoned labels
    def highlight_abandoned(row):
        if row["Status"] == "Abandoned":
            return ["background-color: #ffcccc"] * len(row)
        return [""] * len(row)

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
        st.subheader("Cleanup Suggestions")
        st.warning(
            f"Found **{len(abandoned)} abandoned label(s)** with no messages in the "
            "last 90 days. Consider deleting these to clean up your Gmail."
        )

        with st.expander("View abandoned labels"):
            for label in abandoned:
                st.write(f"- {label['label']}")


def render_redundancy(messages: list):
    """Render redundancy audit."""
    st.subheader("Redundant Label Pairs")
    st.caption(
        "Labels that frequently appear together may be candidates for merging. "
        "A high co-occurrence rate means the labels are often used on the same emails."
    )

    # Threshold control
    threshold = st.slider(
        "Co-occurrence threshold (%)",
        min_value=50,
        max_value=100,
        value=90,
        step=5,
    ) / 100

    redundant = find_redundant_labels(messages, threshold=threshold)

    if not redundant:
        st.success(f"No label pairs with >{threshold*100:.0f}% co-occurrence found.")
        return

    for pair in redundant:
        with st.expander(
            f"**{pair['label_a']}** + **{pair['label_b']}** "
            f"({pair['co_occurrence_rate']:.1f}% co-occurrence)"
        ):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(pair["label_a"], f"{pair['count_a']} emails")

            with col2:
                st.metric(pair["label_b"], f"{pair['count_b']} emails")

            with col3:
                st.metric("Together", f"{pair['pair_count']} emails")

            st.info(pair["suggestion"])

    # Split candidates
    st.subheader("Split Candidates")
    st.caption(
        "Labels with many different senders might benefit from being split into more specific labels."
    )

    split = find_split_candidates(messages)

    if not split:
        st.info("No labels identified as split candidates.")
        return

    for candidate in split[:10]:
        with st.expander(
            f"**{candidate['label']}** - {candidate['unique_senders']} unique senders"
        ):
            st.metric("Total Emails", candidate["count"])
            st.metric("Sender Diversity", f"{candidate['sender_diversity']:.2f}")
            st.info(candidate["suggestion"])


def render_suggestions(messages: list):
    """Render new label suggestions."""
    st.subheader("Suggested New Labels")
    st.caption(
        "Based on patterns in your unlabeled emails, these new labels might help organize your inbox."
    )

    suggestions = suggest_new_labels(messages)

    if not suggestions:
        st.success("Your emails are well-organized! No new label suggestions.")
        return

    for suggestion in suggestions[:15]:
        with st.expander(
            f"**{suggestion['suggested_label']}** - {suggestion['message_count']} emails"
        ):
            st.write(f"**Domain:** {suggestion['domain']}")
            st.write(f"**Email count:** {suggestion['message_count']}")

            if suggestion.get("sample_subjects"):
                st.write("**Sample subjects:**")
                for subject in suggestion["sample_subjects"][:5]:
                    st.write(f"- {subject[:80]}...")

            if suggestion.get("common_words"):
                st.write(f"**Common words:** {', '.join(suggestion['common_words'][:10])}")

    # Summary
    st.divider()
    total_unlabeled = sum(s["message_count"] for s in suggestions)
    st.info(
        f"Creating these labels could help organize approximately {total_unlabeled} emails."
    )
