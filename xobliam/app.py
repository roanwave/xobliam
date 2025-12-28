"""Streamlit app entrypoint for xobliam."""

import streamlit as st

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="xobliam - Gmail Analytics",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Import pages
from xobliam.ui.pages import (
    dashboard,
    analytics,
    labels,
    taxonomy,
    smart_delete,
)


def main():
    """Main Streamlit app."""
    # Sidebar navigation
    st.sidebar.title("xobliam")
    st.sidebar.caption("Gmail Analytics Dashboard")

    # Navigation
    page = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "Analytics", "Labels", "Taxonomy", "Smart Delete"],
        label_visibility="collapsed",
    )

    st.sidebar.divider()

    # Quick actions
    st.sidebar.subheader("Quick Actions")

    if st.sidebar.button("Refresh Data", use_container_width=True):
        with st.spinner("Fetching data..."):
            try:
                from xobliam.fetcher import fetch_messages, fetch_labels

                fetch_messages(use_cache=False)
                fetch_labels(use_cache=False)
                st.sidebar.success("Data refreshed!")
                st.rerun()
            except FileNotFoundError as e:
                st.sidebar.error(str(e))
            except Exception as e:
                st.sidebar.error(f"Error: {e}")

    # Cache info
    from xobliam.fetcher import MessageCache

    cache = MessageCache()
    msg_count = cache.get_message_count()

    st.sidebar.caption(f"Cached messages: {msg_count:,}")

    if cache.is_fresh():
        st.sidebar.caption("Cache: Fresh")
    else:
        st.sidebar.caption("Cache: Stale")

    st.sidebar.divider()

    # About
    st.sidebar.caption(
        "xobliam v0.1.0\n\n"
        "Gmail analytics with intelligent cleanup recommendations."
    )

    # Render selected page
    if page == "Dashboard":
        dashboard.render()
    elif page == "Analytics":
        analytics.render()
    elif page == "Labels":
        labels.render()
    elif page == "Taxonomy":
        taxonomy.render()
    elif page == "Smart Delete":
        smart_delete.render()


if __name__ == "__main__":
    main()
