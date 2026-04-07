import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os
import time


# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.vald_client import ValdHubClient

from src.visualizations import create_metrics_comparison_chart, create_limb_asymmetry_charts, create_raw_force_plot
from src.visualizations import create_mean_std_chart, create_left_right_chart, create_overlay_trials_chart

from src.data_prep_funcs import parse_excluded_tests, group_metrics_by_base, normalize_metric_name, split_metric_and_limb, extract_metric_record, extract_available_metrics_from_tests, resolve_category_metrics_for_test_type, build_comparison_df_for_test_trials, find_jump_height_column, prepare_tests_for_comparison, get_all_trial_metric_names, parse_forcedeck_raw_data
from src.data_prep_funcs import detect_movement_onset_events, prepare_overlay_trial, extract_trial_aligned_to_takeoff, find_movement_onset_before_takeoff, detect_takeoff_events, estimate_bodyweight

from src.metric_categories import TEST_TYPE_METRIC_CATEGORIES


APP_VERSION = "1.2"

@st.cache_resource
def get_vald_client():
    """Get cached ValdHubClient instance - persists across Streamlit reruns"""
    return ValdHubClient()


def main():
    st.set_page_config(
        page_title="Vald Hub Dashboard",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown("""
    <style>
    .main {
        padding: 0rem 0rem;
    }

    [data-testid="stMarkdownContainer"] hr {
        margin-top: 0.2rem !important;
        margin-bottom: 0.2rem !important;
    }
    h1 {
        margin-top: 0rem !important;
    }
    </style>
    
    """, unsafe_allow_html=True)

    st.title("Vald Hub Performance Dashboard")
    st.markdown("*Real-time athlete performance monitoring and analysis*")

    with st.sidebar:
        st.header("Configuration")
        client = get_vald_client()

        with st.expander("API Connection Status", expanded=False):
            try:
                api_connected = client.get_token(client.client_id, client.client_secret)

                if api_connected:
                    st.success("✅ Connected to Vald Hub API. ")
                    st.caption(f"App version: {APP_VERSION}")
                else:
                    st.info("Configure `.env` file with your Vald Hub credentials")
            except Exception as e:
                st.error(f"API Error: {str(e)}")

            if st.button("🔄 Refresh Data", width="stretch"):
                if 'data' in st.session_state:
                    del st.session_state.data
                for key in [
                    'profiles_data', 'groups_data', 'athlete_details', 'group_details',
                    'tests_details_all', 'chosen_test_ids', 'selected_metrics',
                    'prepared_comparison_data', 'prepared_summary_data',
                    'graphs_generated', 'use_time_axis', 'excluded_tests_text',
                    'selected_categories', 'resolved_category_metrics',
                    'unmatched_category_metrics', 'use_all_metrics_multi',
                    'overview_selected_test', 'overview_specific_test_details',
                    'overview_current_test_id', 'overview_current_tenant_id',
                    'overview_test_recorded_date', 'overview_test_type', 'show_trendline',
                ]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

        st.divider()

        if 'profiles_data' not in st.session_state:
            st.session_state.profiles_data = client.get_profiles()
        profiles_data = st.session_state.profiles_data

        if 'groups_data' not in st.session_state:
            st.session_state.groups_data = client.get_groups()
        groups_data = st.session_state.groups_data

        st.sidebar.markdown("## Athlete")
        try:
            if 'profiles_data' not in st.session_state:
                st.session_state.profiles_data = client.get_profiles()
            profiles_data = st.session_state.profiles_data

            if profiles_data and 'profiles' in profiles_data:
                athletes = profiles_data['profiles']
                athlete_names = [
                    f"{a.get('familyName', '')} {a.get('givenName', 'Unknown')}"
                    for a in athletes
                ]

                if athlete_names:
                    sorted_athletes = sorted(zip(athlete_names, athletes), key=lambda x: x[0])
                    sorted_athlete_names = [x[0] for x in sorted_athletes]

                    selected_athlete = st.selectbox(
                        " ",
                        sorted_athlete_names,
                        key="athlete_selector",
                        label_visibility="collapsed"
                    )
                    st.session_state.selected_athlete = selected_athlete

                    athlete_obj = next(a for n, a in sorted_athletes if n == selected_athlete)
                    athlete_id = athlete_obj.get('profileId', 'N/A')
                    #st.write(f"**Athlete ID:** {athlete_id}")

                    previous_selected_athlete_id = st.session_state.get("selected_athlete_id_for_context")

                    if previous_selected_athlete_id != athlete_id:
                        keys_to_clear_on_athlete_change = [
                            # tab 1
                            "overview_selected_test",
                            "overview_specific_test_details",
                            "overview_current_test_id",
                            "overview_current_tenant_id",
                            "overview_test_recorded_date",
                            "overview_test_type",
                            "overview_selected_metrics",
                            "overview_selected_categories",
                            "overview_resolved_metrics",
                            "show_trendline",

                            # tab 2
                            "tests_details_all",
                            "chosen_test_ids",
                            "selected_metrics",
                            "prepared_comparison_data",
                            "prepared_summary_data",
                            "graphs_generated",
                            "use_time_axis",
                            "excluded_tests_text",
                            "selected_categories",
                            "resolved_category_metrics",
                            "unmatched_category_metrics",
                            "use_all_metrics_multi",
                        ]

                        for key in keys_to_clear_on_athlete_change:
                            if key in st.session_state:
                                del st.session_state[key]

                    st.session_state.selected_athlete_id_for_context = athlete_id

                    athlete_weight = athlete_obj.get('weight', 'N/A')
                    athlete_date_of_birth = athlete_obj.get('dateOfBirth', 'N/A')

                    col1, col2 = st.columns(2)
                    col1.metric("Weight (kg)", athlete_weight)
                    col2.metric("Date of Birth", athlete_date_of_birth[:10 if athlete_date_of_birth != 'N/A' else None])

                else:
                    st.warning("No athletes found")
            else:
                st.warning("Could not load athletes")
        except Exception as e:
            st.error(f"Error loading athletes: {str(e)}")

        st.divider()

        st.sidebar.markdown("## Settings")
        display_mode = st.radio(
            "Display Mode",
            ["Overview - Single Training", "Multiple trainings comparison", "Comparison across different trials"]
        )

        st.divider()
        st.sidebar.markdown("## Notes / ID storage")

        if "sidebar_id_storage" not in st.session_state:
            st.session_state.sidebar_id_storage = ""

        def clear_sidebar_notes():
            st.session_state.sidebar_id_storage = ""

        st.text_area(
            "Temporary space for test IDs / notes",
            height=180,
            key="sidebar_id_storage",
            placeholder="Paste test IDs or notes here to keep them handy while exploring the data."
        )

        st.button(
            "Clear notes",
            width="stretch",
            on_click=clear_sidebar_notes
        )

    if display_mode == "Overview - Single Training":
        try:
            if "overview_specific_test_details" not in st.session_state:
                st.session_state.overview_specific_test_details = None

            if "overview_current_test_id" not in st.session_state:
                st.session_state.overview_current_test_id = None

            if "overview_current_tenant_id" not in st.session_state:
                st.session_state.overview_current_tenant_id = None

            if "overview_test_recorded_date" not in st.session_state:
                st.session_state.overview_test_recorded_date = None

            if "overview_test_type" not in st.session_state:
                st.session_state.overview_test_type = None

            if "overview_selected_test" not in st.session_state:
                st.session_state.overview_selected_test = None

            if "overview_selected_metrics" not in st.session_state:
                st.session_state.overview_selected_metrics = {}

            if "overview_selected_categories" not in st.session_state:
                st.session_state.overview_selected_categories = {}

            if "overview_resolved_metrics" not in st.session_state:
                st.session_state.overview_resolved_metrics = {}

            st.header("Training Sessions Overview")

            default_from = datetime.now().date() - pd.Timedelta(days=30)
            modified_from = st.date_input(
                "Show sessions from date:",
                value=default_from,
                key="modified_from"
            )

            modified_from_utc = datetime.combine(modified_from, datetime.min.time()).strftime("%Y-%m-%dT%H:%M:%S.000Z")

            st.caption(f"Current filter: date from {modified_from_utc[:10]}")

            data = client.get_training_sessions(
                profile_id=athlete_id,
                modified_from_utc=modified_from_utc,
                page_number=1,
            )

            if data and "tests" in data:
                tests_list = data["tests"]
                if tests_list:
                    df = pd.DataFrame(tests_list)
                    columns_to_show = [
                        "testId", "profileId", "testType", "recordedDateUtc",
                        "analysedDateUtc", "weight", "notes"
                    ]
                    df_display = df.reindex(columns=columns_to_show, fill_value='').copy()
                    df_display.columns = [
                        "Test ID", "Profile ID", "Test Type", "Recorded Date",
                        "Analysed Date", "Weight (kg)", "Notes"
                    ]
                    df_display["Recorded Date"] = pd.to_datetime(
                        df_display["Recorded Date"],
                        format='ISO8601',
                        errors='coerce'
                    ).dt.strftime("%Y-%m-%d %H:%M")
                    df_display["Analysed Date"] = pd.to_datetime(
                        df_display["Analysed Date"],
                        format='ISO8601',
                        errors='coerce'
                    ).dt.strftime("%Y-%m-%d %H:%M")

                    st.dataframe(df_display, width="stretch")

                    st.write(f"**Total sessions:** {len(tests_list)}")

                    st.subheader("Select Test for Details")
                    test_options = [
                        f"{test.get('testType', 'Unknown')} - "
                        f"{pd.to_datetime(test.get('recordedDateUtc'), format='ISO8601', errors='coerce').strftime('%Y-%m-%d %H:%M') if test.get('recordedDateUtc') else 'Unknown Date'} "
                        f"(ID: {test.get('testId', 'N/A')})"
                        for test in tests_list
                    ]

                    selected_test_index = st.selectbox(
                        "Choose a test to view details:",
                        range(len(test_options)),
                        format_func=lambda x: test_options[x],
                        key="test_selector"
                    )

                    if st.button("Get Test Details", key="get_details"):
                        selected_test = tests_list[selected_test_index]
                        tenant_id = selected_test.get('tenantId')
                        test_id = selected_test.get('testId')

                        if tenant_id and test_id:
                            with st.spinner("Loading test details..."):
                                specific_test_details = client.get_test_details(teamId=tenant_id, testId=test_id)

                            if specific_test_details:
                                st.session_state.overview_selected_test = selected_test
                                st.session_state.overview_specific_test_details = specific_test_details
                                st.session_state.overview_current_test_id = test_id
                                st.session_state.overview_current_tenant_id = tenant_id
                                st.session_state.overview_test_recorded_date = selected_test.get('recordedDateUtc')
                                st.session_state.overview_test_type = selected_test.get('testType')

                                # reset selection state for newly loaded test
                                if test_id not in st.session_state.overview_selected_metrics:
                                    st.session_state.overview_selected_metrics[test_id] = []

                                if test_id not in st.session_state.overview_selected_categories:
                                    st.session_state.overview_selected_categories[test_id] = []

                            else:
                                st.error("Failed to load test details.")

                    selected_test_from_state = st.session_state.get("overview_selected_test")
                    specific_test_details = st.session_state.get("overview_specific_test_details")

                    if selected_test_from_state and specific_test_details:
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Test type", st.session_state.get("overview_test_type"))
                        col2.metric(
                            "Number of trials",
                            len(specific_test_details) if isinstance(specific_test_details, list) else 'Unknown'
                        )
                        col3.metric(
                            "Recorded date",
                            pd.to_datetime(
                                st.session_state.get("overview_test_recorded_date"),
                                format='ISO8601',
                                errors='coerce'
                            ).strftime("%Y-%m-%d %H:%M")
                            if st.session_state.get("overview_test_recorded_date") else 'Unknown'
                        )

                        if isinstance(specific_test_details, list) and specific_test_details:
                            st.write(f"**Number of trials:** {len(specific_test_details)}")

                            current_test_id = st.session_state.get("overview_current_test_id")
                            current_test_type = st.session_state.get("overview_test_type")
                            current_tenant_id = st.session_state.get("overview_current_tenant_id")
                            current_recorded_date = st.session_state.get("overview_test_recorded_date")

                            available_trial_metrics = get_all_trial_metric_names(specific_test_details)

                            available_metric_entries = extract_available_metrics_from_tests([
                                {
                                    "test_id": current_test_id,
                                    "tenant_id": current_tenant_id,
                                    "recorded_date_utc": current_recorded_date,
                                    "test_type": current_test_type,
                                    "trials": specific_test_details
                                }
                            ])

                            available_categories_for_type = list(
                                TEST_TYPE_METRIC_CATEGORIES.get(current_test_type, {}).keys()
                            )

                            selected_overview_metrics = []

                            if available_categories_for_type:
                                resolved_category_metrics, unmatched_category_metrics = resolve_category_metrics_for_test_type(
                                    current_test_type,
                                    available_metric_entries
                                )

                                if (
                                    current_test_id not in st.session_state.overview_selected_categories
                                    or not st.session_state.overview_selected_categories[current_test_id]
                                ):
                                    default_categories = [
                                        c for c in ["Output", "Monitoring", "Concentric", "Landing"]
                                        if c in available_categories_for_type
                                    ]
                                    st.session_state.overview_selected_categories[current_test_id] = default_categories

                                selected_categories = st.multiselect(
                                    "Select metric categories for trial comparison:",
                                    options=available_categories_for_type,
                                    default=st.session_state.overview_selected_categories[current_test_id],
                                    key=f"overview_categories_{current_test_id}"
                                )

                                st.session_state.overview_selected_categories[current_test_id] = selected_categories
                                st.session_state.overview_resolved_metrics[current_test_id] = resolved_category_metrics

                                for category in selected_categories:
                                    selected_overview_metrics.extend(resolved_category_metrics.get(category, []))

                                selected_overview_metrics = list(dict.fromkeys(selected_overview_metrics))

                                with st.expander("Debug: matched and unmatched metrics for this test", expanded=False):
                                    st.write("Test type:", current_test_type)
                                    st.write("Available categories:", available_categories_for_type)
                                    st.write("Selected categories:", selected_categories)
                                    st.write("Matched metrics by category:", resolved_category_metrics)
                                    st.write("Unmatched metrics by category:", unmatched_category_metrics)
                                    st.write("Final selected metrics:", selected_overview_metrics)

                            else:
                                default_metrics = [
                                    m for m in [
                                        'Jump Height (Flight Time)',
                                        'Peak Power',
                                        'Countermovement Depth',
                                        'Peak Landing Force',
                                        'Bodyweight in Kilograms',
                                        'Flight Time',
                                        'Contraction Time',
                                        'RSI-modified',
                                    ]
                                    if m in available_trial_metrics
                                ]

                                if (
                                    current_test_id not in st.session_state.overview_selected_metrics
                                    or not st.session_state.overview_selected_metrics[current_test_id]
                                ):
                                    st.session_state.overview_selected_metrics[current_test_id] = default_metrics

                                selected_overview_metrics = st.multiselect(
                                    "Select Trial-level metrics for trial comparison:",
                                    options=available_trial_metrics,
                                    key=f"overview_metrics_{current_test_id}",
                                    default=st.session_state.overview_selected_metrics[current_test_id]
                                )

                                st.session_state.overview_selected_metrics[current_test_id] = selected_overview_metrics

                            comparison_data = {}
                            for i, trial in enumerate(specific_test_details):
                                trial_id = f"Trial {i+1}"
                                if 'results' in trial:
                                    results = trial['results']
                                    for r in results:
                                        record = extract_metric_record(r)
                                        if not record:
                                            continue

                                        if record["limb"] != "Trial":
                                            continue

                                        metric_name = record["metric_name"]
                                        if metric_name not in selected_overview_metrics:
                                            continue

                                        if metric_name not in comparison_data:
                                            comparison_data[metric_name] = {}
                                        comparison_data[metric_name][trial_id] = record["value"]

                            if comparison_data:
                                comp_df = pd.DataFrame.from_dict(comparison_data, orient='index').transpose()
                                comp_df.drop(columns='Bodyweight in Kilograms', inplace=True, errors='ignore')

                                trials_df = comp_df[comp_df.index.to_series().str.startswith('Trial')].copy()

                                if not trials_df.empty and len(trials_df.columns) > 0:
                                    for col in trials_df.columns:
                                        trials_df[col] = pd.to_numeric(trials_df[col], errors='coerce')

                                    average_all = trials_df.mean(numeric_only=True)
                                    std_all = trials_df.std(numeric_only=True)
                                    cv_all = (std_all / average_all.replace(0, pd.NA)) * 100

                                    jump_height_col = find_jump_height_column(trials_df)
                                    top3_indices = []
                                    best_trial = None

                                    if jump_height_col and jump_height_col in trials_df.columns and not trials_df.empty:
                                        top3_values = trials_df[jump_height_col].dropna().nlargest(
                                            min(3, len(trials_df.dropna(subset=[jump_height_col])))
                                        )
                                        top3_indices = top3_values.index.tolist()
                                        if not top3_values.empty:
                                            best_trial = top3_values.index[0]
                                    else:
                                        top3_indices = trials_df.index[:min(3, len(trials_df))].tolist()
                                        best_trial = top3_indices[0] if top3_indices else None

                                    avg_best3 = trials_df.loc[top3_indices].mean(numeric_only=True) if top3_indices else pd.Series()
                                    std_best3 = trials_df.loc[top3_indices].std(numeric_only=True) if top3_indices else pd.Series()
                                    cv_best3 = (std_best3 / avg_best3.replace(0, pd.NA)) * 100 if not avg_best3.empty else pd.Series()

                                    table_df = trials_df.copy()
                                    table_df.loc['Average'] = average_all
                                    table_df.loc['Std'] = std_all
                                    table_df.loc['CV (%)'] = cv_all
                                    table_df.loc['Average from Best 3'] = avg_best3
                                    table_df.loc['Std Best 3'] = std_best3
                                    table_df.loc['CV Best 3 (%)'] = cv_best3

                                    def _style_rows(row):
                                        if row.name == best_trial:
                                            return ['background-color: #28A028; color: #FFFFFF'] * len(row)
                                        if row.name in top3_indices:
                                            return ['background-color: #90EE90; color: #000000'] * len(row)
                                        if row.name in ['Average', 'Average from Best 3']:
                                            return ['background-color: #FFD700; color: #000000'] * len(row)
                                        if row.name in ['Std', 'Std Best 3', 'CV (%)', 'CV Best 3 (%)']:
                                            return ['background-color: #ADD8E6; color: #000000'] * len(row)
                                        return [''] * len(row)

                                    with st.expander("Metrics Comparison Across Trials", expanded=False):
                                        st.subheader("Metrics Comparison Across Trials")
                                        styled_table = table_df.style.apply(_style_rows, axis=1)
                                        st.dataframe(styled_table, width="stretch")

                                        st.markdown("""
                                        **Colors legend:**
                                        - 🟩 **Dark Green** - best trial
                                        - 🟩 **Light Green** - top 3 trials
                                        - 🟨 **Gold** - average values
                                        - 🟦 **Light Blue** - standard deviations and CV
                                        """)

                                    with st.expander("Visualize Metrics Across Trials", expanded=False):
                                        st.subheader("Comparison Visualizations")
                                        for metric in selected_overview_metrics:
                                            if metric in trials_df.columns:
                                                fig = create_metrics_comparison_chart(trials_df, metric)
                                                if fig:
                                                    st.plotly_chart(fig, width="stretch")
                                else:
                                    st.info("No trial-level data available for the selected metrics.")
                            else:
                                st.info("No comparison data found for the selected metrics.")

                            trial = specific_test_details[0]

                            if 'results' in trial and trial['results']:
                                df_results = pd.DataFrame([
                                    {
                                        'Metric Name': extract_metric_record(r)["metric_name"] if extract_metric_record(r) else None,
                                        'Metric Full Name': extract_metric_record(r)["full_name"] if extract_metric_record(r) else None,
                                        'Metric Key': extract_metric_record(r)["metric_key"] if extract_metric_record(r) else None,
                                        'Value': r.get('value'),
                                        'Unit': r.get('definition', {}).get('unit'),
                                        'Description': r.get('definition', {}).get('description'),
                                        'Time (s)': r.get('time'),
                                        'Limb': r.get('limb'),
                                        'Repeat': r.get('repeat')
                                    }
                                    for r in trial['results']
                                    if extract_metric_record(r)
                                ])

                                with st.expander("All metrics from first trial (debug)", expanded=False):
                                    st.dataframe(df_results, width="stretch")

                                asym_df = df_results[df_results['Limb'].isin(['Left', 'Right', 'Asym'])]
                                if not asym_df.empty:
                                    with st.expander("Limb Asymmetry Analysis", expanded=False):
                                        st.subheader("Limb Asymmetries")
                                        for metric in asym_df['Metric Name'].dropna().unique():
                                            fig_lr, fig_asym = create_limb_asymmetry_charts(asym_df, metric)

                                            if fig_lr or fig_asym:
                                                col1, col2 = st.columns(2)

                                                with col1:
                                                    if fig_lr:
                                                        st.plotly_chart(fig_lr, width="stretch")

                                                with col2:
                                                    if fig_asym:
                                                        st.plotly_chart(fig_asym, width="stretch")
                        else:
                            st.json(specific_test_details)

                else:
                    st.info("No training sessions found.")
            else:
                st.error("There are no training sessions or failed to load data. Try adjusting the date filter or refreshing the data.")

        except Exception as e:
            st.error(f"Could not fetch data: {str(e)}")
    elif display_mode == "Multiple trainings comparison":

        if "tests_details_all" not in st.session_state:
            st.session_state.tests_details_all = None

        if "chosen_test_ids" not in st.session_state:
            st.session_state.chosen_test_ids = []

        if "selected_metrics" not in st.session_state:
            st.session_state.selected_metrics = []

        if "selected_categories" not in st.session_state:
            st.session_state.selected_categories = []

        if "resolved_category_metrics" not in st.session_state:
            st.session_state.resolved_category_metrics = {}

        if "unmatched_category_metrics" not in st.session_state:
            st.session_state.unmatched_category_metrics = {}

        if "prepared_comparison_data" not in st.session_state:
            st.session_state.prepared_comparison_data = None

        if "prepared_summary_data" not in st.session_state:
            st.session_state.prepared_summary_data = None

        if "graphs_generated" not in st.session_state:
            st.session_state.graphs_generated = False

        if "use_time_axis" not in st.session_state:
            st.session_state.use_time_axis = False

        if "show_trendline" not in st.session_state:
            st.session_state.show_trendline = False

        if "excluded_tests_text" not in st.session_state:
            st.session_state.excluded_tests_text = ""

        if "use_all_metrics_multi" not in st.session_state:
            st.session_state.use_all_metrics_multi = False

        default_from = datetime.now().date() - pd.Timedelta(days=30)

        col1, col2, col3 = st.columns(3)
        with col1:
            modified_from = st.date_input(
                "Show sessions from date:",
                value=default_from,
                key="modified_from_multi"
            )

        with col2:
            modified_to = st.date_input(
                "Show sessions until date: \n(currently not working - always till today)",
                value=datetime.now().date(),
                key="modified_to_multi"
            )

        with col3:
            type_of_test = st.selectbox(
                "Select test type:",
                ["All", "CMJ"],
                key="test_type_selector"
            )

        

        modified_from_utc = datetime.combine(modified_from, datetime.min.time()).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        modified_to_utc = datetime.combine(modified_to, datetime.max.time()).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        st.caption(f"Current filter: date from {modified_from_utc[:10]} to {modified_to_utc[:10]}")

        data = client.get_training_sessions_all(
            profile_id=athlete_id,
            modified_from_utc=modified_from_utc,
        )

        if data and "tests" in data:
            tests_list = data["tests"]
            tests_list = [t for t in tests_list if (type_of_test == "All" or t.get('testType') == type_of_test)]

            effective_test_type = type_of_test
            if type_of_test == "All" and tests_list:
                detected_types = sorted(set(t.get("testType") for t in tests_list if t.get("testType")))
                if len(detected_types) == 1 and detected_types[0] in TEST_TYPE_METRIC_CATEGORIES:
                    effective_test_type = detected_types[0]

            available_categories_for_type = list(TEST_TYPE_METRIC_CATEGORIES.get(effective_test_type, {}).keys())

            current_selected_categories = st.session_state.selected_categories
            st.session_state.selected_categories = [
                category for category in current_selected_categories
                if category in available_categories_for_type
            ]

            if tests_list:
                df = pd.DataFrame(tests_list)

                columns_to_show = ['tenantId', "testType", "recordedDateUtc", "analysedDateUtc", "weight", "notes"]
                df_display = df.reindex(columns=columns_to_show, fill_value='').copy()
                df_display.insert(0, "Test Number", range(len(df_display)))
                df_display.columns = ["Test Number", "Tenant ID", "Test Type", "Recorded Date", "Analysed Date", "Weight (kg)", "Notes"]

                df_display["Recorded Date"] = pd.to_datetime(df_display["Recorded Date"], format='ISO8601', errors='coerce').dt.strftime("%Y-%m-%d %H:%M")
                df_display["Analysed Date"] = pd.to_datetime(df_display["Analysed Date"], format='ISO8601', errors='coerce').dt.strftime("%Y-%m-%d %H:%M")

                st.dataframe(df_display, width="stretch")
                st.caption("Test Number corresponds to index in the table (starting from 0).")

                test_ids = df['testId'].tolist()
                st.write(f"**Total sessions:** {len(test_ids)}")

                col_range, col_exclude = st.columns([2, 1])

                with col_range:
                    amount_of_tests = st.slider(
                        "Select test index range:",
                        min_value=0,
                        max_value=len(test_ids) - 1,
                        value=[max(0, len(test_ids) - 2), len(test_ids) - 1],
                        key="num_tests_selector"
                    )

                with col_exclude:
                    excluded_tests_text = st.text_input(
                        "Exclude tests (by index from table)",
                        value=st.session_state.excluded_tests_text,
                        key="excluded_tests_text",
                        placeholder="e.g. 8 or 8,10"
                    )

                use_all_metrics_multi = st.checkbox(
                    "Use all available metrics from loaded tests",
                    value=st.session_state.use_all_metrics_multi,
                    key="use_all_metrics_multi"
                )

                start_idx, end_idx = amount_of_tests

                excluded_test_numbers = parse_excluded_tests(
                    excluded_tests_text,
                    min_idx=start_idx,
                    max_idx=end_idx
                )

                selected_test_indices = [
                    idx
                    for idx in range(start_idx, end_idx + 1)
                    if idx not in excluded_test_numbers
                ]

                chosen_test_ids = [test_ids[idx] for idx in selected_test_indices]

                if excluded_test_numbers:
                    st.caption(
                        f"Selected test indices: {start_idx}-{end_idx} | Excluded: {excluded_test_numbers} | Final count: {len(chosen_test_ids)}"
                    )
                else:
                    st.caption(
                        f"Selected test indices: {start_idx}-{end_idx} | Final count: {len(chosen_test_ids)}"
                    )

                if st.button("Get data", key="get_data"):
                    if not chosen_test_ids:
                        st.warning("No tests selected after exclusions. Adjust the range or excluded test numbers.")
                    else:
                        tests_details_all = []

                        selected_tests = [t for t in tests_list if t.get("testId") in chosen_test_ids]

                        st.write(f"Comparing tests with IDs: {chosen_test_ids}")
                        progress_bar = st.progress(0, text="Loading test details...")

                        for index, test_obj in enumerate(selected_tests):
                            test_id = test_obj.get("testId")
                            tenant_id = test_obj.get("tenantId")

                            specific_test_details = client.get_test_details(
                                teamId=tenant_id,
                                testId=test_id
                            )

                            if specific_test_details:
                                tests_details_all.append({
                                    "test_id": test_id,
                                    "tenant_id": tenant_id,
                                    "recorded_date_utc": test_obj.get("recordedDateUtc"),
                                    "modified_date_utc": test_obj.get("modifiedDateUtc"),
                                    "test_type": test_obj.get("testType"),
                                    "trials": specific_test_details
                                })

                                progress_bar.progress(
                                    (index + 1) / len(selected_tests),
                                    text=f"Loaded details for test number {index + 1} of {len(selected_tests)} (ID: {test_id})"
                                )
                            else:
                                st.error(f"Failed to load details for test {test_id}.")

                        progress_bar.empty()
                        st.session_state.tests_details_all = tests_details_all
                        st.session_state.chosen_test_ids = chosen_test_ids
                        st.session_state.prepared_summary_data = None
                        st.session_state.prepared_comparison_data = None
                        st.session_state.graphs_generated = False
                        st.session_state.resolved_category_metrics = {}
                        st.session_state.unmatched_category_metrics = {}
                        st.session_state.selected_metrics = []

                        success_loading = st.success("All test details loaded.")
                        time.sleep(1)
                        success_loading.empty()

                if st.session_state.tests_details_all:
                    available_metric_entries = extract_available_metrics_from_tests(st.session_state.tests_details_all)

                    with st.expander("Debug: all available metrics found in loaded tests", expanded=False):
                        available_df = pd.DataFrame([
                            {
                                "Metric Key": e["metric_key"],
                                "Metric Name": e["metric_name"],
                                "Full Name": e["full_name"],
                                "Limb": e["limb"],
                            }
                            for e in available_metric_entries
                        ]).sort_values(by=["Metric Name", "Limb"], na_position="last")
                        st.write(f"Total unique metric entries found: {len(available_metric_entries)}")
                        st.dataframe(available_df, width="stretch")

                    if available_categories_for_type and not use_all_metrics_multi:
                        selected_categories = st.multiselect(
                            "Select metric categories:",
                            options=available_categories_for_type,
                            default=st.session_state.selected_categories,
                            key="categories_multiselect"
                        )
                        st.session_state.selected_categories = selected_categories
                    else:
                        selected_categories = []

                    if st.button("Prepare data", key="prepare_data"):
                        with st.spinner("Preparing comparison data..."):
                            if use_all_metrics_multi:
                                selected_metrics = [entry["full_name"] for entry in available_metric_entries]
                                selected_metrics = list(dict.fromkeys(selected_metrics))
                                resolved_category_metrics = {}
                                unmatched_category_metrics = {}
                            else:
                                if not selected_categories:
                                    st.warning("Select at least one category before preparing data.")
                                    return

                                resolved_category_metrics, unmatched_category_metrics = resolve_category_metrics_for_test_type(
                                    effective_test_type,
                                    available_metric_entries
                                )

                                selected_metrics = []
                                for category in selected_categories:
                                    selected_metrics.extend(resolved_category_metrics.get(category, []))

                                selected_metrics = list(dict.fromkeys(selected_metrics))

                            st.session_state.resolved_category_metrics = resolved_category_metrics
                            st.session_state.unmatched_category_metrics = unmatched_category_metrics
                            st.session_state.selected_metrics = selected_metrics

                            if not selected_metrics:
                                st.session_state.prepared_summary_data = None
                                st.session_state.prepared_comparison_data = None
                                st.warning("No metrics selected/found for preparation.")
                            else:
                                summary_df, trials_data_per_test = prepare_tests_for_comparison(
                                st.session_state.tests_details_all,
                                selected_metrics=selected_metrics,
                                use_all_metrics=use_all_metrics_multi
                            )

                            # Add readable display labels for X axis
                            if summary_df is not None and not summary_df.empty:
                                if "Plot Date" in summary_df.columns:
                                    plot_dates = pd.to_datetime(summary_df["Plot Date"], errors="coerce")
                                elif "Recorded Date" in summary_df.columns:
                                    plot_dates = pd.to_datetime(summary_df["Recorded Date"], errors="coerce")
                                else:
                                    plot_dates = pd.Series([pd.NaT] * len(summary_df))

                                summary_df["Plot Date"] = plot_dates

                                summary_df["Display Label"] = plot_dates.apply(
                                    lambda d: d.strftime("%d-%m-%Y %H:%M") if pd.notnull(d) else "Unknown date"
                                )

                            st.session_state.prepared_summary_data = summary_df
                            st.session_state.prepared_comparison_data = trials_data_per_test
                            st.session_state.graphs_generated = False

                            st.success("Data prepared successfully.")
                    if (
                        st.session_state.prepared_summary_data is not None
                        and not st.session_state.prepared_summary_data.empty
                    ):
                        st.subheader("Prepared summary data")
                        st.dataframe(st.session_state.prepared_summary_data, width="stretch")

                        with st.expander("Debug: matched and unmatched metrics", expanded=False):
                            st.write("Use all metrics mode:", use_all_metrics_multi)
                            st.write("Selected categories:", st.session_state.selected_categories)
                            st.write("Matched metrics by category:", st.session_state.resolved_category_metrics)
                            st.write("Unmatched metrics by category:", st.session_state.unmatched_category_metrics)
                            st.write("Final selected metrics count:", len(st.session_state.selected_metrics))
                            st.write("Final selected metrics:", st.session_state.selected_metrics[:200])
                            st.write("Columns in prepared summary data:", list(st.session_state.prepared_summary_data.columns))

                        col_btn, col_chk1, col_chk2 = st.columns([1, 1, 1])

                        with col_btn:
                            if st.button("Generate graphs", key="generate_graphs"):
                                st.session_state.graphs_generated = True

                        with col_chk1:
                            st.checkbox(
                                "Use time scale on X axis",
                                value=st.session_state.use_time_axis,
                                key="use_time_axis"
                            )

                        with col_chk2:
                            st.checkbox(
                                "Show trendline",
                                value=st.session_state.show_trendline,
                                key="show_trendline"
                            )

                    if (
                        st.session_state.graphs_generated
                        and st.session_state.prepared_summary_data is not None
                        and not st.session_state.prepared_summary_data.empty
                    ):
                        st.subheader("Graphs")

                        if use_all_metrics_multi:
                            metrics_to_plot = st.multiselect(
                                "Choose metrics to plot",
                                options=st.session_state.selected_metrics,
                                default=st.session_state.selected_metrics[:min(12, len(st.session_state.selected_metrics))],
                                key="plot_metrics_all_mode"
                            )

                            if metrics_to_plot:
                                for metric in metrics_to_plot:
                                    fig = create_mean_std_chart(
                                        st.session_state.prepared_summary_data,
                                        metric,
                                        use_time_axis=st.session_state.use_time_axis,
                                        show_trendline=st.session_state.show_trendline
                                    )
                                    if fig:
                                        st.plotly_chart(fig, width="stretch")
                        else:
                            resolved_category_metrics = st.session_state.get("resolved_category_metrics", {})

                            for category in st.session_state.selected_categories:
                                category_metrics = resolved_category_metrics.get(category, [])

                                with st.expander(category, expanded=False):
                                    plotted_any = False

                                    grouped_metrics = group_metrics_by_base(category_metrics)

                                    for base_metric, metric_map in grouped_metrics.items():

                                        # jeśli mamy Left + Right -> jeden wspólny wykres
                                        # ale tylko poza kategorią Asymmetry
                                        if category != "Asymmetry" and "Left" in metric_map and "Right" in metric_map:
                                            fig = create_left_right_chart(
                                                st.session_state.prepared_summary_data,
                                                base_metric,
                                                metric_map,
                                                use_time_axis=st.session_state.use_time_axis,
                                                show_trendline=st.session_state.show_trendline
                                            )
                                            if fig:
                                                st.plotly_chart(fig, width="stretch")
                                                plotted_any = True

                                            # opcjonalnie dalej pokaż Trial osobno, jeśli istnieje
                                            if "Trial" in metric_map:
                                                fig = create_mean_std_chart(
                                                    st.session_state.prepared_summary_data,
                                                    metric_map["Trial"],
                                                    use_time_axis=st.session_state.use_time_axis,
                                                    show_trendline=st.session_state.show_trendline
                                                )
                                                if fig:
                                                    st.plotly_chart(fig, width="stretch")
                                                    plotted_any = True

                                        else:
                                            # fallback: rysuj wszystko co jest, w tym Asym
                                            for limb, metric in metric_map.items():
                                                fig = create_mean_std_chart(
                                                    st.session_state.prepared_summary_data,
                                                    metric,
                                                    use_time_axis=st.session_state.use_time_axis,
                                                    show_trendline=st.session_state.show_trendline
                                                )
                                                if fig:
                                                    st.plotly_chart(fig, width="stretch")
                                                    plotted_any = True

                                    if not plotted_any:
                                        st.info(f"No graphs available for category: {category}")

            else:
                st.info("No training sessions found.")
        else:
            st.error("There are no training sessions or failed to load data. Try adjusting the date filter or refreshing the data.")

    else:

        st.header("Raw data / trial overlays")

        if "trial_overlays" not in st.session_state:
            st.session_state.trial_overlays = []

        if "raw_data_cache" not in st.session_state:
            st.session_state.raw_data_cache = {}

        if "current_raw_json" not in st.session_state:
            st.session_state.current_raw_json = None

        if "current_raw_test_id" not in st.session_state:
            st.session_state.current_raw_test_id = ""

        if "current_raw_tenant_id" not in st.session_state:
            st.session_state.current_raw_tenant_id = ""

        st.subheader("Load raw data")

        col1, col2 = st.columns([2, 2])

        raw_tenant_id=client.tenant_id or ""

        with col1:
            raw_test_id = st.text_input(
                "Test ID",
                value=st.session_state.current_raw_test_id,
                key="raw_test_id_input"
            )

        with col2:
            st.write("")
            st.write("")
            load_raw_btn = st.button("Load raw data", width="stretch")

        if load_raw_btn:
            try:
                if not raw_tenant_id.strip() or not raw_test_id.strip():
                    st.error("Enter both Tenant ID and Test ID.")
                else:
                    raw_json = client.get_raw_data(
                        raw_tenant_id.strip(),
                        raw_test_id.strip(),
                        True
                    )

                    st.session_state.current_raw_json = raw_json
                    st.session_state.current_raw_test_id = raw_test_id.strip()
                    st.session_state.current_raw_tenant_id = raw_tenant_id.strip()

                    cache_key = f"{raw_tenant_id.strip()}::{raw_test_id.strip()}"
                    st.session_state.raw_data_cache[cache_key] = raw_json

                    st.success("Raw data loaded.")
            except Exception as e:
                st.error(f"Failed to load raw data: {e}")

        raw_json = st.session_state.current_raw_json

        if raw_json:
            try:
                df_raw, fig_raw = create_raw_force_plot(
                    raw_json,
                    title=f"ForceDecks Raw Data - Test {st.session_state.current_raw_test_id}",
                    max_points=10000
                )
                st.plotly_chart(fig_raw, width="stretch")

                with st.expander("Show raw data table", expanded=False):
                    st.dataframe(df_raw, width="stretch")

                with st.expander("Show raw JSON", expanded=False):
                    st.write(raw_json)

            except Exception as e:
                st.error(f"Failed to visualize raw data: {e}")

        st.divider()
        st.subheader("Trial overlays")

        with st.expander("Add graph of trial", expanded=False):
            overlay_tenant_id = client.tenant_id
            with st.form("add_trial_overlay_form"):
                

                overlay_test_id = st.text_input(
                    "Test ID for overlay trial",
                    value=st.session_state.current_raw_test_id,
                    key="overlay_test_id"
                )

                col_a, col_b, col_c = st.columns(3)

                with col_a:
                    leg_choice = st.selectbox(
                        "Leg",
                        ["Both", "Left", "Right"],
                        key="overlay_leg_choice"
                    )

                with col_b:
                    pre_ms = st.number_input(
                    "Time before movement onset [ms]",
                    min_value=0,
                    value=200,
                    step=50,
                    key="overlay_pre_ms"
                )

                with col_c:
                    post_ms = st.number_input(
                        "Time after movement onset [ms]",
                        min_value=200,
                        value=2000,
                        step=50,
                        key="overlay_post_ms"
                    )

                detect_trials_btn = st.form_submit_button("Detect trials")

            detected_takeoffs = []
            detected_trials_count = 0
            detected_bw = None
            overlay_raw_data = None

            if detect_trials_btn:
                try:
                    if not overlay_tenant_id.strip() or not overlay_test_id.strip():
                        st.error("Enter both Tenant ID and Test ID.")
                    else:
                        cache_key = f"{overlay_tenant_id.strip()}::{overlay_test_id.strip()}"

                        if cache_key in st.session_state.raw_data_cache:
                            overlay_raw_data = st.session_state.raw_data_cache[cache_key]
                        else:
                            overlay_raw_data = client.get_raw_data(
                                overlay_tenant_id.strip(),
                                overlay_test_id.strip(),
                                True
                            )
                            st.session_state.raw_data_cache[cache_key] = overlay_raw_data

                        overlay_df = parse_forcedeck_raw_data(overlay_raw_data)
                        detected_takeoffs, detected_bw = detect_takeoff_events(
                            overlay_df,
                            sampling_frequency=int(overlay_raw_data.get("samplingFrequency", 1000))
                        )
                        detected_trials_count = len(detected_takeoffs)

                        st.session_state["last_overlay_raw_data"] = overlay_raw_data
                        st.session_state["last_overlay_test_id"] = overlay_test_id.strip()
                        st.session_state["last_overlay_tenant_id"] = overlay_tenant_id.strip()
                        st.session_state["last_overlay_leg_choice"] = leg_choice
                        st.session_state["last_overlay_pre_ms"] = int(pre_ms)
                        st.session_state["last_overlay_post_ms"] = int(post_ms)
                        st.session_state["last_detected_trials_count"] = detected_trials_count

                        if detected_trials_count > 0:
                            st.success(
                                f"Detected {detected_trials_count} trial(s). Estimated BW: {detected_bw:.1f} N"
                            )
                        else:
                            st.warning("No trials detected.")
                except Exception as e:
                    st.error(f"Failed to detect trials: {e}")

        if st.session_state.get("last_detected_trials_count", 0) > 0:
            with st.form("choose_trial_to_overlay_form"):
                trial_number = st.selectbox(
                    "Choose trial to overlay",
                    options=list(range(1, st.session_state["last_detected_trials_count"] + 1)),
                    key="overlay_trial_number"
                )

                add_overlay_btn = st.form_submit_button("Add selected trial overlay")

            if add_overlay_btn:
                try:
                    overlay_raw_data = st.session_state["last_overlay_raw_data"]
                    overlay_test_id = st.session_state["last_overlay_test_id"]
                    leg_choice = st.session_state["last_overlay_leg_choice"]
                    pre_ms = st.session_state["last_overlay_pre_ms"]
                    post_ms = st.session_state["last_overlay_post_ms"]

                    trial_df, plot_cols, detected_trials, bw = prepare_overlay_trial(
                        raw_data=overlay_raw_data,
                        leg=leg_choice,
                        trial_number=int(trial_number),
                        pre_ms=int(pre_ms),
                        post_ms=int(post_ms)
                    )

                    recorded_utc = overlay_raw_data.get("recordedUTC")

                    if recorded_utc:
                        try:
                            recorded_dt = pd.to_datetime(recorded_utc, errors="coerce")
                            recorded_str = recorded_dt.strftime("%Y-%m-%d %H:%M") if pd.notnull(recorded_dt) else "Unknown date"
                        except:
                            recorded_str = "Unknown date"
                    else:
                        recorded_str = "Unknown date"

                    overlay_label = f"{recorded_str} | Trial {trial_number} | {leg_choice} | ID: {overlay_test_id}"

                    st.session_state.trial_overlays.append({
                        "label": overlay_label,
                        "df": trial_df,
                        "plot_cols": plot_cols
                    })

                    st.success("Trial overlay added.")
                except Exception as e:
                    st.error(f"Failed to add overlay: {e}")

        if st.session_state.trial_overlays:
            overlay_fig = create_overlay_trials_chart(st.session_state.trial_overlays)
            st.plotly_chart(overlay_fig, width="stretch")

            st.markdown("**Added overlays:**")
            for idx, overlay in enumerate(st.session_state.trial_overlays, start=1):
                st.write(f"{idx}. {overlay['label']}")

            col_remove_1, col_remove_2 = st.columns([1, 1])

            with col_remove_1:
                remove_idx = st.number_input(
                    "Remove overlay #",
                    min_value=1,
                    max_value=len(st.session_state.trial_overlays),
                    step=1,
                    value=1,
                    key="remove_overlay_idx"
                )

            with col_remove_2:
                st.write("")
                st.write("")
                if st.button("Remove selected overlay", width="stretch"):
                    st.session_state.trial_overlays.pop(remove_idx - 1)
                    st.rerun()

            if st.button("Clear all overlays", width="stretch"):
                st.session_state.trial_overlays = []
                st.rerun()
        else:
            st.info("No trial overlays added yet.")


if __name__ == "__main__":
    main()