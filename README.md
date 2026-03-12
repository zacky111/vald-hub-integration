# Vald Hub Integration Dashboard

A Streamlit-based performance monitoring dashboard for Vald Hub athlete data. This app fetches real-time data from the Vald Hub API and displays interactive visualizations of force, power, and velocity metrics.

## Features

- 📊 **Real-time Dashboards** - Multiple viewing modes (Overview, Athlete Analysis, Trends)
- 📈 **Interactive Visualizations** - Force production, power vs velocity, normalized metrics
- ⚡ **Cross-Platform** - Works seamlessly on macOS and Windows
- 🔄 **Auto-Refresh** - Data updates each time the app loads
- 📋 **Athlete Management** - View and filter athlete performance data
- 🎨 **Dark Theme** - Professional, eye-friendly interface

## Quick Start

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. **Clone or navigate to the project**
```bash
cd c:\projects\vald-hub-integration
```

2. **Create a virtual environment** (recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure API credentials**
```bash
# Copy the example env file
cp .env.example .env

# Edit .env with your Vald Hub credentials
# VALD_HUB_API_KEY=your_api_key_here
# VALD_HUB_BASE_URL=https://api.vald-hub.com
```

### Running the App

```bash
streamlit run app.py
```

The app will open in your default browser at `http://localhost:8501`

## Project Structure

```
vald-hub-integration/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── .env.example          # Example environment variables
├── .gitignore           # Git ignore file
└── src/
    ├── vald_client.py    # Vald Hub API client
    └── visualizations.py # Chart and visualization utilities
```

## Configuration

### Environment Variables

Edit the `.env` file with your Vald Hub credentials:

```env
VALD_HUB_API_KEY=your_api_key_here
VALD_HUB_BASE_URL=https://api.vald-hub.com
```

### Streamlit Configuration

You can customize Streamlit settings by creating `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#0084FF"
backgroundColor = "#111111"
secondaryBackgroundColor = "#262730"
textColor = "#FAFAFA"
font = "sans serif"

[client]
showErrorDetails = true
```

## Usage Guide

### Overview Mode
- See key metrics (athletes count, average force, power, velocity)
- View force production trends over time
- Analyze power vs velocity relationships
- Review complete athlete roster

### Athlete Analysis Mode
- Select individual athletes from dropdown
- Compare specific athlete performance
- View personalized force and power metrics

### Trends Mode
- Track performance trends across all athletes
- View statistical ranges and variations
- Compare normalized metrics side-by-side

## Data Features

The app displays:
- **Force (N)** - Measured in Newtons, maximum force produced
- **Power (W)** - Measured in Watts, rate of force production
- **Velocity (m/s)** - Measured in meters per second, movement speed

## API Integration

The app connects to Vald Hub API with the following methods:

- `get_athletes()` - Fetch list of all athletes
- `get_athlete_data(athlete_id)` - Get specific athlete profile
- `get_assessments()` - Fetch performance assessments
- `get_metrics(athlete_id)` - Get performance metrics

If the API is unavailable, the app automatically falls back to sample data for development.

## Troubleshooting

### API Connection Issues
- Verify your API key in `.env` file
- Check your internet connection
- Ensure Vald Hub API is accessible from your network

### App Won't Start
```bash
# Clear Streamlit cache
streamlit cache clear

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Cross-Platform Issues
- **Windows**: Use `python` instead of `python3`
- **macOS**: Use `python3` explicitly
- Both platforms: Use virtual environments for consistency

## Development

To extend the app:

1. **Add new API endpoints** in `src/vald_client.py`
2. **Create new visualizations** in `src/visualizations.py`
3. **Add new dashboard views** in `app.py`

Example adding a new metric:
```python
def get_new_metric(self, athlete_id: str):
    return self._make_request(f'/athletes/{athlete_id}/new-metric')
```

## Performance Notes

- Data refreshes completely on each app load (by design)
- Use Streamlit's caching decorators for optimized queries:
```python
@st.cache_data(ttl=300)  # Cache for 5 minutes
def expensive_operation():
    ...
```

## License

[Specify your license here]

## Support

For issues with Vald Hub API, visit: https://docs.vald-hub.com
