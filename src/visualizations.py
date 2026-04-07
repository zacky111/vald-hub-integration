import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.data_prep_funcs import parse_forcedeck_raw_data


def _add_linear_trendline(fig, x_values, y_values, name="Trendline", color="black", dash="dot"):
    """
    Adds a simple linear trendline based on numeric x positions.
    Works for both categorical and datetime x axes by fitting on index positions.
    """
    y_numeric = pd.to_numeric(pd.Series(y_values), errors="coerce")
    valid_mask = y_numeric.notna()

    if valid_mask.sum() < 2:
        return fig

    x_plot = list(pd.Series(x_values)[valid_mask].values)
    y_plot = y_numeric[valid_mask].values
    x_idx = np.arange(len(y_plot))

    if len(x_idx) < 2:
        return fig

    slope, intercept = np.polyfit(x_idx, y_plot, 1)
    trend_y = slope * x_idx + intercept

    fig.add_trace(
        go.Scatter(
            x=x_plot,
            y=trend_y,
            mode="lines",
            name=name,
            line=dict(color=color, dash=dash, width=2),
            hovertemplate="<b>Trendline</b><br>Value: %{y:.2f}<extra></extra>"
        )
    )

    return fig


def create_metrics_comparison_chart(comp_df, metric, show_trendline=False):
    """
    Create a scatter plot with lines for a specific metric across trials, including average line.
    """
    if metric not in comp_df.columns:
        return None

    trials_df = comp_df.loc[comp_df.index.to_series().str.startswith('Trial')]
    metric_data = pd.to_numeric(trials_df[metric], errors="coerce").dropna()

    if len(metric_data) > 1:
        fig = px.scatter(
            x=metric_data.index,
            y=metric_data.values,
            title=f'{metric} Across Trials',
            labels={'x': 'Trial', 'y': 'Value'}
        )
        fig.update_traces(mode='lines+markers', name=metric)

        avg_value = metric_data.mean()
        fig.add_hline(
            y=avg_value,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Average: {avg_value:.2f}"
        )

        if show_trendline:
            fig = _add_linear_trendline(
                fig,
                x_values=metric_data.index.tolist(),
                y_values=metric_data.values,
                name="Trendline"
            )

        fig.update_layout(
            template="plotly_white",
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(color="black"),
            title_font=dict(color="black"),
            legend=dict(font=dict(color="black"))
        )

        return fig

    return None


def create_limb_asymmetry_chart(asym_df, metric):
    """
    Create a chart for limb data:
    - Left / Right shown as bars on primary Y axis
    - Asym shown as horizontal bar from 0 to value on secondary Y axis (%)
    - Asym value is displayed directly as text on the chart
    """
    metric_data = asym_df[asym_df['Metric Name'] == metric].copy()

    if metric_data.empty:
        return None

    metric_data['Value'] = pd.to_numeric(metric_data['Value'], errors='coerce')
    metric_data = metric_data.dropna(subset=['Value'])

    if metric_data.empty:
        return None

    left_right = metric_data[metric_data['Limb'].isin(['Left', 'Right'])].copy()
    asym_only = metric_data[metric_data['Limb'] == 'Asym'].copy()

    if left_right.empty and asym_only.empty:
        return None

    fig = go.Figure()

    if not left_right.empty:
        fig.add_trace(
            go.Bar(
                x=left_right['Limb'],
                y=left_right['Value'],
                name='Left / Right',
                yaxis='y',
                hovertemplate="<b>%{x}</b><br>Value: %{y:.2f}<extra></extra>"
            )
        )

    if not asym_only.empty:
        asym_value = float(asym_only['Value'].iloc[0])
        asym_x = ["Asymmetry"]

        fig.add_trace(
            go.Bar(
                x=asym_x,
                y=[asym_value],
                name='Asymmetry (%)',
                yaxis='y2',
                text=[f"{asym_value:.2f}%"],
                textposition='outside',
                hovertemplate="<b>Asymmetry</b><br>Value: %{y:.2f}%<extra></extra>"
            )
        )

        fig.add_hline(
            y=0,
            line_dash="dash",
            line_color="black",
            opacity=0.8,
            yref="y2"
        )

        asym_abs_max = max(abs(asym_value), 10)
        asym_margin = max(2, asym_abs_max * 0.25)
        asym_range = [-asym_abs_max - asym_margin, asym_abs_max + asym_margin]
    else:
        asym_range = None

    fig.update_layout(
        title=f'{metric} by Limb',
        template='plotly_white',
        height=550,
        barmode='group',
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(color='black'),
        title_font=dict(color='black'),
        legend=dict(font=dict(color='black')),
        xaxis=dict(
            title='',
            title_font=dict(color='black'),
            tickfont=dict(color='black')
        ),
        yaxis=dict(
            title='Value',
            title_font=dict(color='black'),
            tickfont=dict(color='black')
        ),
        yaxis2=dict(
            title='Asymmetry (%)',
            title_font=dict(color='black'),
            tickfont=dict(color='black'),
            overlaying='y',
            side='right',
            showgrid=False,
            range=asym_range,
            zeroline=True,
            zerolinewidth=2,
            zerolinecolor='black'
        )
    )

    return fig


def create_limb_asymmetry_charts(asym_df, metric):
    """
    Returns two separate charts:
    1. Left / Right absolute values
    2. Asymmetry (%) shown separately around zero
    """
    metric_data = asym_df[asym_df['Metric Name'] == metric].copy()

    if metric_data.empty:
        return None, None

    metric_data['Value'] = pd.to_numeric(metric_data['Value'], errors='coerce')
    metric_data = metric_data.dropna(subset=['Value'])

    if metric_data.empty:
        return None, None

    left_right = metric_data[metric_data['Limb'].isin(['Left', 'Right'])].copy()
    asym_only = metric_data[metric_data['Limb'] == 'Asym'].copy()

    fig_lr = None
    fig_asym = None

    if not left_right.empty:
        fig_lr = go.Figure()

        fig_lr.add_trace(
            go.Bar(
                x=left_right['Limb'],
                y=left_right['Value'],
                name='Left / Right',
                text=[f"{v:.2f}" for v in left_right['Value']],
                textposition='outside',
                hovertemplate="<b>%{x}</b><br>Value: %{y:.2f}<extra></extra>"
            )
        )

        fig_lr.update_layout(
            title=f"{metric} - Left vs Right",
            template="plotly_white",
            height=500,
            showlegend=False,
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(color="black"),
            title_font=dict(color="black"),
            xaxis=dict(
                title="",
                title_font=dict(color="black"),
                tickfont=dict(color="black")
            ),
            yaxis=dict(
                title="Value",
                title_font=dict(color="black"),
                tickfont=dict(color="black")
            )
        )

    if not asym_only.empty:
        asym_value = float(asym_only['Value'].iloc[0])

        asym_abs_max = max(abs(asym_value), 10)
        asym_margin = max(2, asym_abs_max * 0.25)
        y_range = [-asym_abs_max - asym_margin, asym_abs_max + asym_margin]

        fig_asym = go.Figure()

        fig_asym.add_trace(
            go.Bar(
                x=["Asymmetry"],
                y=[asym_value],
                text=[f"{asym_value:.2f}%"],
                marker_color="red" if asym_value > 0 else "darkblue",
                textposition='outside',
                hovertemplate="<b>Asymmetry</b><br>Value: %{y:.2f}%<extra></extra>"
            )
        )

        fig_asym.add_hline(
            y=0,
            line_width=2,
            line_dash="dash",
            line_color="black"
        )

        fig_asym.update_layout(
            title=f"{metric} - Asymmetry",
            template="plotly_white",
            height=500,
            showlegend=False,
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(color="black"),
            title_font=dict(color="black"),
            xaxis=dict(
                title="",
                title_font=dict(color="black"),
                tickfont=dict(color="black")
            ),
            yaxis=dict(
                title="Asymmetry (%)",
                title_font=dict(color="black"),
                tickfont=dict(color="black"),
                range=y_range,
                zeroline=True,
                zerolinewidth=2,
                zerolinecolor="black"
            )
        )

    return fig_lr, fig_asym


def create_mean_std_chart(summary_df, metric, use_time_axis=False, show_trendline=False):
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

    if "Display Label" not in df.columns:
        if "Plot Date" in df.columns:
            tmp_dates = pd.to_datetime(df["Plot Date"], errors="coerce")
            df["Display Label"] = tmp_dates.apply(
                lambda d: d.strftime("%a %d-%m-%Y") if pd.notnull(d) else "Unknown date"
            )
        else:
            df["Display Label"] = df["Test"].astype(str)

    if use_time_axis and "Plot Date" in df.columns:
        x_dt = pd.to_datetime(df["Plot Date"], errors="coerce")
        x = np.array(x_dt.dt.to_pydatetime())
        x_title = "Date"
        hover_x = df["Display Label"].tolist()
    else:
        x = df["Display Label"].tolist()
        x_title = "Session"
        hover_x = df["Display Label"].tolist()

    y = df[mean_col]
    error_y = df[std_col] if std_col in df.columns else None

    metric_lower = str(metric).lower()
    is_asymmetry_metric = (
        "asym" in metric_lower
        or "asymmetry" in metric_lower
    )

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            name=metric,
            customdata=hover_x,
            error_y=dict(
                type="data",
                array=error_y,
                visible=True
            ) if error_y is not None else None,
            hovertemplate=(
                f"<b>{metric}</b><br>"
                + "Session: %{customdata}<br>"
                + "Mean: %{y:.2f}<br>"
                + (f"Std: %{{error_y.array:.2f}}<br>" if error_y is not None else "")
                + "<extra></extra>"
            ),
        )
    )

    if show_trendline:
        fig = _add_linear_trendline(
            fig,
            x_values=x,
            y_values=y,
            name="Trendline"
        )

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

    if use_time_axis and "Plot Date" in df.columns:
        tick_vals = np.array(pd.to_datetime(df["Plot Date"], errors="coerce").dt.to_pydatetime())
        tick_text = df["Display Label"].tolist()

        fig.update_xaxes(
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_text,
            title_font=dict(color="black"),
            tickfont=dict(color="black")
        )
    else:
        fig.update_xaxes(
            title_font=dict(color="black"),
            tickfont=dict(color="black")
        )

    fig.update_yaxes(
        title_font=dict(color="black"),
        tickfont=dict(color="black")
    )

    return fig


def create_left_right_chart(summary_df, base_metric, metric_map, use_time_axis=False, show_trendline=False):
    """
    Rysuje Left + Right na jednym wykresie
    """

    fig = go.Figure()
    df = summary_df.copy()

    if "Display Label" not in df.columns:
        if "Plot Date" in df.columns:
            tmp_dates = pd.to_datetime(df["Plot Date"], errors="coerce")
            df["Display Label"] = tmp_dates.apply(
                lambda d: d.strftime("%a %d-%m-%Y") if pd.notnull(d) else "Unknown date"
            )
        else:
            df["Display Label"] = df["Test"].astype(str)

    if use_time_axis and "Plot Date" in df.columns:
        x_dt = pd.to_datetime(df["Plot Date"], errors="coerce")
        x = np.array(x_dt.dt.to_pydatetime())
        x_title = "Date"
        hover_x = df["Display Label"].tolist()
    else:
        x = df["Display Label"].tolist()
        x_title = "Session"
        hover_x = df["Display Label"].tolist()

    for limb, color in [("Left", "blue"), ("Right", "red")]:
        if limb not in metric_map:
            continue

        metric = metric_map[limb]

        mean_col = f"{metric} Mean"
        std_col = f"{metric} Std"

        if mean_col not in df.columns:
            continue

        y = pd.to_numeric(df[mean_col], errors="coerce")
        error = pd.to_numeric(df[std_col], errors="coerce") if std_col in df else None

        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines+markers",
                name=f"{base_metric} - {limb}",
                line=dict(color=color),
                customdata=hover_x,
                error_y=dict(type="data", array=error, visible=True) if error is not None else None,
                hovertemplate=(
                    f"<b>{base_metric} - {limb}</b><br>"
                    + "Session: %{customdata}<br>"
                    + "Mean: %{y:.2f}<br>"
                    + (f"Std: %{{error_y.array:.2f}}<br>" if error is not None else "")
                    + "<extra></extra>"
                ),
            )
        )

        if show_trendline:
            fig = _add_linear_trendline(
                fig,
                x_values=x,
                y_values=y,
                name=f"{base_metric} - {limb} Trendline",
                color=color,
                dash="dot"
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

    if use_time_axis and "Plot Date" in df.columns:
        tick_vals = np.array(pd.to_datetime(df["Plot Date"], errors="coerce").dt.to_pydatetime())
        tick_text = df["Display Label"].tolist()

        fig.update_xaxes(
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_text,
            title_font=dict(color="black"),
            tickfont=dict(color="black")
        )
    else:
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
    """
    df = parse_forcedeck_raw_data(raw_data)

    df_plot = df.copy()

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