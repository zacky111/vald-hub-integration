import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.data_prep_funcs import parse_forcedeck_raw_data


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


import pandas as pd
import plotly.graph_objects as go


def create_mean_std_chart(summary_df, metric, use_time_axis=False):
    """
    Creates mean/std chart across tests.

    Dla zwykłych metryk:
    - linia + punkty + std

    Dla asymetrii:
    - zielone tło dla zakresu -10 do 10
    - czerwone tło poza tym zakresem
    - pozioma linia odniesienia y=0
    """

    mean_col = f"{metric} Mean"
    std_col = f"{metric} Std"

    if summary_df is None or summary_df.empty:
        return None

    if mean_col not in summary_df.columns:
        return None

    df = summary_df.copy()

    df[mean_col] = pd.to_numeric(df[mean_col], errors="coerce")
    if std_col in df.columns:
        df[std_col] = pd.to_numeric(df[std_col], errors="coerce")
    else:
        df[std_col] = None

    df = df.dropna(subset=[mean_col])
    if df.empty:
        return None

    # Oś X
    if use_time_axis and "Plot Date" in df.columns:
        x = pd.to_datetime(df["Plot Date"], errors="coerce")
        x_title = "Date"
    else:
        x = df["Test"]
        x_title = "Test"

    y = df[mean_col]
    error_y = df[std_col] if std_col in df.columns else None

    metric_lower = str(metric).lower()
    is_asymmetry_metric = (
        "asym" in metric_lower
        or "asymmetry" in metric_lower
    )

    fig = go.Figure()

    # Główna seria: linia + punkty + error bars
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            name=metric,
            error_y=dict(
                type="data",
                array=error_y,
                visible=True
            ) if error_y is not None else None,
            hovertemplate=(
                f"<b>{metric}</b><br>"
                + f"{x_title}: %{{x}}<br>"
                + "Mean: %{y:.2f}<br>"
                + (f"Std: %{{error_y.array:.2f}}<br>" if error_y is not None else "")
                + "<extra></extra>"
            ),
        )
    )

    # Specjalne tło dla asymetrii
    if is_asymmetry_metric:
        fig.add_hrect(
            y0=-10,
            y1=10,
            fillcolor="green",
            opacity=0.12,
            line_width=0,
            layer="below"
        )

        fig.add_hrect(
            y0=10,
            y1=max(10, float(y.max()) + max(2, abs(float(y.max())) * 0.1)),
            fillcolor="red",
            opacity=0.10,
            line_width=0,
            layer="below"
        )

        fig.add_hrect(
            y0=min(-10, float(y.min()) - max(2, abs(float(y.min())) * 0.1)),
            y1=-10,
            fillcolor="red",
            opacity=0.10,
            line_width=0,
            layer="below"
        )

        fig.add_hline(
            y=0,
            line_width=2,
            line_dash="dash",
            line_color="black"
        )

    fig.update_layout(
        title=f"{metric} across tests",
        xaxis_title=x_title,
        yaxis_title=metric,
        hovermode="x unified",
        template="plotly_white",
        height=500,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="black"),
        title_font=dict(color="black"),
        legend=dict(font=dict(color="black"))
    )

    fig.update_xaxes(
        title_font=dict(color="black"),
        tickfont=dict(color="black")
    )

    fig.update_yaxes(
        title_font=dict(color="black"),
        tickfont=dict(color="black")
    )

    return fig


def create_left_right_chart(summary_df, base_metric, metric_map, use_time_axis=False):
    """
    Rysuje Left + Right na jednym wykresie
    """

    fig = go.Figure()

    if use_time_axis and "Plot Date" in summary_df.columns:
        x = pd.to_datetime(summary_df["Plot Date"], errors="coerce")
        x_title = "Date"
    else:
        x = summary_df["Test"]
        x_title = "Test"

    for limb, color in [("Left", "blue"), ("Right", "red")]:
        if limb not in metric_map:
            continue

        metric = metric_map[limb]

        mean_col = f"{metric} Mean"
        std_col = f"{metric} Std"

        if mean_col not in summary_df.columns:
            continue

        y = pd.to_numeric(summary_df[mean_col], errors="coerce")
        error = pd.to_numeric(summary_df[std_col], errors="coerce") if std_col in summary_df else None

        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines+markers",
                name=f"{base_metric} - {limb}",
                line=dict(color=color),
                error_y=dict(type="data", array=error, visible=True) if error is not None else None,
            )
        )

    fig.update_layout(
        title=f"{base_metric} (Left vs Right)",
        xaxis_title=x_title,
        yaxis_title=base_metric,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="black"),
        template="plotly_white",
        title_font=dict(color="black"),
        legend=dict(font=dict(color="black"))
        )

    fig.update_xaxes(
        title_font=dict(color="black"),
        tickfont=dict(color="black")
    )

    fig.update_yaxes(
        title_font=dict(color="black"),
        tickfont=dict(color="black")
    )

    return fig





def create_raw_force_plot(
    raw_data: dict,
    title: str = "Raw Force Data",
    max_points: int | None = 10000
):
    """
    Tworzy wykres raw data dla lewej nogi, prawej nogi oraz sumy.

    Parametry:
    - raw_data: payload z API
    - title: tytuł wykresu
    - max_points: opcjonalne ograniczenie liczby punktów dla wydajności
                  (np. przy 127k próbkach). Jeśli None, rysuje wszystko.

    Zwraca:
    - df_plot: DataFrame użyty do wykresu
    - fig: obiekt Plotly Figure
    """
    df = parse_forcedeck_raw_data(raw_data)

    df_plot = df.copy()

    # Downsampling dla wydajności wykresu
    if max_points is not None and len(df_plot) > max_points:
        step = max(1, len(df_plot) // max_points)
        df_plot = df_plot.iloc[::step].reset_index(drop=True)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_plot["time"],
        y=df_plot["left"],
        mode="lines",
        name="Left"
    ))

    fig.add_trace(go.Scatter(
        x=df_plot["time"],
        y=df_plot["right"],
        mode="lines",
        name="Right"
    ))

    fig.add_trace(go.Scatter(
        x=df_plot["time"],
        y=df_plot["total"],
        mode="lines",
        name="Total"
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Time [s]",
        yaxis_title="Force [N]",
        hovermode="x unified",
        template="plotly_white",
        height=600,
        title_font=dict(color="black"),
        legend=dict(font=dict(color="black")),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="black"),
    )

    fig.update_xaxes(
        title_font=dict(color="black"),
        tickfont=dict(color="black")
    )

    fig.update_yaxes(
        title_font=dict(color="black"),
        tickfont=dict(color="black")
    )

    return df_plot, fig

def create_overlay_trials_chart(overlays: list):
    fig = go.Figure()
    dash_styles = ["solid", "dash", "dot", "dashdot"]

    for overlay_idx, overlay in enumerate(overlays):
        label = overlay["label"]
        df = overlay["df"]
        plot_cols = overlay["plot_cols"]

        dash_style = dash_styles[overlay_idx % len(dash_styles)]

        for col in plot_cols:
            fig.add_trace(go.Scatter(
                x=df["time_rel"],
                y=df[col],
                mode="lines",
                name=f"{label} - {col.capitalize()}",
                line=dict(
                    dash=dash_style,
                    width=2
                )
            ))

    fig.add_vline(x=0, line_width=2, line_dash="dash")

    fig.update_layout(
        title="Overlay of Trials Aligned to Movement Onset",
        xaxis_title="Time relative to movement onset [s]",
        yaxis_title="Force [N]",
        hovermode="x unified",
        template="plotly_white",
        height=650
    )

    return fig