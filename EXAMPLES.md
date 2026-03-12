# Vald Hub Integration Examples & Extensions

This file contains examples of how to extend the dashboard with custom metrics and visualizations.

## Adding Custom Metrics

### Example 1: Add a new API endpoint

In `src/vald_client.py`, add a new method:

```python
def get_injury_risk(self, athlete_id: str) -> Optional[Dict]:
    """Fetch injury risk assessment for an athlete"""
    return self._make_request(f'/athletes/{athlete_id}/injury-risk')

def get_weekly_summary(self, athlete_id: str) -> Optional[Dict]:
    """Fetch weekly performance summary"""
    return self._make_request(f'/athletes/{athlete_id}/weekly-summary')
```

### Example 2: Create a custom visualization

In `src/visualizations.py`, add:

```python
def create_injury_risk_gauge(risk_score: float) -> go.Figure:
    """Create a gauge chart for injury risk"""
    fig = go.Figure(data=[go.Indicator(
        mode="gauge+number+delta",
        value=risk_score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Injury Risk"},
        delta={'reference': 50},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 33], 'color': "lightgreen"},
                {'range': [33, 67], 'color': "lightyellow"},
                {'range': [67, 100], 'color': "lightcoral"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 85
            }
        }
    )])
    return fig
```

### Example 3: Add a new dashboard view

In `app.py`, add to main():

```python
elif display_mode == "Injury Prevention":
    show_injury_prevention(data)
```

Then add the function:

```python
def show_injury_prevention(data):
    """Display injury prevention metrics"""
    st.header("Injury Prevention")
    
    client = ValdHubClient()
    athlete = st.selectbox("Select Athlete", [a['name'] for a in data['athletes']])
    
    risk_data = client.get_injury_risk(athlete['id'])
    
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(create_injury_risk_gauge(risk_data['score']))
    with col2:
        st.info(f"Risk Level: {risk_data['level']}")
        st.write(f"Recommendations: {risk_data['recommendations']}")
```

## Caching for Performance

Use Streamlit's caching decorators to avoid repeated API calls:

```python
import streamlit as st
from src.vald_client import ValdHubClient

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_athletes_cached():
    client = ValdHubClient()
    return client.get_athletes()

@st.cache_resource
def get_client():
    return ValdHubClient()
```

## Working with Time Series Data

Example of filtering data by date range:

```python
import pandas as pd
from datetime import datetime, timedelta

def filter_metrics_by_date(data: List[Dict], days: int = 30) -> pd.DataFrame:
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    cutoff = datetime.now() - timedelta(days=days)
    return df[df['date'] > cutoff]
```

## Export Data

Add this function to export filtered data:

```python
def export_to_csv(df: pd.DataFrame, filename: str = "athletes_data.csv"):
    csv = df.to_csv(index=False)
    st.download_button(
        label="Download as CSV",
        data=csv,
        file_name=filename,
        mime="text/csv"
    )
```

Use in app:

```python
csv_data = create_athlete_summary(data['athletes'])
export_to_csv(csv_data)
```

## Real-time Updates

For real-time updates, use Streamlit's `st.rerun()`:

```python
import time

if st.checkbox("Enable Auto-Refresh"):
    refresh_interval = st.slider("Refresh every (seconds):", 10, 300, 60)
    time.sleep(refresh_interval)
    st.rerun()
```

## Database Integration

Example with SQLite for caching:

```python
import sqlite3
from datetime import datetime

def save_metrics_to_db(athlete_id: str, metrics: Dict):
    conn = sqlite3.connect('vald_metrics.db')
    c = conn.cursor()
    c.execute('''INSERT INTO metrics 
                 (athlete_id, force, power, velocity, timestamp)
                 VALUES (?, ?, ?, ?, ?)''',
              (athlete_id, metrics['force'], metrics['power'], 
               metrics['velocity'], datetime.now()))
    conn.commit()
    conn.close()
```

## Multi-page Dashboard

Create additional files in pages/:

```
app.py (main entry point)
pages/
  ├── 01_📊_overview.py
  ├── 02_👤_athletes.py
  ├── 03_📈_trends.py
  └── 04_⚙️_settings.py
```

In each file, use the same structure as app.py without the multi-page selection logic.

## Deployment

### Deploy on Streamlit Cloud

1. Push your code to GitHub
2. Go to https://share.streamlit.io
3. Connect your GitHub account
4. Deploy the repository
5. Configure secrets in the app dashboard

### Deploy on Heroku

Create `Procfile`:
```
web: streamlit run --server.port=$PORT app.py
```

Push to Heroku:
```bash
git push heroku main
```

## Testing

Add automated tests in `tests/` directory:

```python
# tests/test_vald_client.py
import pytest
from src.vald_client import ValdHubClient

def test_connection():
    client = ValdHubClient()
    assert client.api_key is not None
    
def test_get_athletes():
    client = ValdHubClient()
    athletes = client.get_athletes()
    assert isinstance(athletes, list)
```

Run tests:
```bash
pip install pytest
pytest tests/
```
