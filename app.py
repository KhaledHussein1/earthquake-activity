import dash
from dash import html, dcc, callback, Output, Input, State
from pymongo import MongoClient
import plotly.express as px
from datetime import datetime, timezone, timedelta
from fetch_data import check_and_fetch_data
import json
import csv
import io

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
    start_datetime = datetime.strptime(start_date.split('T')[0], '%Y-%m-%d')
    end_datetime = datetime.strptime(end_date.split('T')[0], '%Y-%m-%d')
    data = list(collection.find({
        'properties.time': {
            '$gte': start_datetime.timestamp() * 1000,
            '$lte': end_datetime.timestamp() * 1000
        }
    }))
    client.close()
    return data

def convert_timestamp(milliseconds):
    return datetime.fromtimestamp(milliseconds / 1000, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

def export_data_to_csv(start_date, end_date):
    # Ensure data is available in the database
    data = get_data(start_date, end_date)

    # Define the fields to export
    fields = [
        'id', 'time', 'mag', 'magType', 'place', 'longitude', 'latitude', 'depth',
        'type', 'status', 'sig', 'net', 'rms', 'url'
    ]

    # Create a buffer to hold CSV data
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for feature in data:
        writer.writerow({
            'id': feature.get('id'),
            'time': convert_timestamp(feature['properties'].get('time')),
            'mag': feature['properties'].get('mag'),
            'magType': feature['properties'].get('magType'),
            'place': feature['properties'].get('place'),
            'longitude': feature['geometry']['coordinates'][0],
            'latitude': feature['geometry']['coordinates'][1],
            'depth': feature['geometry']['coordinates'][2],
            'type': feature['properties'].get('type'),
            'status': feature['properties'].get('status'),
            'sig': feature['properties'].get('sig'),
            'net': feature['properties'].get('net'),
            'rms': feature['properties'].get('rms'),
            'url': feature['properties'].get('url'),
        })
    output.seek(0)  # Rewind the buffer
    return output.getvalue()

def generate_figure(data):
    lons = [d['geometry']['coordinates'][0] for d in data]
    lats = [d['geometry']['coordinates'][1] for d in data]
    mags = [d['properties']['mag'] if 'mag' in d['properties'] else 0 for d in data]
    
    # Handling None values in magnitudes
    sizes = [max(1, (mag if mag is not None else 0) * 2) for mag in mags]
    
    dates = [datetime.fromtimestamp(d['properties']['time'] / 1000).strftime('%Y-%m-%d')
             for d in data if 'time' in d['properties'] and isinstance(d['properties']['time'], (int, float))]
    date_range = f"{min(dates)} to {max(dates)}" if dates else "No date range available"

    # Use Plotly Express to create the figure
    fig = px.scatter_geo(
        lon=lons, 
        lat=lats, 
        size=sizes,  # Updated sizes list with None handling
        color=mags,  # Use magnitude as color
        color_continuous_scale=px.colors.sequential.Plasma,  # Color scale
        hover_name=["Magnitude: " + str(mag) for mag in mags],  # Hover text
        projection="natural earth"  # More realistic earth projection
    )

    fig.update_geos(
        visible=False,  # Hide the default basemap
    )

    fig.update_layout(
        title={
        'text': f"Global Earthquake Activity ({date_range})",
        'y': 0.97,  # Position of the title. Adjust the y-coordinate as needed
        'x': 0.5,  # Centers the title horizontally
        'xanchor': 'center',  # Anchor the title at its center
        'yanchor': 'top'  # Anchor the title from the top
    },
        autosize=True,
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

app.layout = html.Div(className='container', children=[
    html.H1("Seismic Activity Visualizer", className='app-title'),

    # Graph Container
    html.Div(className='graph-container', children=[
        dcc.Graph(id='earthquake-map', style={'height': '80vh', 'width': '80vw'})
    ]),
    # Controls Container
    html.Div(className='control-bar', children=[
        dcc.DatePickerRange(
            id='date-picker-range',
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now(),
            display_format='YYYY-MM-DD'
        ),
        html.Button('Export Data', id='export-button'),
        dcc.Download(id="download-data")
    ]),
    html.Div(className='info-container', children=[
     html.H2("About", className='info-title'),
     html.H4("This tool visualizes global earthquake activity by utilizing data from the United States Geological Survey (USGS) API to provide real-time and historical earthquake information. Users can select a specific date range to view detailed earthquake events on an interactive map, which displays the locations, magnitudes, and additional details of seismic activities around the world. The application also offers the capability to export earthquake data for the selected date range into a CSV file for further analysis or record-keeping.", className='note'),
     html.H2("Performance Recommendation for Users", className='info-title'),
     html.H4("For the best experience when interacting with the map, it is advisable to choose a date range of no longer than one week. This ensures that the map loads quickly and remains responsive. However, if you need to visualize or export data for extensive research or personal use, you can select much longer periods, even spanning several years. Please be aware that processing large amounts of data for export may take some time.", className='note'),
     html.H2("Exported Data Documentation", className='info-title'),
     html.H4([
    "You can export earthquake data in a formatted CSV file that includes columns such as 'id', 'time', 'mag', 'magType', 'place', 'longitude', 'latitude', 'depth', 'type', 'status', 'sig', 'net', 'rms', 'url'. For a detailed understanding of each of these columns, take a look at the ",
    html.A('USGS website', href='https://earthquake.usgs.gov/data/comcat/data-eventterms.php#mag')
], className='note')
    ])
])

@app.callback(
    Output('earthquake-map', 'figure'),
    [Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date')]
)
def update_map(start_date, end_date):
    data = get_data(start_date, end_date)
    return generate_figure(data)


@app.callback(
    Output('download-data', 'data'),
    Input('export-button', 'n_clicks'),
    State('date-picker-range', 'start_date'),
    State('date-picker-range', 'end_date'),
    prevent_initial_call=True
)
def export_button_click(n_clicks, start_date, end_date):
    if n_clicks is not None:
        csv_string = export_data_to_csv(start_date, end_date)
        return dcc.send_string(csv_string, "earthquake_data.csv")

if __name__ == '__main__':
    app.run_server(debug=True, dev_tools_ui=True)