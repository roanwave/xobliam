"""Dashboard page for Streamlit UI."""

import streamlit as st

from xobliam.analytics import (
    analyze_time_patterns,
    calculate_open_rate,
    get_day_of_week_distribution,
    get_frequent_senders,
)
from xobliam.fetcher import MessageCache
from xobliam.smart_delete import get_deletion_summary


def render():
    """Render the dashboard page."""
    st.title("Dashboard")
    st.caption("Overview of your email analytics")

    # Load data
    cache = MessageCache()
    messages = cache.get_cached_messages(since_days=90)

    if not messages:
        st.warning(
            "No email data available. Click 'Refresh Data' in the sidebar to fetch emails."
        )
        return

    # Summary metrics
    open_rate = calculate_open_rate(messages)
    dow = get_day_of_week_distribution(messages)
    patterns = analyze_time_patterns(messages)
    deletion_summary = get_deletion_summary(messages)

    # Top row metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Emails", f"{open_rate['total']:,}")

    with col2:
        st.metric("Open Rate", f"{open_rate['open_rate']:.1f}%")

    with col3:
        st.metric("Busiest Day", dow["busiest_day"])

    with col4:
        st.metric(
            "Deletable",
            f"{deletion_summary['deletable']:,}",
            help="Messages safe to delete (score >= 70)",
        )

    st.divider()

    # Two column layout
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Email Health")

        # Read/unread breakdown
        import plotly.express as px

        fig = px.pie(
            names=["Read", "Unread"],
            values=[open_rate["read"], open_rate["unread"]],
            color_discrete_sequence=["#00CC96", "#EF553B"],
            hole=0.4,
        )
        fig.update_layout(showlegend=True, height=300)
        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            f"You've read {open_rate['read']:,} of {open_rate['total']:,} emails"
        )

    with col2:
        st.subheader("Day of Week Distribution")

        import plotly.express as px
        import pandas as pd

        dow_data = pd.DataFrame(dow["distribution"])
        fig = px.bar(
            dow_data,
            x="day_name",
            y="count",
            color="count",
            color_continuous_scale="Blues",
        )
        fig.update_layout(
            xaxis_title="",
            yaxis_title="Emails",
            coloraxis_showscale=False,
            height=300,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Top senders
    st.subheader("Top Senders")

    senders = get_frequent_senders(messages, top_n=10)

    if senders:
        import pandas as pd

        df = pd.DataFrame(senders)[["sender", "count", "read_rate"]]
        df.columns = ["Sender", "Emails", "Read Rate (%)"]
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Read Rate (%)": st.column_config.ProgressColumn(
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                ),
            },
        )

    st.divider()

    # Quick insights
    st.subheader("Quick Insights")

    insights_col1, insights_col2 = st.columns(2)

    with insights_col1:
        st.info(
            f"**Peak Activity:** {patterns['peak_day']} at {patterns['peak_hour']:02d}:00 "
            f"({patterns['peak_count']} emails)"
        )

        if dow["weekday_avg"] > 0:
            ratio = dow["weekend_avg"] / dow["weekday_avg"]
            if ratio < 0.5:
                st.success("Your inbox is relatively quiet on weekends")
            else:
                st.warning("You receive significant email on weekends too")

    with insights_col2:
        if open_rate["open_rate"] > 80:
            st.success(f"Great inbox engagement at {open_rate['open_rate']:.1f}%!")
        elif open_rate["open_rate"] > 50:
            st.info(
                f"Moderate engagement ({open_rate['open_rate']:.1f}%). "
                "Consider using Smart Delete to clean up."
            )
        else:
            st.warning(
                f"Low engagement ({open_rate['open_rate']:.1f}%). "
                "You may want to unsubscribe from some senders."
            )

        if deletion_summary["deletable"] > 100:
            st.info(
                f"Found {deletion_summary['deletable']} emails safe to delete. "
                "Check the Smart Delete page."
            )
