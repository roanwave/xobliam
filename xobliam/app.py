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
from xobliam.ui.pages import setup, settings


def check_first_run() -> bool:
    """Check if this is a first run (no credentials or no data)."""
    # Skip check if user completed setup
    if st.session_state.get("setup_complete"):
        return False

    from xobliam.auth.credentials import load_credentials
    from xobliam.fetcher import MessageCache

    # Check credentials
    creds = load_credentials()
    has_credentials = creds is not None and creds.valid

    # Check cache
    cache = MessageCache()
    has_data = cache.get_message_count() > 0

    return not (has_credentials and has_data)


def main():
    """Main Streamlit app."""
    # Check if first run - show setup wizard
    if check_first_run():
        setup.render()
        return

    # Sidebar navigation
    st.sidebar.title("xobliam")
    st.sidebar.caption("Gmail Analytics Dashboard")

    # Navigation
    page = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "Analytics", "Labels", "Taxonomy", "Smart Delete", "Settings"],
        label_visibility="collapsed",
    )

    st.sidebar.divider()

    # Quick actions
    st.sidebar.subheader("Quick Actions")

    if st.sidebar.button("Refresh Data", key="sidebar_refresh"):
        _refresh_data_with_progress()

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
        "xobliam v1.0.0\n\n"
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
    elif page == "Settings":
        settings.render()


def _refresh_data_with_progress():
    """Refresh data with progress indicator."""
    from xobliam.fetcher import fetch_messages, fetch_labels

    progress_bar = st.sidebar.progress(0, text="Starting...")

    def update_progress(current: int, total: int):
        pct = current / total if total > 0 else 0
        progress_bar.progress(pct, text=f"Fetching... ({current:,}/{total:,})")

    try:
        fetch_messages(use_cache=False, progress_callback=update_progress)
        progress_bar.progress(0.9, text="Fetching labels...")
        fetch_labels(use_cache=False)
        progress_bar.progress(1.0, text="Complete!")
        st.sidebar.success("Data refreshed!")
        st.rerun()
    except FileNotFoundError as e:
        progress_bar.empty()
        st.sidebar.error(str(e))
    except Exception as e:
        progress_bar.empty()
        st.sidebar.error(f"Error: {e}")


if __name__ == "__main__":
    main()
