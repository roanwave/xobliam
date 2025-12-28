"""Setup wizard page for first-run experience."""

import streamlit as st

from xobliam.auth.credentials import load_credentials
from xobliam.fetcher import MessageCache


def check_setup_complete() -> dict:
    """
    Check if initial setup is complete.

    Returns:
        Dictionary with setup status for each step.
    """
    # Check credentials
    creds = load_credentials()
    has_credentials = creds is not None and creds.valid

    # Check cache
    cache = MessageCache()
    has_data = cache.get_message_count() > 0

    return {
        "has_credentials": has_credentials,
        "has_data": has_data,
        "complete": has_credentials and has_data,
    }


def render():
    """Render the setup wizard."""
    st.title("Welcome to xobliam")
    st.caption("Let's get you set up in just a few steps")

    status = check_setup_complete()

    # Progress indicator
    steps_complete = sum([status["has_credentials"], status["has_data"]])
    st.progress(steps_complete / 2, text=f"Step {steps_complete + 1} of 2")

    st.divider()

    # Step 1: Connect Gmail
    st.subheader("Step 1: Connect Gmail")

    if status["has_credentials"]:
        st.success("Gmail connected!")

        # Show connected account info
        try:
            from xobliam.auth import get_gmail_service

            service = get_gmail_service()
            profile = service.users().getProfile(userId="me").execute()
            st.info(f"Connected as: **{profile.get('emailAddress')}**")
        except Exception:
            pass
    else:
        st.warning("You need to connect your Gmail account to continue.")

        st.markdown("""
        **Before you begin:**
        1. Make sure you have a `credentials.json` file from Google Cloud Console
        2. Place it in the project root directory
        3. Click the button below to authenticate
        """)

        if st.button("Connect Gmail", type="primary", key="connect_gmail"):
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

    st.divider()

    # Step 2: Fetch Emails
    st.subheader("Step 2: Fetch Your Emails")

    if not status["has_credentials"]:
        st.info("Complete Step 1 first to fetch your emails.")
    elif status["has_data"]:
        cache = MessageCache()
        count = cache.get_message_count()
        st.success(f"Email data loaded! ({count:,} messages)")
    else:
        st.warning("No email data found. Let's fetch your emails.")

        days = st.slider(
            "How many days of email history?",
            min_value=30,
            max_value=365,
            value=90,
            step=30,
        )

        if st.button("Fetch Emails", type="primary", key="fetch_emails"):
            _fetch_with_progress(days)

    st.divider()

    # Completion
    if status["complete"]:
        st.success("Setup complete! You're ready to use xobliam.")

        if st.button("Go to Dashboard", type="primary", key="go_dashboard"):
            st.session_state["setup_complete"] = True
            st.rerun()
    else:
        st.info("Complete the steps above to start using xobliam.")


def _fetch_with_progress(days: int):
    """Fetch emails with progress bar."""
    from xobliam.fetcher import fetch_messages, fetch_labels

    progress_bar = st.progress(0, text="Initializing...")
    status_text = st.empty()

    def update_progress(current: int, total: int):
        pct = current / total if total > 0 else 0
        progress_bar.progress(pct, text=f"Fetching messages... ({current:,}/{total:,})")

    try:
        # Fetch messages
        status_text.text("Fetching messages from Gmail...")
        messages = fetch_messages(
            days=days,
            use_cache=False,
            progress_callback=update_progress,
        )

        progress_bar.progress(0.9, text="Fetching labels...")
        status_text.text("Fetching labels...")

        # Fetch labels
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
