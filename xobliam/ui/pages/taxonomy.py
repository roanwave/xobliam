"""Taxonomy page for Streamlit UI."""

import streamlit as st
import pandas as pd
import plotly.express as px

from xobliam.taxonomy import (
    SENDER_TYPES,
    get_category_stats,
    get_category_senders,
    get_unlabeled_taxonomy,
)
from xobliam.taxonomy.rules import CATEGORY_ACTIONS
from xobliam.fetcher import MessageCache


def render():
    """Render the taxonomy page."""
    st.title("Email Taxonomy")
    st.caption("Classification of your emails by sender type")

    # Load data
    cache = MessageCache()
    messages = cache.get_cached_messages(since_days=90)

    if not messages:
        st.warning("No email data available. Click 'Refresh Data' in the sidebar.")
        return

    # Get category stats
    stats = get_category_stats(messages)

    # Summary metrics
    total = sum(data["count"] for data in stats.values())

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Emails", f"{total:,}")

    with col2:
        categories_used = len([c for c, d in stats.items() if d["count"] > 0])
        st.metric("Categories", categories_used)

    with col3:
        # Most common category
        if stats:
            top_cat = max(stats.items(), key=lambda x: x[1]["count"])
            st.metric("Top Category", top_cat[0].title())

    with col4:
        unknown_pct = (stats.get("unknown", {}).get("count", 0) / total * 100) if total > 0 else 0
        st.metric("Unclassified", f"{unknown_pct:.1f}%")

    st.divider()

    # Category breakdown
    st.subheader("Category Distribution")

    # Prepare data for chart
    chart_data = [
        {
            "category": cat.title(),
            "count": data["count"],
            "read_rate": data["read_rate"],
        }
        for cat, data in stats.items()
        if data["count"] > 0
    ]

    if chart_data:
        df = pd.DataFrame(chart_data)
        df = df.sort_values("count", ascending=True)

        fig = px.bar(
            df,
            x="count",
            y="category",
            orientation="h",
            color="read_rate",
            color_continuous_scale="RdYlGn",
            labels={"count": "Emails", "category": "", "read_rate": "Read Rate (%)"},
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, width="stretch")

    # Detailed breakdown by category
    st.subheader("Category Details")

    # Sort categories by count
    sorted_cats = sorted(
        [(cat, data) for cat, data in stats.items() if data["count"] > 0],
        key=lambda x: x[1]["count"],
        reverse=True,
    )

    for category, data in sorted_cats:
        with st.expander(
            f"**{category.title()}** - {data['count']:,} emails "
            f"({data['read_rate']:.1f}% read)"
        ):
            # Description
            st.caption(data.get("description", SENDER_TYPES.get(category, {}).get("description", "")))

            # Metrics
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Total", f"{data['count']:,}")

            with col2:
                st.metric("Read", f"{data['read']:,}")

            with col3:
                st.metric("Unread", f"{data['unread']:,}")

            # Top senders in this category
            if data.get("top_senders"):
                st.write("**Top senders:**")
                for sender in data["top_senders"][:5]:
                    st.write(f"- {sender}")

            # Sample subjects
            if data.get("sample_subjects"):
                st.write("**Sample subjects:**")
                for subject in data["sample_subjects"][:3]:
                    if subject:
                        st.write(f"- {subject[:70]}...")

            # Recommended actions
            actions = CATEGORY_ACTIONS.get(category, {})
            if actions:
                st.write("**Recommended actions:**")
                for action, description in actions.items():
                    st.write(f"- **{action.title()}:** {description}")

    st.divider()

    # Unlabeled email analysis
    st.subheader("Unlabeled Email Analysis")

    unlabeled = get_unlabeled_taxonomy(messages)

    st.metric("Unlabeled Emails", f"{unlabeled['total_unlabeled']:,}")

    if unlabeled["categories"]:
        st.write("**Breakdown of unlabeled emails:**")

        unlabeled_data = [
            {"category": cat.title(), "count": data["count"]}
            for cat, data in unlabeled["categories"].items()
            if data["count"] > 0
        ]

        if unlabeled_data:
            ul_df = pd.DataFrame(unlabeled_data)

            fig = px.pie(
                ul_df,
                names="category",
                values="count",
                hole=0.4,
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, width="stretch")

    # Drill-down by category
    st.subheader("Explore Category")

    selected_category = st.selectbox(
        "Select category to explore",
        [cat for cat in stats.keys() if stats[cat]["count"] > 0],
        format_func=lambda x: f"{x.title()} ({stats[x]['count']} emails)",
    )

    if selected_category:
        senders = get_category_senders(messages, selected_category, top_n=20)

        if senders:
            st.write(f"**Top senders in {selected_category.title()}:**")

            sender_df = pd.DataFrame(senders)
            sender_df = sender_df[["sender", "count", "read_rate"]]
            sender_df.columns = ["Sender", "Emails", "Read Rate (%)"]

            st.dataframe(
                sender_df,
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
