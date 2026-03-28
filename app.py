from xmlrpc import client

from plotly import data
import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.vald_client import ValdHubClient
from src.visualizations import create_metrics_comparison_chart, create_limb_asymmetry_chart


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
    
    # Custom CSS
    st.markdown("""
    <style>
    .main {
        padding: 0rem 0rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.title("Vald Hub Performance Dashboard")
    st.markdown("*Real-time athlete performance monitoring and analysis*")
    
    # Sidebar
    with st.sidebar:

        st.header("Configuration")
        
        # Get cached client instance
        client = get_vald_client()
        
        # API Status
        try:
            api_connected = client.get_token(client.client_id, client.client_secret)
            
            if api_connected:
                st.success("✅ Connected to Vald Hub API. ")
            else:
                st.info("Configure `.env` file with your Vald Hub credentials")
        except Exception as e:
            st.error(f"API Error: {str(e)}")
        
        # Refresh data
        if st.button("🔄 Refresh Data", use_container_width=True):
            if 'data' in st.session_state:
                del st.session_state.data
            # Clear cached data
            for key in ['profiles_data', 'groups_data', 'athlete_details', 'group_details']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        
        st.divider()


        #obtaining data for dropdowns - cached
        if 'profiles_data' not in st.session_state:
            st.session_state.profiles_data = client.get_profiles()
        profiles_data = st.session_state.profiles_data
        
        if 'groups_data' not in st.session_state:
            st.session_state.groups_data = client.get_groups()
        groups_data = st.session_state.groups_data
        
        # Athlete Selection
        st.sidebar.markdown("## Athlete")
        try:
            # Cache athlete data to avoid reloading on button clicks
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
                    
                    #to be deleted later on
                    athlete_id = profiles_data['profiles'][athlete_names.index(selected_athlete)].get('profileId', 'N/A')
                    st.write(f"**Athlete ID:** {athlete_id}")

                    # Cache athlete details
                    if 'athlete_details' not in st.session_state or st.session_state.get('current_athlete_id') != athlete_id:
                        st.session_state.athlete_details = client.get_profiles_details(athlete_id)
                        st.session_state.current_athlete_id = athlete_id
                    athlete_details = st.session_state.athlete_details
                    
                    st.write(f"**Athlete Groups - ID:** {athlete_details['groupIds']}")
                    
                    # Cache group details
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
        
        # Group Selection
        st.sidebar.markdown("## Group")
        try:
            # Cache groups data
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
        
        # Settings
        st.subheader("Settings")
        display_mode = st.radio(
            "Display Mode",
            ["Overview - Single Training", "Multiple trainings comparison", "Trends"]
        )
    

    
    
    # Main content based on display mode
    if display_mode == "Overview - Single Training":
        try:
            st.header("Training Sessions Overview")

            # Date filter for training sessions
            default_from = datetime.now().date() - pd.Timedelta(days=30)
            modified_from = st.date_input(
                "Show sessions from date:",
                value=default_from,
                key="modified_from"
            )

            # Convert to API-required UTC ISO format
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
                    # Select and rename columns for better display
                    columns_to_show = [
                        "testId", "profileId", "testType", "recordedDateUtc", 
                        "analysedDateUtc", "weight", "notes"
                    ]
                    df_display = df.reindex(columns=columns_to_show, fill_value='').copy()
                    df_display.columns = [
                        "Test ID", "Profile ID", "Test Type", "Recorded Date", 
                        "Analysed Date", "Weight (kg)", "Notes"
                    ]
                    # Format dates
                    df_display["Recorded Date"] = pd.to_datetime(df_display["Recorded Date"], format='ISO8601', errors='coerce').dt.strftime("%Y-%m-%d %H:%M")
                    df_display["Analysed Date"] = pd.to_datetime(df_display["Analysed Date"], format='ISO8601', errors='coerce').dt.strftime("%Y-%m-%d %H:%M")
                    
                    st.dataframe(df_display, use_container_width=True)
                    
                    st.write(f"**Total sessions:** {len(tests_list)}")
                    
                    # Test selection for details
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
                                    

                                    # Handle the response as a list of trials
                                    if isinstance(specific_test_details, list) and specific_test_details:
                                        # Display number of trials
                                        st.write(f"**Number of trials:** {len(specific_test_details)}")
                                        
                                        # Collect key metrics across all trials for comparison
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
                                        
                                        # Display comparison table
                                        if comparison_data:
                                            with st.expander("Metrics Comparison Across Trials"):
                                                st.subheader("Metrics Comparison Across Trials")
                                                comp_df = pd.DataFrame.from_dict(comparison_data, orient='index')
                                                comp_df = comp_df.transpose()  # Trials as rows, metrics as columns
                                                comp_df.drop(columns='Bodyweight in Kilograms', inplace=True, errors='ignore')  # Remove bodyweight if present

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
                                                
                                                # Display legend
                                                st.markdown("""
                                                **Legenda kolorów:**
                                                - 🟩 **Ciemnozielony** - najlepsza próba (najwyższa wartość Jump Height)
                                                - 🟩 **Jasnozielony** - top 3 próby
                                                - 🟨 **Złoty** - średnie wartości (Average, Average from Best 3)
                                                - 🟦 **Jasnoniebieski** - odchylenia standardowe i współczynnik zmienności (Std, CV)
                                                """)

                                            # Visualization: Bar chart for each metric across trials
                                            with st.expander("Visualize Metrics Across Trials"):
                                                st.subheader("Comparison Visualizations")
                                                for metric in key_metrics_for_comparison:
                                                    fig = create_metrics_comparison_chart(trials_df, metric)
                                                    if fig:
                                                        st.plotly_chart(fig, use_container_width=True)
                                        
                                        # For simplicity, show detailed results from the first trial
                                        # You can add a selector for multiple trials if needed
                                        trial = specific_test_details[0]
                                        #t.subheader(f"Detailed Results from Trial 1 (ID: {trial.get('id', 'N/A')})")
                                        
                                        if 'results' in trial and trial['results']:
                                            results = trial['results']
                                            
                                            # Create DataFrame for better display
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
                                            
                                            #st.dataframe(df_results, use_container_width=True)
                                            
                                            # Summary stats
                                            #st.write(f"**Total metrics:** {len(results)}")
                                            
                                            # Optional: Highlight key metrics
                                            #key_metrics = ['Bodyweight', 'Countermovement Depth', 'Start of Movement']
                                            #filtered_df = df_results[df_results['Metric Name'].str.contains('|'.join(key_metrics), case=False, na=False)]
                                            #if not filtered_df.empty:
                                            #    st.subheader("Key Performance Metrics")
                                            #    st.dataframe(filtered_df, use_container_width=True)
                                            
                                            
                                            # Asymmetry visualization if available
                                            asym_df = df_results[df_results['Limb'].isin(['Left', 'Right', 'Asym'])]
                                            if not asym_df.empty:
                                                with st.expander("Limb Asymmetry Analysis"):
                                                    st.subheader("Limb Asymmetries")
                                                    # Group by metric name and show left/right comparison
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

        # Date filter for training sessions
        default_from = datetime.now().date() - pd.Timedelta(days=30)
        
        # Filters for searching - date from, date to, type of test
        col1, col2, col3 = st.columns(3)
        with col1:
            modified_from = st.date_input(
            "Show sessions from date:",
            value=default_from,
            key="modified_from"
        )
            
        with col2:
            modified_to = st.date_input(
                "Show sessions until date:",
                value=datetime.now().date(),
                key="modified_to"
            )

        with col3:
            type_of_test = st.selectbox(
                "Select test type:",
                ["All", "CMJ"],
                key="test_type_selector"
            )

        # Convert to API-required UTC ISO format
        modified_from_utc = datetime.combine(modified_from, datetime.min.time()).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        modified_to_utc = datetime.combine(modified_to, datetime.max.time()).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        st.caption(f"Current filter: date from {modified_from_utc[:10]} to {modified_to_utc[:10]}")


        data = client.get_training_sessions_all(
            profile_id=athlete_id,
            modified_from_utc=modified_from_utc,
        )

        
        if data and "tests" in data:
            tests_list = data["tests"]
            if tests_list:
                df = pd.DataFrame(tests_list)
                # Select and rename columns for better display
                columns_to_show = [
                    "testId", "profileId", "testType", "recordedDateUtc", 
                    "analysedDateUtc", "weight", "notes"
                ]
                df_display = df.reindex(columns=columns_to_show, fill_value='').copy()
                df_display.columns = [
                    "Test ID", "Profile ID", "Test Type", "Recorded Date", 
                    "Analysed Date", "Weight (kg)", "Notes"
                ]
                # Format dates
                df_display["Recorded Date"] = pd.to_datetime(df_display["Recorded Date"], format='ISO8601', errors='coerce').dt.strftime("%Y-%m-%d %H:%M")
                df_display["Analysed Date"] = pd.to_datetime(df_display["Analysed Date"], format='ISO8601', errors='coerce').dt.strftime("%Y-%m-%d %H:%M")
                
                st.dataframe(df_display, use_container_width=True)
                


    else:
        pass
    

if __name__ == "__main__":
    main()
