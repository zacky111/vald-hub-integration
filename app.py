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
from src.visualizations import create_mean_std_chart, create_left_right_chart

from src.data_prep_funcs import parse_excluded_tests, group_metrics_by_base
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
        "body-weight": "bodyweight",
        "flight time": "flighttime",
        "jump height ft": "jumpheightflighttime",
        "rsi modified": "rsimodified",
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


def extract_metric_record(result: dict):
    """
    Unified metric extractor from API result.
    Returns normalized metadata for easier matching/debugging.
    """
    definition = result.get("definition", {}) or {}
    metric_name = definition.get("name")
    metric_key = definition.get("result") or definition.get("id") or result.get("resultId")
    limb = result.get("limb", "Trial")
    value = result.get("value")

    if not metric_name:
        return None

    base_name, full_name = split_metric_and_limb(metric_name, limb)

    return {
        "metric_key": str(metric_key) if metric_key is not None else None,
        "metric_name": metric_name,
        "base_name": base_name,
        "full_name": full_name,
        "limb": limb,
        "value": value,
        "unit": definition.get("unit"),
        "description": definition.get("description"),
        "result_id": result.get("resultId"),
        "normalized_metric_key": normalize_metric_name(metric_key) if metric_key is not None else "",
        "normalized_name": normalize_metric_name(metric_name),
        "normalized_base": normalize_metric_name(base_name),
        "normalized_full": normalize_metric_name(full_name),
    }


def extract_available_metrics_from_tests(tests_details_all):
    """
    Zwraca listę wszystkich metryk dostępnych w pobranych testach.
    Każdy element:
    {
        "metric_key": ...,
        "metric_name": ...,
        "base_name": ...,
        "full_name": ...,
        "limb": ...,
        "normalized_metric_key": ...,
        "normalized_name": ...,
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
                record = extract_metric_record(result)
                if not record:
                    continue

                key = (
                    record["metric_key"],
                    record["base_name"],
                    record["full_name"],
                    record["limb"],
                )

                if key in seen:
                    continue

                seen.add(key)
                available_entries.append(record)

    return available_entries


def resolve_category_metrics_for_test_type(test_type, available_metric_entries):
    """
    Dopasowuje metryki z configu kategorii do realnych metryk z API.
    Matching jest bardziej ostrożny niż wcześniej:
    1. exact base match
    2. exact full match
    3. exact metric name match
    4. exact metric key match
    5. token / partial match

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
            matched_entries = []

            # 1. exact base match
            matched_entries = [
                entry["full_name"]
                for entry in available_metric_entries
                if entry["normalized_base"] == normalized_config
            ]

            # 2. exact full match
            if not matched_entries:
                matched_entries = [
                    entry["full_name"]
                    for entry in available_metric_entries
                    if entry["normalized_full"] == normalized_config
                ]

            # 3. exact metric name match
            if not matched_entries:
                matched_entries = [
                    entry["full_name"]
                    for entry in available_metric_entries
                    if entry["normalized_name"] == normalized_config
                ]

            # 4. exact metric key match
            if not matched_entries:
                matched_entries = [
                    entry["full_name"]
                    for entry in available_metric_entries
                    if entry["normalized_metric_key"] == normalized_config
                ]

            # 5. partial match - ostrożniejszy
            if not matched_entries:
                matched_entries = [
                    entry["full_name"]
                    for entry in available_metric_entries
                    if (
                        normalized_config in entry["normalized_base"]
                        or normalized_config in entry["normalized_name"]
                        or normalized_config in entry["normalized_full"]
                        or entry["normalized_base"] in normalized_config
                    )
                ]

            matched_entries = list(dict.fromkeys(matched_entries))

            if matched_entries:
                for metric in matched_entries:
                    if metric not in resolved[category]:
                        resolved[category].append(metric)
            else:
                unmatched[category].append(config_metric)

    return resolved, unmatched


def build_comparison_df_for_test_trials(test_trials):
    """
    Buduje dataframe trial x metric ze WSZYSTKIMI metrykami z API.
    NIE odcina żadnych kolumn.
    """
    comparison_data = {}

    for i, trial in enumerate(test_trials):
        trial_id = f"Trial {i + 1}"

        if "results" not in trial:
            continue

        for result in trial["results"]:
            record = extract_metric_record(result)
            if not record:
                continue

            full_metric_name = record["full_name"]
            value = record["value"]

            if full_metric_name not in comparison_data:
                comparison_data[full_metric_name] = {}

            comparison_data[full_metric_name][trial_id] = value

    if not comparison_data:
        return pd.DataFrame()

    comp_df = pd.DataFrame.from_dict(comparison_data, orient="index").transpose()
    return comp_df


def find_jump_height_column(df: pd.DataFrame):
    """
    Znajduje najlepszą kolumnę do sortowania top 3 prób.
    Preferowana:
    - Jump Height (Flight Time)
    Fallback:
    - Jump Height...
    """
    preferred = "Jump Height (Flight Time)"
    if preferred in df.columns:
        return preferred

    candidates = [c for c in df.columns if "Jump Height" in str(c)]
    if candidates:
        return candidates[0]

    return None


def prepare_tests_for_comparison(tests_details_all, selected_metrics=None, use_all_metrics=False):
    """
    Dla każdego testu:
    - zbiera WSZYSTKIE metryki per trial (Trial, Left, Right, Asym, itd.)
    - wybiera top 3 próby wg Jump Height (Flight Time) lub fallback Jump Height*
    - liczy mean i std dla:
        * selected_metrics, albo
        * wszystkich metryk jeśli use_all_metrics=True

    Zwraca:
    - summary_df
    - trials_data_per_test
    """
    selected_metrics = selected_metrics or []

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

        comp_df = build_comparison_df_for_test_trials(test_trials)

        if comp_df.empty:
            continue

        trials_df = comp_df[comp_df.index.to_series().str.startswith("Trial")].copy()
        if trials_df.empty:
            continue

        jump_height_metric = find_jump_height_column(trials_df)

        if jump_height_metric:
            trials_df[jump_height_metric] = pd.to_numeric(trials_df[jump_height_metric], errors="coerce")
            trials_df_for_sort = trials_df.dropna(subset=[jump_height_metric]).copy()
        else:
            trials_df_for_sort = trials_df.copy()

        if trials_df_for_sort.empty:
            continue

        if jump_height_metric:
            top3_indices = trials_df_for_sort[jump_height_metric].nlargest(min(3, len(trials_df_for_sort))).index.tolist()
        else:
            top3_indices = trials_df_for_sort.index[:min(3, len(trials_df_for_sort))].tolist()

        if not top3_indices:
            continue

        best3_df = trials_df.loc[top3_indices].copy()

        if use_all_metrics:
            metrics_to_use = list(best3_df.columns)
        else:
            metrics_to_use = [m for m in selected_metrics if m in best3_df.columns]

        if jump_height_metric and jump_height_metric in best3_df.columns and jump_height_metric not in metrics_to_use:
            metrics_to_use = [jump_height_metric] + metrics_to_use

        metrics_to_use = list(dict.fromkeys(metrics_to_use))

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
            "Best Jump Height": trials_df.loc[top3_indices[0], jump_height_metric] if jump_height_metric and top3_indices else None,
            "Jump Height Metric Used": jump_height_metric if jump_height_metric else "None",
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
            "jump_height_metric_used": jump_height_metric,
            "all_metric_columns": list(trials_df.columns),
        }

    summary_df = pd.DataFrame(summary_rows)
    return summary_df, trials_data_per_test


def get_all_trial_metric_names(specific_test_details):
    """
    Returns all Trial-level metric names from single-test details.
    """
    metric_names = set()

    if not isinstance(specific_test_details, list):
        return []

    for trial in specific_test_details:
        for result in trial.get("results", []):
            record = extract_metric_record(result)
            if not record:
                continue
            if record["limb"] == "Trial":
                metric_names.add(record["metric_name"])

    return sorted(metric_names)


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
                'unmatched_category_metrics', 'use_all_metrics_multi'
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
                                    col3.metric(
                                        "Recorded date",
                                        pd.to_datetime(selected_test.get('recordedDateUtc'), format='ISO8601', errors='coerce').strftime("%Y-%m-%d %H:%M")
                                        if selected_test.get('recordedDateUtc') else 'Unknown'
                                    )

                                    if isinstance(specific_test_details, list) and specific_test_details:
                                        st.write(f"**Number of trials:** {len(specific_test_details)}")

                                        available_trial_metrics = get_all_trial_metric_names(specific_test_details)

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

                                        selected_overview_metrics = st.multiselect(
                                            "Select Trial-level metrics for trial comparison:",
                                            options=available_trial_metrics,
                                            default=default_metrics,
                                            key=f"overview_metrics_{test_id}"
                                        )

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
                                            with st.expander("Metrics Comparison Across Trials", expanded=True):
                                                st.subheader("Metrics Comparison Across Trials")
                                                comp_df = pd.DataFrame.from_dict(comparison_data, orient='index').transpose()
                                                comp_df.drop(columns='Bodyweight in Kilograms', inplace=True, errors='ignore')

                                                trials_df = comp_df[comp_df.index.to_series().str.startswith('Trial')].copy()

                                                for col in trials_df.columns:
                                                    trials_df[col] = pd.to_numeric(trials_df[col], errors='coerce')

                                                average_all = trials_df.mean(numeric_only=True)
                                                std_all = trials_df.std(numeric_only=True)
                                                cv_all = (std_all / average_all.replace(0, pd.NA)) * 100

                                                jump_height_col = find_jump_height_column(trials_df)
                                                top3_indices = []
                                                best_trial = None

                                                if jump_height_col and jump_height_col in trials_df.columns and not trials_df.empty:
                                                    top3_values = trials_df[jump_height_col].dropna().nlargest(min(3, len(trials_df.dropna(subset=[jump_height_col]))))
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

                                                styled_table = table_df.style.apply(_style_rows, axis=1)
                                                st.dataframe(styled_table, use_container_width=True)

                                                st.markdown("""
                                                **Legenda kolorów:**
                                                - 🟩 **Ciemnozielony** - najlepsza próba
                                                - 🟩 **Jasnozielony** - top 3 próby
                                                - 🟨 **Złoty** - średnie wartości
                                                - 🟦 **Jasnoniebieski** - odchylenia standardowe i CV
                                                """)

                                            with st.expander("Visualize Metrics Across Trials", expanded=True):
                                                st.subheader("Comparison Visualizations")
                                                for metric in selected_overview_metrics:
                                                    fig = create_metrics_comparison_chart(trials_df, metric)
                                                    if fig:
                                                        st.plotly_chart(fig, use_container_width=True)

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
                                                st.dataframe(df_results, use_container_width=True)

                                            asym_df = df_results[df_results['Limb'].isin(['Left', 'Right', 'Asym'])]
                                            if not asym_df.empty:
                                                with st.expander("Limb Asymmetry Analysis", expanded=True):
                                                    st.subheader("Limb Asymmetries")
                                                    for metric in asym_df['Metric Name'].dropna().unique():
                                                        fig_asym = create_limb_asymmetry_chart(asym_df, metric)
                                                        if fig_asym:
                                                            st.plotly_chart(fig_asym, use_container_width=True)
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
                        st.dataframe(available_df, use_container_width=True)

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

                        with st.expander("Debug: matched and unmatched metrics", expanded=False):
                            st.write("Use all metrics mode:", use_all_metrics_multi)
                            st.write("Selected categories:", st.session_state.selected_categories)
                            st.write("Matched metrics by category:", st.session_state.resolved_category_metrics)
                            st.write("Unmatched metrics by category:", st.session_state.unmatched_category_metrics)
                            st.write("Final selected metrics count:", len(st.session_state.selected_metrics))
                            st.write("Final selected metrics:", st.session_state.selected_metrics[:200])
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
                                        use_time_axis=st.session_state.use_time_axis
                                    )
                                    if fig:
                                        st.plotly_chart(fig, use_container_width=True)
                        else:
                            resolved_category_metrics = st.session_state.get("resolved_category_metrics", {})

                            for category in st.session_state.selected_categories:
                                category_metrics = resolved_category_metrics.get(category, [])

                                with st.expander(category, expanded=True):
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
                                                use_time_axis=st.session_state.use_time_axis
                                            )
                                            if fig:
                                                st.plotly_chart(fig, use_container_width=True)
                                                plotted_any = True

                                            # opcjonalnie dalej pokaż Trial osobno, jeśli istnieje
                                            if "Trial" in metric_map:
                                                fig = create_mean_std_chart(
                                                    st.session_state.prepared_summary_data,
                                                    metric_map["Trial"],
                                                    use_time_axis=st.session_state.use_time_axis
                                                )
                                                if fig:
                                                    st.plotly_chart(fig, use_container_width=True)
                                                    plotted_any = True

                                        else:
                                            # fallback: rysuj wszystko co jest, w tym Asym
                                            for limb, metric in metric_map.items():
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