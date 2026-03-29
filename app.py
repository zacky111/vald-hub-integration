from xmlrpc import client

from plotly import data
import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os
import time
import re

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.vald_client import ValdHubClient

from src.visualizations import create_metrics_comparison_chart, create_limb_asymmetry_chart
from src.visualizations import create_mean_std_chart

from src.data_prep_funcs import parse_excluded_tests
from src.metric_categories import TEST_TYPE_METRIC_CATEGORIES


@st.cache_resource
def get_vald_client():
    """Get cached ValdHubClient instance - persists across Streamlit reruns"""
    return ValdHubClient()


def normalize_metric_name(metric_name: str) -> str:
    if metric_name is None:
        return ""

    text = str(metric_name).strip().lower()

    replacements = {
        "assymetry": "asymmetry",
        "conctraction": "contraction",
        "body weight": "bodyweight",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def split_metric_and_limb(metric_name: str, limb: str):
    """
    Zwraca:
    - base_metric_name: nazwa bazowa metryki
    - full_metric_name: nazwa metryki z suffixem limb, jeśli limb != Trial
    """
    base_metric_name = metric_name
    full_metric_name = metric_name if not limb or limb == "Trial" else f"{metric_name} - {limb}"
    return base_metric_name, full_metric_name


def extract_available_metrics_from_tests(tests_details_all):
    """
    Zwraca listę wszystkich metryk dostępnych w pobranych testach.
    Każdy element:
    {
        "base_name": ...,
        "full_name": ...,
        "limb": ...,
        "normalized_base": ...,
        "normalized_full": ...,
    }
    """
    available_entries = []
    seen = set()

    for test_obj in tests_details_all or []:
        trials = test_obj.get("trials", [])
        for trial in trials:
            for result in trial.get("results", []):
                metric_name = result.get("definition", {}).get("name")
                limb = result.get("limb")

                if not metric_name:
                    continue

                base_name, full_name = split_metric_and_limb(metric_name, limb)
                key = (base_name, full_name, limb)

                if key in seen:
                    continue

                seen.add(key)
                available_entries.append({
                    "base_name": base_name,
                    "full_name": full_name,
                    "limb": limb,
                    "normalized_base": normalize_metric_name(base_name),
                    "normalized_full": normalize_metric_name(full_name),
                })

    return available_entries


def resolve_category_metrics_for_test_type(test_type, available_metric_entries):
    """
    Dopasowuje metryki z configu kategorii do realnych metryk z API.
    Dopasowanie odbywa się po nazwie bazowej, dzięki czemu np.:
    'Peak Force'
    dopasuje:
    - Peak Force
    - Peak Force - Left
    - Peak Force - Right
    - Peak Force - Asym

    Zwraca:
    - resolved: category -> lista pełnych nazw metryk z API
    - unmatched: category -> lista metryk z configu, których nie udało się dopasować
    """
    category_config = TEST_TYPE_METRIC_CATEGORIES.get(test_type, {})
    resolved = {}
    unmatched = {}

    for category, config_metrics in category_config.items():
        resolved[category] = []
        unmatched[category] = []

        for config_metric in config_metrics:
            normalized_config = normalize_metric_name(config_metric)

            # 1. exact base match
            matched_entries = [
                entry["full_name"]
                for entry in available_metric_entries
                if entry["normalized_base"] == normalized_config
            ]

            # 2. fallback: exact full match
            if not matched_entries:
                matched_entries = [
                    entry["full_name"]
                    for entry in available_metric_entries
                    if entry["normalized_full"] == normalized_config
                ]

            # 3. fallback: partial base/full match
            if not matched_entries:
                matched_entries = [
                    entry["full_name"]
                    for entry in available_metric_entries
                    if normalized_config in entry["normalized_base"]
                    or entry["normalized_base"] in normalized_config
                    or normalized_config in entry["normalized_full"]
                    or entry["normalized_full"] in normalized_config
                ]

            matched_entries = list(dict.fromkeys(matched_entries))

            if matched_entries:
                for metric in matched_entries:
                    if metric not in resolved[category]:
                        resolved[category].append(metric)
            else:
                unmatched[category].append(config_metric)

    return resolved, unmatched


def prepare_tests_for_comparison(tests_details_all, selected_metrics):
    """
    Dla każdego testu:
    - zbiera WSZYSTKIE metryki per trial (Trial, Left, Right, Asym, itd.)
    - wybiera top 3 próby wg Jump Height (Flight Time) [tylko Trial]
    - liczy mean i std dla wybranych metryk
    Zwraca:
    - summary_df
    - trials_data_per_test
    """
    jump_height_metric = "Jump Height (Flight Time)"

    def get_sort_date(test_obj):
        date_source = test_obj.get("recorded_date_utc") or test_obj.get("modified_date_utc")
        return pd.to_datetime(date_source, errors="coerce", utc=True)

    sorted_tests = sorted(
        tests_details_all,
        key=lambda x: (
            pd.isna(get_sort_date(x)),
            get_sort_date(x)
        )
    )

    summary_rows = []
    trials_data_per_test = {}

    for test_idx, test_obj in enumerate(sorted_tests):
        test_trials = test_obj["trials"]

        recorded_date_utc = test_obj.get("recorded_date_utc")
        modified_date_utc = test_obj.get("modified_date_utc")
        test_id = test_obj.get("test_id")
        test_type = test_obj.get("test_type")

        date_source = recorded_date_utc or modified_date_utc
        parsed_date = pd.to_datetime(date_source, errors="coerce", utc=True) if date_source else pd.NaT

        test_label = f"Test {test_idx + 1}"

        if not isinstance(test_trials, list) or not test_trials:
            continue

        comparison_data = {}

        for i, trial in enumerate(test_trials):
            trial_id = f"Trial {i + 1}"

            if "results" not in trial:
                continue

            for r in trial["results"]:
                metric_name = r.get("definition", {}).get("name")
                limb = r.get("limb")
                value = r.get("value")

                if metric_name is None:
                    continue

                _, full_metric_name = split_metric_and_limb(metric_name, limb)

                if full_metric_name not in comparison_data:
                    comparison_data[full_metric_name] = {}
                comparison_data[full_metric_name][trial_id] = value

        if not comparison_data:
            continue

        comp_df = pd.DataFrame.from_dict(comparison_data, orient="index").transpose()

        # Jump Height do top3 wybieramy wyłącznie po Trial
        if jump_height_metric not in comp_df.columns:
            continue

        trials_df = comp_df[comp_df.index.to_series().str.startswith("Trial")].copy()
        if trials_df.empty:
            continue

        trials_df[jump_height_metric] = pd.to_numeric(trials_df[jump_height_metric], errors="coerce")
        trials_df = trials_df.dropna(subset=[jump_height_metric])

        if trials_df.empty:
            continue

        top3_indices = trials_df[jump_height_metric].nlargest(3).index.tolist()
        best3_df = trials_df.loc[top3_indices].copy()

        metrics_to_use = [m for m in selected_metrics if m in best3_df.columns]

        # Jump Height zawsze ma być policzone
        if jump_height_metric in best3_df.columns:
            metrics_to_use = [jump_height_metric] + [m for m in metrics_to_use if m != jump_height_metric]

        if not metrics_to_use:
            continue

        for metric in metrics_to_use:
            best3_df[metric] = pd.to_numeric(best3_df[metric], errors="coerce")

        mean_series = best3_df[metrics_to_use].mean(numeric_only=True)
        std_series = best3_df[metrics_to_use].std(numeric_only=True)

        row = {
            "Test": test_label,
            "Test Order": test_idx + 1,
            "Test ID": test_id,
            "Test Type": test_type,
            "Recorded Date UTC": recorded_date_utc,
            "Modified Date UTC": modified_date_utc,
            "Plot Date": parsed_date,
            "Top 3 Trials": ", ".join(top3_indices),
            "Best Jump Height": trials_df.loc[top3_indices[0], jump_height_metric] if top3_indices else None,
        }

        for metric in metrics_to_use:
            row[f"{metric} Mean"] = mean_series.get(metric)
            row[f"{metric} Std"] = std_series.get(metric)

        summary_rows.append(row)

        trials_data_per_test[test_label] = {
            "test_id": test_id,
            "test_type": test_type,
            "recorded_date_utc": recorded_date_utc,
            "modified_date_utc": modified_date_utc,
            "all_trials_df": trials_df,
            "best3_df": best3_df,
            "top3_indices": top3_indices,
        }

    summary_df = pd.DataFrame(summary_rows)
    return summary_df, trials_data_per_test


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
    </style>
    """, unsafe_allow_html=True)

    st.title("Vald Hub Performance Dashboard")
    st.markdown("*Real-time athlete performance monitoring and analysis*")

    with st.sidebar:
        st.header("Configuration")
        client = get_vald_client()

        try:
            api_connected = client.get_token(client.client_id, client.client_secret)

            if api_connected:
                st.success("✅ Connected to Vald Hub API. ")
            else:
                st.info("Configure `.env` file with your Vald Hub credentials")
        except Exception as e:
            st.error(f"API Error: {str(e)}")

        if st.button("🔄 Refresh Data", use_container_width=True):
            if 'data' in st.session_state:
                del st.session_state.data
            for key in [
                'profiles_data', 'groups_data', 'athlete_details', 'group_details',
                'tests_details_all', 'chosen_test_ids', 'selected_metrics',
                'prepared_comparison_data', 'prepared_summary_data',
                'graphs_generated', 'use_time_axis', 'excluded_tests_text',
                'selected_categories', 'resolved_category_metrics',
                'unmatched_category_metrics'
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
                    selected_athlete = st.selectbox(
                        " ",
                        sorted(athlete_names),
                        key="athlete_selector",
                        label_visibility="collapsed"
                    )
                    st.session_state.selected_athlete = selected_athlete

                    athlete_id = profiles_data['profiles'][athlete_names.index(selected_athlete)].get('profileId', 'N/A')
                    st.write(f"**Athlete ID:** {athlete_id}")

                    if 'athlete_details' not in st.session_state or st.session_state.get('current_athlete_id') != athlete_id:
                        st.session_state.athlete_details = client.get_profiles_details(athlete_id)
                        st.session_state.current_athlete_id = athlete_id
                    athlete_details = st.session_state.athlete_details

                    st.write(f"**Athlete Groups - ID:** {athlete_details['groupIds']}")

                    group_id = athlete_details['groupIds'][0] if athlete_details['groupIds'] else None
                    if group_id and ('group_details' not in st.session_state or st.session_state.get('current_group_id') != group_id):
                        st.session_state.group_details = client.get_group_details(group_id)
                        st.session_state.current_group_id = group_id
                    group_details = st.session_state.get('group_details')

                    st.write(f"**Athlete Groups - Name:** {group_details['name'] if group_details and group_details.get('name') != '' else 'N/A'}")

                    athlete_weight = profiles_data['profiles'][athlete_names.index(selected_athlete)].get('weight', 'N/A')
                    athlete_date_of_birth = profiles_data['profiles'][athlete_names.index(selected_athlete)].get('dateOfBirth', 'N/A')

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

        st.sidebar.markdown("## Group")
        try:
            if 'groups_data' not in st.session_state:
                st.session_state.groups_data = client.get_groups()
            groups_data = st.session_state.groups_data

            if groups_data and 'groups' in groups_data:
                groups = groups_data['groups']
                group_names = [g.get('name', 'Unknown') for g in groups]

                if group_names:
                    selected_group = st.selectbox(
                        " ",
                        sorted(group_names),
                        key="group_selector",
                        label_visibility="collapsed"
                    )
                    st.session_state.selected_group = selected_group
                else:
                    st.warning("No groups found")
            else:
                st.warning("Could not load groups")
        except Exception as e:
            st.error(f"Error loading groups: {str(e)}")

        st.divider()

        st.subheader("Settings")
        display_mode = st.radio(
            "Display Mode",
            ["Overview - Single Training", "Multiple trainings comparison", "Trends"]
        )

    if display_mode == "Overview - Single Training":
        try:
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
                    df_display["Recorded Date"] = pd.to_datetime(df_display["Recorded Date"], format='ISO8601', errors='coerce').dt.strftime("%Y-%m-%d %H:%M")
                    df_display["Analysed Date"] = pd.to_datetime(df_display["Analysed Date"], format='ISO8601', errors='coerce').dt.strftime("%Y-%m-%d %H:%M")

                    st.dataframe(df_display, use_container_width=True)

                    st.write(f"**Total sessions:** {len(tests_list)}")

                    st.subheader("Select Test for Details")
                    test_options = [
                        f"{test.get('testType', 'Unknown')} - {pd.to_datetime(test.get('recordedDateUtc'), format='ISO8601', errors='coerce').strftime('%Y-%m-%d %H:%M') if test.get('recordedDateUtc') else 'Unknown Date'} (ID: {test.get('testId', 'N/A')})"
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

                                    col1, col2, col3 = st.columns(3)
                                    col1.metric("Test type", selected_test.get('testType'))
                                    col2.metric("Number of trials", len(specific_test_details) if isinstance(specific_test_details, list) else 'Unknown')
                                    col3.metric("Recorded date", pd.to_datetime(selected_test.get('recordedDateUtc'), format='ISO8601', errors='coerce').strftime("%Y-%m-%d %H:%M") if selected_test.get('recordedDateUtc') else 'Unknown')

                                    if isinstance(specific_test_details, list) and specific_test_details:
                                        st.write(f"**Number of trials:** {len(specific_test_details)}")

                                        key_metrics_for_comparison = [
                                            'Jump Height (Flight Time)',
                                            'Peak Power',
                                            'Contact Time',
                                            'Countermovement Depth',
                                            'Peak Landing Force',
                                            'Bodyweight in Kilograms'
                                        ]

                                        comparison_data = {}
                                        for i, trial in enumerate(specific_test_details):
                                            trial_id = f"Trial {i+1}"
                                            if 'results' in trial:
                                                results = trial['results']
                                                for r in results:
                                                    metric_name = r['definition']['name']
                                                    if metric_name in key_metrics_for_comparison and r['limb'] == 'Trial':
                                                        if metric_name not in comparison_data:
                                                            comparison_data[metric_name] = {}
                                                        comparison_data[metric_name][trial_id] = r['value']

                                        if comparison_data:
                                            with st.expander("Metrics Comparison Across Trials"):
                                                st.subheader("Metrics Comparison Across Trials")
                                                comp_df = pd.DataFrame.from_dict(comparison_data, orient='index')
                                                comp_df = comp_df.transpose()
                                                comp_df.drop(columns='Bodyweight in Kilograms', inplace=True, errors='ignore')

                                                trials_df = comp_df[comp_df.index.to_series().str.startswith('Trial')]

                                                average_all = trials_df.mean(numeric_only=True)
                                                std_all = trials_df.std(numeric_only=True)
                                                cv_all = (std_all / average_all) * 100

                                                jump_height_col = 'Jump Height (Flight Time)'
                                                top3_indices = []
                                                best_trial = None
                                                if jump_height_col in trials_df.columns and not trials_df.empty:
                                                    top3_values = trials_df[jump_height_col].nlargest(3)
                                                    top3_indices = top3_values.index.tolist()
                                                    best_trial = top3_values.index[0]

                                                avg_best3 = trials_df.loc[top3_indices].mean(numeric_only=True) if top3_indices else pd.Series()
                                                std_best3 = trials_df.loc[top3_indices].std(numeric_only=True) if top3_indices else pd.Series()
                                                cv_best3 = (std_best3 / avg_best3) * 100 if not avg_best3.empty else pd.Series()

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

                                                styled_table = table_df.style.apply(_style_rows, axis=1)
                                                st.dataframe(styled_table, use_container_width=True)

                                                st.markdown("""
                                                **Legenda kolorów:**
                                                - 🟩 **Ciemnozielony** - najlepsza próba (najwyższa wartość Jump Height)
                                                - 🟩 **Jasnozielony** - top 3 próby
                                                - 🟨 **Złoty** - średnie wartości (Average, Average from Best 3)
                                                - 🟦 **Jasnoniebieski** - odchylenia standardowe i współczynnik zmienności (Std, CV)
                                                """)

                                            with st.expander("Visualize Metrics Across Trials"):
                                                st.subheader("Comparison Visualizations")
                                                for metric in key_metrics_for_comparison:
                                                    fig = create_metrics_comparison_chart(trials_df, metric)
                                                    if fig:
                                                        st.plotly_chart(fig, use_container_width=True)

                                        trial = specific_test_details[0]

                                        if 'results' in trial and trial['results']:
                                            results = trial['results']

                                            df_results = pd.DataFrame([
                                                {
                                                    'Metric Name': r['definition']['name'],
                                                    'Value': r['value'],
                                                    'Unit': r['definition']['unit'],
                                                    'Description': r['definition']['description'],
                                                    'Time (s)': r['time'],
                                                    'Limb': r['limb'],
                                                    'Repeat': r['repeat']
                                                } for r in results
                                            ])

                                            asym_df = df_results[df_results['Limb'].isin(['Left', 'Right', 'Asym'])]
                                            if not asym_df.empty:
                                                with st.expander("Limb Asymmetry Analysis"):
                                                    st.subheader("Limb Asymmetries")
                                                    for metric in asym_df['Metric Name'].unique():
                                                        fig_asym = create_limb_asymmetry_chart(asym_df, metric)
                                                        if fig_asym:
                                                            st.plotly_chart(fig_asym, use_container_width=True)
                                        else:
                                            st.json(trial)
                                    else:
                                        st.json(specific_test_details)
                                else:
                                    st.error("Failed to load test details.")
                        else:
                            st.error("Invalid test data.")

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

        if "excluded_tests_text" not in st.session_state:
            st.session_state.excluded_tests_text = ""

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

        available_categories_for_type = list(TEST_TYPE_METRIC_CATEGORIES.get(type_of_test, {}).keys())

        current_selected_categories = st.session_state.selected_categories
        st.session_state.selected_categories = [
            category for category in current_selected_categories
            if category in available_categories_for_type
        ]

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

            if tests_list:
                df = pd.DataFrame(tests_list)

                columns_to_show = ['tenantId', "testType", "recordedDateUtc", "analysedDateUtc", "weight", "notes"]
                df_display = df.reindex(columns=columns_to_show, fill_value='').copy()
                df_display.insert(0, "Test Number", range(len(df_display)))
                df_display.columns = ["Test Number", "Tenant ID", "Test Type", "Recorded Date", "Analysed Date", "Weight (kg)", "Notes"]

                df_display["Recorded Date"] = pd.to_datetime(df_display["Recorded Date"], format='ISO8601', errors='coerce').dt.strftime("%Y-%m-%d %H:%M")
                df_display["Analysed Date"] = pd.to_datetime(df_display["Analysed Date"], format='ISO8601', errors='coerce').dt.strftime("%Y-%m-%d %H:%M")

                st.dataframe(df_display, use_container_width=True)
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
                    if available_categories_for_type:
                        selected_categories = st.multiselect(
                            "Select metric categories:",
                            options=available_categories_for_type,
                            default=st.session_state.selected_categories,
                            key="categories_multiselect"
                        )
                        st.session_state.selected_categories = selected_categories
                    else:
                        st.info(f"No metric categories configured for test type: {type_of_test}")
                        selected_categories = []

                    if st.button("Prepare data", key="prepare_data"):
                        if not selected_categories:
                            st.warning("Select at least one category before preparing data.")
                        else:
                            with st.spinner("Preparing comparison data..."):
                                available_metric_entries = extract_available_metrics_from_tests(st.session_state.tests_details_all)
                                resolved_category_metrics, unmatched_category_metrics = resolve_category_metrics_for_test_type(
                                    type_of_test,
                                    available_metric_entries
                                )

                                st.session_state.resolved_category_metrics = resolved_category_metrics
                                st.session_state.unmatched_category_metrics = unmatched_category_metrics

                                selected_metrics = []
                                for category in selected_categories:
                                    selected_metrics.extend(resolved_category_metrics.get(category, []))

                                selected_metrics = list(dict.fromkeys(selected_metrics))
                                st.session_state.selected_metrics = selected_metrics

                                if not selected_metrics:
                                    st.session_state.prepared_summary_data = None
                                    st.session_state.prepared_comparison_data = None
                                    st.warning("None of the metrics from the selected categories were found in the loaded tests.")
                                else:
                                    summary_df, trials_data_per_test = prepare_tests_for_comparison(
                                        st.session_state.tests_details_all,
                                        selected_metrics
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
                        st.dataframe(st.session_state.prepared_summary_data, use_container_width=True)

                        with st.expander("Debug: matched and unmatched metrics"):
                            st.write("Selected categories:", st.session_state.selected_categories)
                            st.write("Matched metrics by category:", st.session_state.resolved_category_metrics)
                            st.write("Unmatched metrics by category:", st.session_state.unmatched_category_metrics)
                            st.write("Final selected metrics:", st.session_state.selected_metrics)
                            st.write("Columns in prepared summary data:", list(st.session_state.prepared_summary_data.columns))

                        col_btn, col_chk = st.columns([1, 2])

                        with col_btn:
                            if st.button("Generate graphs", key="generate_graphs"):
                                st.session_state.graphs_generated = True

                        with col_chk:
                            st.checkbox(
                                "Use time scale on X axis",
                                value=st.session_state.use_time_axis,
                                key="use_time_axis"
                            )

                    if (
                        st.session_state.graphs_generated
                        and st.session_state.prepared_summary_data is not None
                        and not st.session_state.prepared_summary_data.empty
                    ):
                        st.subheader("Graphs by category")

                        resolved_category_metrics = st.session_state.get("resolved_category_metrics", {})

                        for category in st.session_state.selected_categories:
                            category_metrics = resolved_category_metrics.get(category, [])

                            with st.expander(category, expanded=True):
                                plotted_any = False

                                for metric in category_metrics:
                                    fig = create_mean_std_chart(
                                        st.session_state.prepared_summary_data,
                                        metric,
                                        use_time_axis=st.session_state.use_time_axis
                                    )
                                    if fig:
                                        st.plotly_chart(fig, use_container_width=True)
                                        plotted_any = True

                                if not plotted_any:
                                    st.info(f"No graphs available for category: {category}")

            else:
                st.info("No training sessions found.")
        else:
            st.error("There are no training sessions or failed to load data. Try adjusting the date filter or refreshing the data.")

    else:
        pass


if __name__ == "__main__":
    main()