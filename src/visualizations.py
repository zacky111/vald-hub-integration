import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


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
    if len(metric_data) >= 2:
        fig = px.bar(
            metric_data,
            x='Limb',
            y='Value',
            title=f'{metric} by Limb',
            color='Limb'
        )
        return fig
    return None


def create_mean_std_chart(summary_df, metric_name, use_time_axis=False):
    """
    Tworzy wykres dla jednej metryki:
    - punkt = mean
    - pionowa kreska = std
    - X = czas albo kolejność testów
    """
    mean_col = f"{metric_name} Mean"
    std_col = f"{metric_name} Std"

    if mean_col not in summary_df.columns or std_col not in summary_df.columns:
        return None

    required_cols = ["Test", "Test Order", "Plot Date", mean_col, std_col]
    if not all(col in summary_df.columns for col in required_cols):
        return None

    plot_df = summary_df[required_cols].copy()
    plot_df[mean_col] = pd.to_numeric(plot_df[mean_col], errors="coerce")
    plot_df[std_col] = pd.to_numeric(plot_df[std_col], errors="coerce")
    plot_df["Plot Date"] = pd.to_datetime(plot_df["Plot Date"], errors="coerce", utc=True)

    plot_df = plot_df.dropna(subset=[mean_col])

    if plot_df.empty:
        return None

    plot_df = plot_df.sort_values("Test Order")

    if use_time_axis:
        plot_df = plot_df.dropna(subset=["Plot Date"])
        if plot_df.empty:
            return None
        x_values = plot_df["Plot Date"]
        x_title = "Date"
    else:
        x_values = plot_df["Test"]
        x_title = "Test"

    customdata = []
    for _, row in plot_df.iterrows():
        plot_date = row["Plot Date"]
        if pd.notna(plot_date):
            plot_date_text = plot_date.strftime("%Y-%m-%d %H:%M")
        else:
            plot_date_text = "N/A"
        customdata.append([row["Test"], plot_date_text, row[std_col]])

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=plot_df[mean_col],
            mode="markers+lines",
            name=metric_name,
            error_y=dict(
                type="data",
                array=plot_df[std_col],
                visible=True
            ),
            customdata=customdata,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Date: %{customdata[1]}<br>"
                "Mean: %{y:.2f}<br>"
                "Std: %{customdata[2]:.2f}<extra></extra>"
            )
        )
    )

    fig.update_layout(
        title=f"{metric_name} across tests",
        xaxis_title=x_title,
        yaxis_title=metric_name,
        template="plotly_white",
        height=450
    )

    if not use_time_axis:
        fig.update_layout(
            xaxis=dict(
                type="category",
                categoryorder="array",
                categoryarray=plot_df["Test"].tolist()
            )
        )

    return fig