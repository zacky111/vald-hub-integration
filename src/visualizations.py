import pandas as pd
import plotly.express as px


def create_metrics_comparison_chart(comp_df, metric):
    """
    Create a scatter plot with lines for a specific metric across trials, including average line.
    
    Args:
        comp_df (pd.DataFrame): DataFrame with trials as rows and metrics as columns
        metric (str): The metric name to plot
    
    Returns:
        plotly.graph_objects.Figure: The scatter plot figure
    """
    if metric not in comp_df.columns:
        return None

    trials_df = comp_df.loc[comp_df.index.to_series().str.startswith('Trial')]
    metric_data = trials_df[metric].dropna()

    if len(metric_data) > 1:
        fig = px.scatter(
            x=metric_data.index,
            y=metric_data.values,
            title=f'{metric} Across Trials',
            labels={'x': 'Trial', 'y': 'Value'}
        )
        fig.update_traces(mode='lines+markers')
        
        # Add horizontal line for average
        avg_value = metric_data.mean()
        fig.add_hline(y=avg_value, line_dash="dash", line_color="red", annotation_text=f"Average: {avg_value:.2f}")
        
        return fig

    return None


def create_limb_asymmetry_chart(asym_df, metric):
    """
    Create a bar chart for limb asymmetry for a specific metric.
    
    Args:
        asym_df (pd.DataFrame): DataFrame with limb data
        metric (str): The metric name to plot
    
    Returns:
        plotly.graph_objects.Figure: The bar chart figure
    """
    metric_data = asym_df[asym_df['Metric Name'] == metric]
    if len(metric_data) >= 2:  # At least left and right
        fig = px.bar(
            metric_data, 
            x='Limb', 
            y='Value', 
            title=f'{metric} by Limb',
            color='Limb'
        )
        return fig
    return None