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
    get_suggestion_summary,
    suggest_new_labels,
)
from xobliam.fetcher import (
    MessageCache,
    apply_label_to_messages,
    create_filter_for_senders,
    create_label,
    delete_filter,
    get_label_id_by_name,
    get_label_name_by_id,
    list_filters,
    merge_labels,
)
from xobliam.smart_delete import filter_unlabeled_messages


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
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "Health Summary",
        "All Labels",
        "Label Details",
        "Coherence",
        "Engagement",
        "Overlap & Merge",
        "Label Manager",
        "Suggestions",
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

    with tab7:
        render_label_manager(messages, cache)

    with tab8:
        render_label_suggestions(messages, cache)


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
        st.plotly_chart(fig, width="stretch")


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


def render_label_manager(messages: list, cache: MessageCache):
    """Render label manager for creating labels and bulk-applying them."""
    st.subheader("Label Manager")
    st.caption(
        "Create new labels and bulk-apply them to unlabeled emails based on sender patterns."
    )

    # Get existing labels for dropdown
    cached_labels = cache.get_cached_labels()
    user_labels = [l for l in cached_labels if l.get("type") == "user"]
    label_names = sorted([l.get("name", "") for l in user_labels if l.get("name")])

    # Initialize session state for created labels
    if "created_labels" not in st.session_state:
        st.session_state.created_labels = []

    # Section 1: Create New Label
    st.divider()
    st.subheader("Create New Label")

    col1, col2 = st.columns([3, 1])

    with col1:
        new_label_name = st.text_input(
            "Label name",
            placeholder="e.g., Fantasy Sports, Newsletters, Shopping",
            key="new_label_input",
        )

    with col2:
        st.write("")  # Spacer
        st.write("")  # Spacer
        create_btn = st.button("Create Label", type="primary", disabled=not new_label_name)

    if create_btn and new_label_name:
        with st.spinner(f"Creating label '{new_label_name}'..."):
            result = create_label(new_label_name)

        if result["success"]:
            st.success(f"Created label '{result['label_name']}'")
            # Add to session state for use in dropdown
            st.session_state.created_labels.append({
                "name": result["label_name"],
                "label_id": result["label_id"],
            })
            st.info("Refresh data in Settings to see the new label in all views.")
        else:
            st.error(result.get("error", "Failed to create label"))

    # Section 2: Bulk Apply Label
    st.divider()
    st.subheader("Bulk Apply Label (Smart Labeling)")
    st.caption("Find unlabeled emails matching sender patterns and apply a label to them.")

    # Combine existing labels with newly created ones
    all_label_options = label_names.copy()
    for created in st.session_state.created_labels:
        if created["name"] not in all_label_options:
            all_label_options.append(created["name"])
    all_label_options = sorted(all_label_options)

    if not all_label_options:
        st.info("No labels available. Create a label first.")
        return

    # Label selection
    selected_label = st.selectbox(
        "Select label to apply",
        all_label_options,
        key="bulk_apply_label",
    )

    # Get label ID
    selected_label_id = None
    for created in st.session_state.created_labels:
        if created["name"] == selected_label:
            selected_label_id = created["label_id"]
            break
    if not selected_label_id:
        selected_label_id = get_label_id_by_name(selected_label, cache=cache)

    # Sender pattern input
    st.write("**Find emails by sender pattern:**")
    sender_pattern = st.text_input(
        "Senders containing (comma-separated)",
        placeholder="e.g., yahoo sports, fantasypros, espn, nfl",
        key="sender_pattern_input",
        help="Enter comma-separated terms to match sender addresses (case-insensitive, partial match)",
    )

    # Subject pattern input (optional)
    with st.expander("Advanced: Filter by subject (optional)"):
        subject_pattern = st.text_input(
            "Subject containing",
            placeholder="e.g., newsletter, weekly update",
            key="subject_pattern_input",
            help="Additional filter: only match emails with these terms in subject",
        )

    # Search button
    if st.button("Search Emails", disabled=not sender_pattern):
        # Filter to unlabeled emails only
        unlabeled = filter_unlabeled_messages(messages)

        if not unlabeled:
            st.warning("No unlabeled emails found.")
            return

        # Parse search terms
        terms = [t.strip().lower() for t in sender_pattern.split(",") if t.strip()]

        # Find matching emails
        matching_by_sender = {}
        for msg in unlabeled:
            sender = msg.get("sender", "").lower()
            subject = (msg.get("subject", "") or "").lower()

            # Check if sender matches any term
            matches_sender = any(term in sender for term in terms)

            # Check subject if pattern provided
            if subject_pattern:
                subject_terms = [t.strip().lower() for t in subject_pattern.split(",") if t.strip()]
                matches_subject = any(term in subject for term in subject_terms)
                matches = matches_sender and matches_subject
            else:
                matches = matches_sender

            if matches:
                original_sender = msg.get("sender", "unknown")
                if original_sender not in matching_by_sender:
                    matching_by_sender[original_sender] = []
                matching_by_sender[original_sender].append(msg)

        if not matching_by_sender:
            st.warning(f"No unlabeled emails found matching '{sender_pattern}'")
            return

        # Store results in session state
        st.session_state.search_results = matching_by_sender
        st.session_state.search_label_id = selected_label_id
        st.session_state.search_label_name = selected_label

    # Display search results
    if "search_results" in st.session_state and st.session_state.search_results:
        matching_by_sender = st.session_state.search_results
        total_emails = sum(len(msgs) for msgs in matching_by_sender.values())

        st.divider()
        st.write(f"**Found {total_emails} emails from {len(matching_by_sender)} senders:**")

        # Initialize selected senders in session state
        if "selected_senders" not in st.session_state:
            st.session_state.selected_senders = {s: True for s in matching_by_sender}

        # Ensure all current senders are in selected_senders
        for sender in matching_by_sender:
            if sender not in st.session_state.selected_senders:
                st.session_state.selected_senders[sender] = True

        # Display senders with checkboxes
        selected_count = 0
        selected_emails = 0

        for sender, msgs in sorted(matching_by_sender.items(), key=lambda x: len(x[1]), reverse=True):
            count = len(msgs)
            is_selected = st.checkbox(
                f"{sender} ({count} emails)",
                value=st.session_state.selected_senders.get(sender, True),
                key=f"sender_cb_{sender}",
            )
            st.session_state.selected_senders[sender] = is_selected

            if is_selected:
                selected_count += 1
                selected_emails += count

        st.divider()

        # Apply button
        label_name = st.session_state.get("search_label_name", selected_label)
        label_id = st.session_state.get("search_label_id", selected_label_id)

        if selected_emails > 0:
            # Option to create Gmail filter
            create_filter = st.checkbox(
                "Also create Gmail filter for future emails",
                value=True,
                key="create_filter_checkbox",
                help="Automatically label future emails from these senders",
            )

            # Auto-archive option (only show if filter is checked)
            auto_archive = False
            if create_filter:
                auto_archive = st.checkbox(
                    "Skip inbox (auto-archive)",
                    value=False,
                    key="auto_archive_checkbox",
                    help="Future emails will be labeled but not appear in inbox",
                )

            if st.button(
                f"Apply label '{label_name}' to {selected_emails} emails",
                type="primary",
                key="apply_label_btn",
            ):
                # Collect message IDs and senders to label
                message_ids = []
                selected_sender_emails = []
                for sender, msgs in matching_by_sender.items():
                    if st.session_state.selected_senders.get(sender, False):
                        message_ids.extend([m["message_id"] for m in msgs])
                        selected_sender_emails.append(sender)

                # Apply label with progress
                with st.spinner(f"Applying label '{label_name}'..."):
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    def update_progress(current, total):
                        progress_bar.progress(min(1.0, current / total))
                        status_text.text(f"Labeling {current}/{total} emails...")

                    result = apply_label_to_messages(
                        message_ids=message_ids,
                        label_id=label_id,
                        progress_callback=update_progress,
                    )

                    progress_bar.empty()
                    status_text.empty()

                if result["success"]:
                    st.success(
                        f"Applied label '{label_name}' to {result['messages_labeled']} emails!"
                    )

                    # Create Gmail filter if requested
                    if create_filter and selected_sender_emails:
                        with st.spinner("Creating Gmail filter..."):
                            filter_result = create_filter_for_senders(
                                senders=selected_sender_emails,
                                label_id=label_id,
                                auto_archive=auto_archive,
                            )

                        if filter_result["success"]:
                            archive_msg = " and archived" if auto_archive else ""
                            st.success(
                                f"Created filter: Future emails from {filter_result['senders_count']} "
                                f"senders will automatically be labeled '{label_name}'{archive_msg}"
                            )
                        else:
                            st.warning(
                                f"Could not create filter: {filter_result.get('error', 'Unknown error')}"
                            )

                    st.info("Refresh data in Settings to see the updated labels.")
                    # Clear search results
                    del st.session_state.search_results
                    if "selected_senders" in st.session_state:
                        del st.session_state.selected_senders
                else:
                    st.error(f"Failed to apply label: {result.get('errors', 'Unknown error')}")
        else:
            st.info("Select at least one sender to apply the label.")

    # Manage Filters section
    st.divider()
    st.subheader("Manage Gmail Filters")
    st.caption("View and manage filters that auto-label incoming emails.")

    if st.button("Load Filters", key="load_filters_btn"):
        st.session_state.show_filters = True

    if st.session_state.get("show_filters", False):
        with st.spinner("Loading filters..."):
            filters_result = list_filters()

        if not filters_result["success"]:
            st.error(f"Could not load filters: {filters_result.get('error', 'Unknown error')}")
        elif filters_result["count"] == 0:
            st.info("No Gmail filters found.")
        else:
            st.write(f"Found **{filters_result['count']} filters**")

            for f in filters_result["filters"]:
                filter_id = f["filter_id"]
                from_criteria = f["from"] or "(no sender criteria)"

                # Get label names for display
                add_labels = []
                for label_id in f["add_labels"]:
                    label_name = get_label_name_by_id(label_id, cache=cache)
                    add_labels.append(label_name or label_id)

                remove_labels = []
                for label_id in f["remove_labels"]:
                    label_name = get_label_name_by_id(label_id, cache=cache)
                    remove_labels.append(label_name or label_id)

                # Build action description
                actions = []
                if add_labels:
                    actions.append(f"Label: {', '.join(add_labels)}")
                if remove_labels:
                    actions.append(f"Remove: {', '.join(remove_labels)}")
                if f["forward"]:
                    actions.append(f"Forward to: {f['forward']}")

                action_str = " | ".join(actions) if actions else "(no actions)"

                # Truncate long from criteria for display
                from_display = from_criteria[:60] + "..." if len(from_criteria) > 60 else from_criteria

                col1, col2 = st.columns([5, 1])

                with col1:
                    with st.expander(f"From: {from_display}"):
                        st.write(f"**Full criteria:** {from_criteria}")
                        st.write(f"**Actions:** {action_str}")
                        st.caption(f"Filter ID: {filter_id}")

                with col2:
                    if st.button("Delete", key=f"delete_filter_{filter_id}", type="secondary"):
                        delete_result = delete_filter(filter_id)
                        if delete_result["success"]:
                            st.success("Filter deleted!")
                            st.session_state.show_filters = False  # Trigger reload
                            st.rerun()
                        else:
                            st.error(f"Failed: {delete_result.get('error', 'Unknown')}")


def render_label_suggestions(messages: list, cache: MessageCache):
    """Render smart label suggestions for unlabeled emails."""
    st.subheader("Smart Label Suggestions")
    st.caption(
        "Automatically suggest existing labels for unlabeled emails based on sender "
        "patterns, domains, and subject keywords from your labeled emails."
    )

    # Get suggestions summary
    with st.spinner("Analyzing email patterns..."):
        summary = get_suggestion_summary(messages, min_score=35)

    if summary["total_suggestions"] == 0:
        st.info(
            "No label suggestions found. This can happen if:\n"
            "- You have few unlabeled emails\n"
            "- Your labeled emails don't have clear sender patterns\n"
            "- Unlabeled emails don't match your existing labels"
        )
        return

    # Summary metrics
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Emails with Suggestions", summary["total_suggestions"])

    with col2:
        st.metric("Labels Matched", summary["label_count"])

    st.divider()

    # Initialize session state for selections
    if "suggestion_selections" not in st.session_state:
        st.session_state.suggestion_selections = {}

    # Display suggestions by label
    for label_name, label_data in summary["labels"].items():
        with st.expander(
            f"**{label_name}** - {label_data['total_matches']} emails from "
            f"{label_data['unique_senders']} senders",
            expanded=True if label_data["total_matches"] <= 20 else False,
        ):
            # Initialize selections for this label
            if label_name not in st.session_state.suggestion_selections:
                st.session_state.suggestion_selections[label_name] = {
                    "senders": {},
                    "select_all": True,
                }

            # Select all checkbox for this label
            select_all = st.checkbox(
                "Select all senders",
                value=st.session_state.suggestion_selections[label_name].get("select_all", True),
                key=f"select_all_{label_name}",
            )
            st.session_state.suggestion_selections[label_name]["select_all"] = select_all

            st.divider()

            # Display senders with checkboxes
            selected_count = 0
            selected_emails = 0
            selected_message_ids = []

            for sender_info in label_data["senders"]:
                sender = sender_info["sender"]
                count = sender_info["count"]
                reasons = sender_info.get("reasons", [])
                message_ids = sender_info.get("message_ids", [])

                # Initialize sender selection based on select_all
                if sender not in st.session_state.suggestion_selections[label_name]["senders"]:
                    st.session_state.suggestion_selections[label_name]["senders"][sender] = select_all

                # Override with select_all if it was just changed
                if f"select_all_{label_name}" in st.session_state:
                    st.session_state.suggestion_selections[label_name]["senders"][sender] = select_all

                is_selected = st.checkbox(
                    f"{sender[:50]} ({count} emails)",
                    value=st.session_state.suggestion_selections[label_name]["senders"].get(sender, True),
                    key=f"sender_{label_name}_{sender}",
                    help=", ".join(reasons) if reasons else None,
                )
                st.session_state.suggestion_selections[label_name]["senders"][sender] = is_selected

                if is_selected:
                    selected_count += 1
                    selected_emails += count
                    selected_message_ids.extend(message_ids)

            st.divider()

            # Apply button for this label
            if selected_emails > 0:
                label_id = get_label_id_by_name(label_name, cache=cache)

                if not label_id:
                    st.warning(f"Could not find label ID for '{label_name}'. Try refreshing data.")
                else:
                    if st.button(
                        f"Apply '{label_name}' to {selected_emails} emails",
                        type="primary",
                        key=f"apply_suggestion_{label_name}",
                    ):
                        with st.spinner(f"Applying label '{label_name}'..."):
                            progress_bar = st.progress(0)
                            status_text = st.empty()

                            def update_progress(current, total):
                                progress_bar.progress(min(1.0, current / total))
                                status_text.text(f"Labeling {current}/{total} emails...")

                            result = apply_label_to_messages(
                                message_ids=selected_message_ids,
                                label_id=label_id,
                                progress_callback=update_progress,
                            )

                            progress_bar.empty()
                            status_text.empty()

                        if result["success"]:
                            st.success(
                                f"Applied label '{label_name}' to {result['messages_labeled']} emails!"
                            )
                            # Clear selections for this label
                            if label_name in st.session_state.suggestion_selections:
                                del st.session_state.suggestion_selections[label_name]
                            st.info("Refresh data in Settings to see updated labels, then revisit this tab.")
                        else:
                            st.error(f"Failed: {result.get('errors', 'Unknown error')}")
            else:
                st.info("Select at least one sender to apply this label.")

    st.divider()

    # Bulk apply all suggestions button
    st.subheader("Bulk Apply All")
    st.caption("Apply all selected suggestions at once.")

    # Count total selected across all labels
    total_selected = 0
    for label_name, label_data in summary["labels"].items():
        if label_name in st.session_state.suggestion_selections:
            for sender_info in label_data["senders"]:
                sender = sender_info["sender"]
                if st.session_state.suggestion_selections[label_name]["senders"].get(sender, True):
                    total_selected += sender_info["count"]

    if total_selected > 0:
        if st.button(
            f"Apply All Selected ({total_selected} emails across {summary['label_count']} labels)",
            type="primary",
            key="apply_all_suggestions",
        ):
            success_count = 0
            error_count = 0

            progress_bar = st.progress(0)
            status_text = st.empty()

            label_list = list(summary["labels"].items())
            for i, (label_name, label_data) in enumerate(label_list):
                status_text.text(f"Processing label '{label_name}'...")

                label_id = get_label_id_by_name(label_name, cache=cache)
                if not label_id:
                    error_count += 1
                    continue

                # Collect selected message IDs for this label
                message_ids = []
                for sender_info in label_data["senders"]:
                    sender = sender_info["sender"]
                    if (
                        label_name in st.session_state.suggestion_selections
                        and st.session_state.suggestion_selections[label_name]["senders"].get(sender, True)
                    ):
                        message_ids.extend(sender_info.get("message_ids", []))

                if message_ids:
                    result = apply_label_to_messages(
                        message_ids=message_ids,
                        label_id=label_id,
                    )
                    if result["success"]:
                        success_count += result["messages_labeled"]
                    else:
                        error_count += 1

                progress_bar.progress((i + 1) / len(label_list))

            progress_bar.empty()
            status_text.empty()

            if success_count > 0:
                st.success(f"Applied labels to {success_count} emails!")
                # Clear all selections
                st.session_state.suggestion_selections = {}
                st.info("Refresh data in Settings to see updated labels.")
            if error_count > 0:
                st.warning(f"{error_count} label(s) had errors during application.")
    else:
        st.info("Select some suggestions above to enable bulk apply.")
