import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Dict, Any
from datetime import datetime, timedelta
import random


def create_sample_data() -> Dict[str, Any]:
    """Generate sample data when API is not available (for development)"""
    dates = [datetime.now() - timedelta(days=i) for i in range(30, -1, -1)]
    
    athletes = [
        {
            'id': f'athlete_{i}',
            'name': f'Athlete {i}',
            'sport': random.choice(['Rugby', 'Soccer', 'American Football', 'Gymnastics']),
            'team': f'Team {random.choice(["A", "B", "C"])}'
        }
        for i in range(5)
    ]
    
    metrics = {
        'dates': dates,
        'force_data': [random.uniform(1000, 3000) for _ in dates],
        'power_data': [random.uniform(500, 2000) for _ in dates],
        'velocity_data': [random.uniform(1.0, 4.0) for _ in dates],
    }
    
    return {
        'athletes': athletes,
        'metrics': metrics
    }


def create_force_plot(data: Dict[str, Any], athlete_name: str = "All Athletes"):
    """Create force production visualization"""
    df = pd.DataFrame({
        'Date': data['metrics']['dates'],
        'Force (N)': data['metrics']['force_data']
    })
    
    fig = px.line(
        df,
        x='Date',
        y='Force (N)',
        title=f'Force Production Over Time - {athlete_name}',
        markers=True,
        line_shape='spline'
    )
    fig.update_layout(
        hovermode='x unified',
        template='plotly_dark',
        height=400,
        xaxis_title='Date',
        yaxis_title='Force (Newtons)'
    )
    return fig


def create_power_velocity_plot(data: Dict[str, Any], athlete_name: str = "All Athletes"):
    """Create power vs velocity scatter plot"""
    df = pd.DataFrame({
        'Velocity (m/s)': data['metrics']['velocity_data'],
        'Power (W)': data['metrics']['power_data'],
        'Date': data['metrics']['dates']
    })
    
    fig = px.scatter(
        df,
        x='Velocity (m/s)',
        y='Power (W)',
        title=f'Power vs Velocity - {athlete_name}',
        hover_name='Date',
        size_max=15,
        trendline='ols',
        trendline_color_override='red'
    )
    fig.update_layout(
        template='plotly_dark',
        height=400,
        hovermode='closest'
    )
    return fig


def create_metrics_comparison(data: Dict[str, Any]):
    """Create comparison of different metrics"""
    df = pd.DataFrame({
        'Date': data['metrics']['dates'],
        'Force (normalized)': normalize_data(data['metrics']['force_data']),
        'Power (normalized)': normalize_data(data['metrics']['power_data']),
        'Velocity (normalized)': normalize_data(data['metrics']['velocity_data'])
    })
    
    fig = px.area(
        df,
        x='Date',
        y=['Force (normalized)', 'Power (normalized)', 'Velocity (normalized)'],
        title='Normalized Metrics Comparison',
    )
    fig.update_layout(
        template='plotly_dark',
        height=400,
        hovermode='x unified'
    )
    return fig


def create_athlete_summary(athletes: List[Dict]) -> pd.DataFrame:
    """Create summary dataframe of athletes"""
    return pd.DataFrame(athletes)


def normalize_data(data: List[float]) -> List[float]:
    """Normalize data to 0-1 range"""
    min_val = min(data)
    max_val = max(data)
    range_val = max_val - min_val
    if range_val == 0:
        return [0.5] * len(data)
    return [(x - min_val) / range_val for x in data]
