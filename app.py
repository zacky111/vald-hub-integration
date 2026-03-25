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
    st.title("⚡ Vald Hub Performance Dashboard")
    st.markdown("*Real-time athlete performance monitoring and analysis*")
    
    # Sidebar
    with st.sidebar:
        st.header("Configuration")
        
        # API Status
        client = ValdHubClient()
        api_connected = client.get_token(client.client_id, client.client_secret)
        
        if api_connected:
            st.success("✅ Connected to Vald Hub API. ")
        else:
            st.warning("⚠️ Using sample data (API not connected)")
            st.info("Configure `.env` file with your Vald Hub credentials")
        
        # Refresh data
        if st.button("🔄 Refresh Data", use_container_width=True):
            if 'data' in st.session_state:
                del st.session_state.data
            st.rerun()
        
        st.divider()
        
        # Settings
        st.subheader("Settings")
        display_mode = st.radio(
            "Display Mode",
            ["Overview", "Athlete Analysis", "Trends"]
        )
    
    # Load or fetch data
    if 'data' not in st.session_state:
        with st.spinner("Loading athlete data..."):
            # Try to get real data, fall back to sample
            try:
                client = ValdHubClient()
                athletes = client.get_athletes()
                if athletes:
                    st.session_state.data = {
                        'athletes': athletes,
                        'metrics': {}
                    }
                else:
                    st.session_state.data = create_sample_data()
            except Exception as e:
                st.warning(f"Could not fetch data: {e}. Using sample data.")
                st.session_state.data = create_sample_data()
    
    data = st.session_state.data
    
    # Main content based on display mode
    if display_mode == "Overview":
        show_overview(data)
    elif display_mode == "Athlete Analysis":
        show_athlete_analysis(data)
    else:
        show_trends(data)


def show_overview(data):
    """Display overview dashboard"""
    st.header("Performance Overview")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Athletes", len(data['athletes']))
    with col2:
        st.metric("Avg Force", f"{sum(data['metrics']['force_data']) / len(data['metrics']['force_data']):.0f} N")
    with col3:
        st.metric("Avg Power", f"{sum(data['metrics']['power_data']) / len(data['metrics']['power_data']):.0f} W")
    with col4:
        st.metric("Avg Velocity", f"{sum(data['metrics']['velocity_data']) / len(data['metrics']['velocity_data']):.2f} m/s")
    
    st.divider()
    
    # Visualizations
    col1, col2 = st.columns(2)
    
    with col1:
        st.plotly_chart(create_force_plot(data), use_container_width=True)
    with col2:
        st.plotly_chart(create_power_velocity_plot(data), use_container_width=True)
    
    st.plotly_chart(create_metrics_comparison(data), use_container_width=True)
    
    # Athletes table
    st.subheader("Athletes List")
    athletes_df = create_athlete_summary(data['athletes'])
    st.dataframe(athletes_df, use_container_width=True)


def show_athlete_analysis(data):
    """Display individual athlete analysis"""
    st.header("Athlete Analysis")
    
    athletes_list = [a.get('name', f"Athlete {a.get('id')}") for a in data['athletes']]
    selected_athlete = st.selectbox("Select Athlete", athletes_list)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.plotly_chart(create_force_plot(data, selected_athlete), use_container_width=True)
    with col2:
        st.plotly_chart(create_power_velocity_plot(data, selected_athlete), use_container_width=True)


def show_trends(data):
    """Display trends analysis"""
    st.header("Performance Trends")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Force Trend")
        st.plotly_chart(create_force_plot(data), use_container_width=True)
    
    with col2:
        st.subheader("Metrics Comparison")
        st.plotly_chart(create_metrics_comparison(data), use_container_width=True)
    
    # Statistics
    st.subheader("Statistics")
    col1, col2, col3 = st.columns(3)
    
    force_data = data['metrics']['force_data']
    power_data = data['metrics']['power_data']
    velocity_data = data['metrics']['velocity_data']
    
    with col1:
        st.metric("Force Range", f"{max(force_data) - min(force_data):.0f} N")
    with col2:
        st.metric("Power Range", f"{max(power_data) - min(power_data):.0f} W")
    with col3:
        st.metric("Velocity Range", f"{max(velocity_data) - min(velocity_data):.2f} m/s")


if __name__ == "__main__":
    main()
