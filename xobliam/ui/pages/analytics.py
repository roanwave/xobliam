"""Analytics page for Streamlit UI."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from xobliam.analytics import (
    analyze_time_patterns,
    calculate_open_rate,
    get_busiest_dates,
    get_calendar_distribution,
    get_day_hourly_breakdown,
    get_day_of_week_distribution,
    get_frequent_senders,
    get_sender_domains,
    get_sender_engagement,
)
from xobliam.fetcher import MessageCache


def render():
    """Render the analytics page."""
    st.title("Analytics")
    st.caption("Detailed email patterns and statistics")

    # Load data
    cache = MessageCache()
    messages = cache.get_cached_messages(since_days=90)

    if not messages:
        st.warning("No email data available. Click 'Refresh Data' in the sidebar.")
        return

    # Tabs for different analytics
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Time Patterns", "Day Breakdown", "Sender Analysis", "Daily Distribution", "Engagement"]
    )

    with tab1:
        render_time_patterns(messages)

    with tab2:
        render_day_breakdown(messages)

    with tab3:
        render_sender_analysis(messages)

    with tab4:
        render_daily_distribution(messages)

    with tab5:
        render_engagement(messages)


def render_time_patterns(messages: list):
    """Render time pattern analysis."""
    st.subheader("Email Activity Heatmap")

    patterns = analyze_time_patterns(messages)
    matrix = patterns["matrix"]
    day_names = patterns["day_names"]

    # Create heatmap
    fig = go.Figure(
        data=go.Heatmap(
            z=matrix,
            x=list(range(24)),
            y=day_names,
            colorscale="Blues",
            hoverongaps=False,
            hovertemplate="Day: %{y}<br>Hour: %{x}:00<br>Emails: %{z}<extra></extra>",
        )
    )

    fig.update_layout(
        xaxis_title="Hour of Day",
        yaxis_title="",
        xaxis=dict(tickmode="linear", tick0=0, dtick=2),
        height=400,
    )

    st.plotly_chart(fig, width="stretch")

    # Peak info
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Peak Day", patterns["peak_day"])

    with col2:
        st.metric("Peak Hour", f"{patterns['peak_hour']:02d}:00")

    with col3:
        st.metric("Peak Count", patterns["peak_count"])

    # Hourly totals
    st.subheader("Hourly Distribution")

    hourly_data = pd.DataFrame(
        {"hour": list(range(24)), "count": patterns["hour_totals"]}
    )

    fig = px.bar(
        hourly_data,
        x="hour",
        y="count",
        color="count",
        color_continuous_scale="Blues",
    )
    fig.update_layout(
        xaxis_title="Hour",
        yaxis_title="Emails",
        coloraxis_showscale=False,
        height=300,
    )
    st.plotly_chart(fig, width="stretch")


def render_day_breakdown(messages: list):
    """Render per-day hourly breakdown with focus mode suggestions."""
    st.subheader("Daily Hourly Breakdown")
    st.caption(
        "See email activity by hour for each day of the week, and find your best focus time."
    )

    # Day selector
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    selected_day = st.selectbox(
        "Select a day",
        day_names,
        key="day_breakdown_selector",
    )

    # Get breakdown for selected day
    breakdown = get_day_hourly_breakdown(messages, day_name=selected_day)

    # Summary metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(f"Total on {selected_day}s", breakdown["total_emails"])

    with col2:
        peak_times = breakdown["peak_times"]
        peak_display = peak_times[0] if peak_times else "N/A"
        st.metric("Peak Period", peak_display)

    with col3:
        quiet_times = breakdown["quiet_times"]
        quiet_display = quiet_times[0] if quiet_times else "N/A"
        st.metric("Quietest Period", quiet_display)

    # Focus mode suggestion
    if breakdown["quiet_times"]:
        st.success(f"🎯 **Focus Mode Suggestion:** {breakdown['focus_mode_suggestion']}")
    else:
        st.info("No clear low-traffic periods identified for this day.")

    st.divider()

    # Hourly bar chart
    st.subheader(f"Hourly Activity on {selected_day}s")

    hourly_counts = breakdown["hourly_counts"]
    hourly_df = pd.DataFrame({
        "Hour": [f"{h:02d}:00" for h in range(24)],
        "Emails": hourly_counts,
    })

    fig = px.bar(
        hourly_df,
        x="Hour",
        y="Emails",
        color="Emails",
        color_continuous_scale="Blues",
    )
    fig.update_layout(
        height=350,
        xaxis_title="Hour of Day",
        yaxis_title="Emails",
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig, width="stretch")

    st.divider()

    # Time blocks table
    st.subheader("Activity by Time Block")

    blocks_data = []
    for block in breakdown["blocks"]:
        status = "🔥 Peak" if block["is_peak"] else ("🌙 Quiet" if block["percentage"] < 10 else "")
        blocks_data.append({
            "Time Block": block["label"],
            "Emails": block["count"],
            "% of Day": block["percentage"],
            "Status": status,
        })

    blocks_df = pd.DataFrame(blocks_data)

    st.dataframe(
        blocks_df,
        width="stretch",
        hide_index=True,
        column_config={
            "% of Day": st.column_config.ProgressColumn(
                min_value=0,
                max_value=100,
                format="%.1f%%",
            ),
        },
    )

    # Compare all days
    st.divider()
    st.subheader("Compare All Days")

    patterns = analyze_time_patterns(messages)
    day_totals = patterns["day_totals"]

    compare_df = pd.DataFrame({
        "Day": day_names,
        "Total Emails": day_totals,
    })

    fig2 = px.bar(
        compare_df,
        x="Day",
        y="Total Emails",
        color="Total Emails",
        color_continuous_scale="Blues",
    )
    fig2.update_layout(height=300, coloraxis_showscale=False)
    st.plotly_chart(fig2, width="stretch")


def render_sender_analysis(messages: list):
    """Render sender analysis."""
    st.subheader("Top Senders by Volume")

    # Controls
    col1, col2 = st.columns([1, 3])
    with col1:
        top_n = st.selectbox("Show top", [10, 20, 50, 100], index=0)

    senders = get_frequent_senders(messages, top_n=top_n)

    if senders:
        df = pd.DataFrame(senders)
        df = df[["sender", "count", "read_rate", "has_attachments_count"]]
        df.columns = ["Sender", "Emails", "Read Rate (%)", "With Attachments"]

        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            height=400,
            column_config={
                "Read Rate (%)": st.column_config.ProgressColumn(
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                ),
            },
        )

    # Domain analysis
    st.subheader("Top Domains")

    domains = get_sender_domains(messages)[:20]

    if domains:
        domain_df = pd.DataFrame(domains)
        domain_df = domain_df[["domain", "count", "unique_senders", "read_rate"]]
        domain_df.columns = ["Domain", "Emails", "Unique Senders", "Read Rate (%)"]

        fig = px.bar(
            domain_df.head(15),
            x="Emails",
            y="Domain",
            orientation="h",
            color="Read Rate (%)",
            color_continuous_scale="RdYlGn",
        )
        fig.update_layout(height=500, yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, width="stretch")


def render_daily_distribution(messages: list):
    """Render daily distribution analysis."""
    st.subheader("Emails by Date")

    calendar = get_calendar_distribution(messages)

    if calendar:
        df = pd.DataFrame(calendar)
        df["date"] = pd.to_datetime(df["date"])

        fig = px.line(
            df,
            x="date",
            y="count",
            markers=True,
        )
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Emails",
            height=400,
        )
        st.plotly_chart(fig, width="stretch")

    # Day of week breakdown
    st.subheader("Weekly Pattern")

    dow = get_day_of_week_distribution(messages)

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Weekday Average", f"{dow['weekday_avg']:.1f} emails/day")

    with col2:
        st.metric("Weekend Average", f"{dow['weekend_avg']:.1f} emails/day")

    # Busiest dates
    st.subheader("Busiest Days")

    busiest = get_busiest_dates(messages, top_n=10)

    if busiest:
        busiest_df = pd.DataFrame(busiest)
        busiest_df = busiest_df[["date", "day_name", "count"]]
        busiest_df.columns = ["Date", "Day", "Emails"]

        st.dataframe(busiest_df, width="stretch", hide_index=True)


def render_engagement(messages: list):
    """Render engagement analysis."""
    st.subheader("Overall Engagement")

    open_rate = calculate_open_rate(messages)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Emails", f"{open_rate['total']:,}")

    with col2:
        st.metric("Read", f"{open_rate['read']:,}")

    with col3:
        st.metric("Unread", f"{open_rate['unread']:,}")

    # Engagement by sender
    st.subheader("Sender Engagement")

    # Filter options
    col1, col2 = st.columns(2)

    with col1:
        min_emails = st.slider("Minimum emails from sender", 1, 50, 5)

    with col2:
        sort_by = st.selectbox("Sort by", ["Volume", "Open Rate (High)", "Open Rate (Low)"])

    engagement = get_sender_engagement(messages)

    # Filter
    engagement = [s for s in engagement if s["total"] >= min_emails]

    # Sort
    if sort_by == "Open Rate (High)":
        engagement = sorted(engagement, key=lambda x: x["open_rate"], reverse=True)
    elif sort_by == "Open Rate (Low)":
        engagement = sorted(engagement, key=lambda x: x["open_rate"])

    if engagement:
        df = pd.DataFrame(engagement[:30])
        df = df[["sender", "total", "read", "unread", "open_rate"]]
        df.columns = ["Sender", "Total", "Read", "Unread", "Open Rate (%)"]

        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            column_config={
                "Open Rate (%)": st.column_config.ProgressColumn(
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                ),
            },
        )

    # Low engagement senders (candidates for unsubscribe)
    st.subheader("Low Engagement Senders")
    st.caption("Senders with low open rates - consider unsubscribing")

    low_engagement = [
        s for s in get_sender_engagement(messages)
        if s["total"] >= 5 and s["open_rate"] < 20
    ]

    if low_engagement:
        le_df = pd.DataFrame(low_engagement[:20])
        le_df = le_df[["sender", "total", "open_rate"]]
        le_df.columns = ["Sender", "Emails", "Open Rate (%)"]

        st.dataframe(le_df, width="stretch", hide_index=True)
    else:
        st.info("No senders with consistently low engagement found.")
