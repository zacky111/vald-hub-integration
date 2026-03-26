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
from src.visualizations import (
    create_sample_data,
    create_force_plot,
    create_power_velocity_plot,
    create_metrics_comparison,
    create_athlete_summary
)


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
                st.warning("⚠️ Using sample data (API not connected)")
                st.info("Configure `.env` file with your Vald Hub credentials")
        except Exception as e:
            st.error(f"API Error: {str(e)}")
        
        # Refresh data
        if st.button("🔄 Refresh Data", use_container_width=True):
            if 'data' in st.session_state:
                del st.session_state.data
            st.rerun()
        
        st.divider()


        #obtaining data for dropdowns
        profiles_data = client.get_profiles()
        groups_data = client.get_groups()
        
        # Athlete Selection
        st.subheader("Select Athlete")
        try:
            
            if profiles_data and 'profiles' in profiles_data:
                athletes = profiles_data['profiles']
                athlete_names = [
                    f"{a.get('familyName', '')} {a.get('givenName', 'Unknown')}" 
                    for a in athletes
                ]
                
                if athlete_names:
                    selected_athlete = st.selectbox(
                        "Choose athlete",
                        sorted(athlete_names),
                        key="athlete_selector"
                    )
                    st.session_state.selected_athlete = selected_athlete
                    
                    #to be deleted later on
                    athlete_id = profiles_data['profiles'][athlete_names.index(selected_athlete)].get('profileId', 'N/A')
                    st.write(f"**Athlete ID:** {athlete_id}")

                    athlete_details = client.get_profiles_details(athlete_id)
                    st.write(f"**Athlete Groups - ID:** {athlete_details['groupIds']}")
                    
                    group_details = client.get_group_details(athlete_details['groupIds'][0]) if athlete_details['groupIds'] else None
                    st.write(f"**Athlete Groups - Name:** {group_details['name'] if group_details['name'] != '' else 'N/A'}")

                    athlete_weight = profiles_data['profiles'][athlete_names.index(selected_athlete)].get('weight', 'N/A')
                    athlete_date_of_birth = profiles_data['profiles'][athlete_names.index(selected_athlete)].get('dateOfBirth', 'N/A')

                    st.write(f"**Weight:** {athlete_weight} kg")
                    st.write(f"**Date of Birth:** {athlete_date_of_birth[:10 if athlete_date_of_birth != 'N/A' else None]}")  # Show only date part

                else:
                    st.warning("No athletes found")
            else:
                st.warning("Could not load athletes")
        except Exception as e:
            st.error(f"Error loading athletes: {str(e)}")
        
        st.divider()
        
        # Group Selection
        st.subheader("Select Group")
        try:
            
            
            if groups_data and 'groups' in groups_data:
                groups = groups_data['groups']
                group_names = [g.get('name', 'Unknown') for g in groups]
                
                if group_names:
                    selected_group = st.selectbox(
                        "Choose group",
                        sorted(group_names),
                        key="group_selector"
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
            ["Overview", "Athlete Analysis", "Trends"]
        )
    

    
    
    # Main content based on display mode
    if display_mode == "Overview":
        try:
            st.write("API Version: ", client.get_version())
        except Exception as e:
            st.error(f"Could not fetch data: {str(e)}")
    elif display_mode == "Athlete Analysis":
        pass
    else:
        pass
    

if __name__ == "__main__":
    main()
