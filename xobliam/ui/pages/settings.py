"""Settings/Admin page for Streamlit UI."""

import json
import streamlit as st
from datetime import datetime

from xobliam.analytics import (
    analyze_time_patterns,
    calculate_open_rate,
    find_redundant_labels,
    get_day_of_week_distribution,
    get_frequent_senders,
    get_label_stats,
)
from xobliam.auth.credentials import load_credentials
from xobliam.fetcher import MessageCache
from xobliam.smart_delete import get_deletion_summary
from xobliam.taxonomy import get_category_stats


def render():
    """Render the settings page."""
    st.title("Settings")
    st.caption("Account management and data operations")

    # Tabs for different settings
    tab1, tab2, tab3 = st.tabs(["Account", "Data Management", "Export"])

    with tab1:
        render_account()

    with tab2:
        render_data_management()

    with tab3:
        render_export()


def render_account():
    """Render account settings."""
    st.subheader("Gmail Account")

    creds = load_credentials()

    if creds and creds.valid:
        st.success("Gmail account connected")

        # Show account info
        try:
            from xobliam.auth import get_gmail_service

            service = get_gmail_service()
            profile = service.users().getProfile(userId="me").execute()

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Email", profile.get("emailAddress", "Unknown"))
            with col2:
                st.metric("Total Messages", f"{profile.get('messagesTotal', 0):,}")

        except Exception as e:
            st.warning(f"Could not fetch account info: {e}")

        st.divider()

        # Re-authenticate option
        st.subheader("Re-authenticate")
        st.caption(
            "Use this if you want to connect a different Gmail account "
            "or if you're having authentication issues."
        )

        if st.button("Re-authenticate", type="secondary"):
            if st.session_state.get("confirm_reauth"):
                with st.spinner("Revoking credentials..."):
                    from xobliam.auth import revoke_credentials

                    revoke_credentials()
                    st.success("Credentials revoked. Please authenticate again.")
                    st.session_state["confirm_reauth"] = False
                    st.rerun()
            else:
                st.session_state["confirm_reauth"] = True
                st.warning("Click again to confirm re-authentication.")

    else:
        st.warning("Gmail account not connected")

        if st.button("Connect Gmail", type="primary"):
            with st.spinner("Opening browser for authentication..."):
                try:
                    from xobliam.auth import get_gmail_service

                    service = get_gmail_service()
                    profile = service.users().getProfile(userId="me").execute()
                    st.success(f"Connected as: {profile.get('emailAddress')}")
                    st.rerun()
                except FileNotFoundError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Authentication failed: {e}")


def render_data_management():
    """Render data management options."""
    cache = MessageCache()

    # Cache info
    st.subheader("Cache Information")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Cached Messages", f"{cache.get_message_count():,}")

    with col2:
        labels = cache.get_cached_labels()
        st.metric("Cached Labels", len(labels))

    with col3:
        if cache.is_fresh():
            st.metric("Cache Status", "Fresh")
        else:
            st.metric("Cache Status", "Stale")

    st.divider()

    # Refresh data
    st.subheader("Refresh Data")
    st.caption("Fetch the latest emails from Gmail.")

    col1, col2 = st.columns([1, 2])

    with col1:
        days = st.number_input(
            "Days to fetch",
            min_value=7,
            max_value=365,
            value=90,
            step=30,
        )

    with col2:
        st.write("")  # Spacing
        st.write("")
        if st.button("Refresh Data", type="primary", key="refresh_data"):
            _fetch_with_progress(days)

    st.divider()

    # Clear cache
    st.subheader("Clear Cache")
    st.caption(
        "Delete all cached data. You'll need to fetch emails again after clearing."
    )

    if st.button("Clear Cache", type="secondary"):
        if st.session_state.get("confirm_clear"):
            cache.clear()
            st.success("Cache cleared!")
            st.session_state["confirm_clear"] = False
            st.rerun()
        else:
            st.session_state["confirm_clear"] = True
            st.warning("Click again to confirm clearing the cache.")


def render_export():
    """Render export options."""
    st.subheader("Export Analytics")
    st.caption("Download your email analytics as a JSON file.")

    cache = MessageCache()
    messages = cache.get_cached_messages(since_days=90)

    if not messages:
        st.warning("No data to export. Fetch emails first.")
        return

    # Export options
    col1, col2 = st.columns(2)

    with col1:
        days = st.number_input(
            "Days to include",
            min_value=7,
            max_value=365,
            value=90,
            step=30,
            key="export_days",
        )

    with col2:
        include_raw = st.checkbox(
            "Include raw message data",
            value=False,
            help="Include full message metadata (larger file size)",
        )

    if st.button("Generate Export", type="primary"):
        with st.spinner("Generating analytics export..."):
            messages = cache.get_cached_messages(since_days=days)
            all_labels = cache.get_cached_labels()

            # Build export data
            export_data = {
                "generated_at": datetime.utcnow().isoformat(),
                "days_analyzed": days,
                "message_count": len(messages),
                "analytics": {
                    "open_rate": calculate_open_rate(messages),
                    "time_patterns": analyze_time_patterns(messages),
                    "day_distribution": get_day_of_week_distribution(messages),
                    "top_senders": get_frequent_senders(messages, top_n=50),
                    "label_stats": get_label_stats(messages, all_labels=all_labels),
                    "category_stats": get_category_stats(messages),
                    "redundant_labels": find_redundant_labels(messages),
                    "deletion_summary": get_deletion_summary(messages),
                },
            }

            if include_raw:
                # Sanitize messages for export (remove sets)
                sanitized = []
                for msg in messages:
                    sanitized.append({
                        k: v for k, v in msg.items()
                        if not isinstance(v, set)
                    })
                export_data["messages"] = sanitized

            # Convert to JSON
            json_str = json.dumps(export_data, indent=2, default=str)

            st.success("Export ready!")

            # Download button
            st.download_button(
                label="Download JSON",
                data=json_str,
                file_name=f"xobliam_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
            )

            # Preview
            with st.expander("Preview export"):
                st.json(export_data["analytics"]["open_rate"])
                st.caption("(Showing open rate summary only)")


def _fetch_with_progress(days: int):
    """Fetch emails with progress bar."""
    from xobliam.fetcher import fetch_messages, fetch_labels

    progress_bar = st.progress(0, text="Initializing...")
    status_text = st.empty()

    def update_progress(current: int, total: int):
        pct = min(1.0, current / total) if total > 0 else 0
        progress_bar.progress(pct, text=f"Fetching messages... ({current:,}/{total:,})")

    try:
        status_text.text("Fetching messages from Gmail...")
        messages = fetch_messages(
            days=days,
            use_cache=False,
            progress_callback=update_progress,
        )

        progress_bar.progress(0.9, text="Fetching labels...")
        status_text.text("Fetching labels...")

        labels = fetch_labels(use_cache=False)

        progress_bar.progress(1.0, text="Complete!")
        status_text.empty()

        st.success(f"Fetched {len(messages):,} messages and {len(labels)} labels!")
        st.rerun()

    except FileNotFoundError as e:
        progress_bar.empty()
        status_text.empty()
        st.error(str(e))
    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"Failed to fetch: {e}")
