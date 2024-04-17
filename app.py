import dash
from dash import html, dcc
from dash.dependencies import Input, Output
from pymongo import MongoClient
import plotly.express as px
import datetime
from fetch_data import check_and_fetch_data
import json

app = dash.Dash(__name__)

# Load configuration from a JSON file
with open('config.json') as config_file:
  config = json.load(config_file)

database_url = config['database_url']

def get_data(start_date, end_date):
    # Check and fetch data if not present
    check_and_fetch_data(start_date, end_date)  # Ensure data is up-to-date

    client = MongoClient(database_url)
    db = client.earthquake_db
    collection = db.earthquakes
    # Parse date strings and ensure no time component issues
    start_datetime = datetime.datetime.strptime(start_date.split('T')[0], '%Y-%m-%d')
    end_datetime = datetime.datetime.strptime(end_date.split('T')[0], '%Y-%m-%d')
    data = list(collection.find({
        'properties.time': {
            '$gte': start_datetime.timestamp() * 1000,
            '$lte': end_datetime.timestamp() * 1000
        }
    }))
    client.close()
    return data


def generate_figure(data):
    lons = [d['geometry']['coordinates'][0] for d in data]
    lats = [d['geometry']['coordinates'][1] for d in data]
    mags = [d['properties']['mag'] if 'mag' in d['properties'] else 0 for d in data]
    
    dates = [datetime.datetime.fromtimestamp(d['properties']['time'] / 1000).strftime('%Y-%m-%d')
             for d in data if 'time' in d['properties'] and isinstance(d['properties']['time'], (int, float))]
    date_range = f"{min(dates)} to {max(dates)}" if dates else "No date range available"

    # Use Plotly Express to create the figure
    fig = px.scatter_geo(
        lon=lons, 
        lat=lats, 
        size=[max(1, mag * 2) for mag in mags],  # Scale size by magnitude
        color=mags,  # Use magnitude as color
        color_continuous_scale=px.colors.sequential.Plasma,  # Color scale
        hover_name=["Magnitude: " + str(mag) for mag in mags],  # Hover text
        projection="natural earth"  # More realistic earth projection
    )

    fig.update_geos(
        visible=False,  # Hide the default basemap
        showcountries=True,  # Show country borders
        countrycolor="RebeccaPurple"  # Stylish color for country borders
    )

    fig.update_layout(
        title=f"Global Earthquake Activity ({date_range})",
        geo=dict(
            showland=True,  # Show land
            landcolor='rgb(54, 69, 79)',  # Land color
            showocean=True,  # Show ocean
            oceancolor="#007592",  # Ocean color
            showcountries=True,  # Show country borders
            countrycolor='rgb(249, 246, 238)'  # Country border color
        )
    )
    return fig

app.layout = html.Div([
    dcc.DatePickerRange(
        id='date-picker-range',
        start_date=datetime.datetime(2024, 4, 1),
        end_date=datetime.datetime(2024, 4, 2),
        display_format='YYYY-MM-DD'
    ),
    dcc.Graph(id='earthquake-map', style={'height': '100vh', 'width': '100%'})
])

@app.callback(
    Output('earthquake-map', 'figure'),
    [Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date')]
)
def update_map(start_date, end_date):
    data = get_data(start_date, end_date)
    return generate_figure(data)

if __name__ == '__main__':
    app.run_server(debug=True, dev_tools_ui=True)