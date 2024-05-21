import dash
from dash import html, dcc, Output, Input, State
from pymongo import MongoClient
import plotly.express as px
from datetime import datetime, timezone, timedelta
import pandas as pd
from fetch_data import check_and_fetch_data
import csv, io, json
from dash.exceptions import PreventUpdate


app = dash.Dash(__name__)
app.title = 'Earthquake Watch'

config_file_path = 'config.json'

# Load the configuration from JSON file
with open(config_file_path, 'r') as file:
    config = json.load(file)

# Directly assign variables
database_url = config['database_url']

# Creating a MongoDB connection pool
client = MongoClient(database_url)
db = client.earthquake_db
collection = db.earthquakes

def get_data(selected_date):
    # Check and fetch data if not present
    check_and_fetch_data(selected_date, selected_date)  

    # Parse date string and create a full day range
    selected_datetime = datetime.strptime(selected_date, '%Y-%m-%d')
    start_datetime = datetime(selected_datetime.year, selected_datetime.month, selected_datetime.day, 0, 0, 0)
    end_datetime = datetime(selected_datetime.year, selected_datetime.month, selected_datetime.day, 23, 59, 59)

    # Define projection to include only necessary fields
    projection = {
        '_id': 0,  # Exclude MongoDB's default '_id' field if not needed
        'id': 1,
        'properties.time': 1,
        'properties.mag': 1,
        'properties.magType': 1,
        'properties.place': 1,
        'properties.type': 1,
        'properties.status': 1,
        'properties.sig': 1,
        'properties.net': 1,
        'properties.rms': 1,
        'properties.url': 1,
        'geometry.coordinates': 1
    }

    data = list(collection.find({
        'properties.time': {
            '$gte': start_datetime.timestamp() * 1000,
            '$lte': end_datetime.timestamp() * 1000
        }
    }, projection=projection))
    return data

def convert_timestamp(milliseconds):
    return datetime.fromtimestamp(milliseconds / 1000, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

def export_data_to_csv(data):
    data = get_data(data)

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


def generate_figure(data, include_size=True, scaling='none'):
    # Convert data lists to a DataFrame
    df = pd.DataFrame({
        'lon': [d['geometry']['coordinates'][0] for d in data],
        'lat': [d['geometry']['coordinates'][1] for d in data],
        'magnitude': [d['properties']['mag'] if 'mag' in d['properties'] else 0 for d in data],
        'time': [datetime.fromtimestamp(d['properties']['time'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                 for d in data if 'time' in d['properties'] and isinstance(d['properties']['time'], (int, float))],
        'place':  [d['properties']['place'] for d in data],
    })

    # Apply different scaling based on the scaling parameter
    if scaling == 'linear':
        df['size'] = df['magnitude'].apply(lambda mag: max(1, mag * 2))
    elif scaling == 'logarithmic':
        df['size'] = df['magnitude'].apply(lambda mag: max(1, 10 ** (0.5 * mag)))
    elif scaling == 'none':
        df['size'] = 1  # Or simply don't apply size at all in the visualization

    date_range = f"{min(df['time'])} to {max(df['time'])}" if not df['time'].empty else "No date range available"

    if include_size:
        size = 'size'  # Use size from DataFrame
    else:
        size = None 
    # Use Plotly Express to create the figure using DataFrame
    fig = px.scatter_geo(
        df,
        lon='lon',
        lat='lat',
        size=size,  # Use size from DataFrame
        color='magnitude',  # Use magnitude as color
        color_continuous_scale=px.colors.sequential.Viridis,  # Inferno, Magma, Plasma, Viridis, Cividis, Jet, Greys
        hover_name=df['place'],  # Use place as hover name
        hover_data={
            'magnitude': True,  # Show magnitude in hover
            'time': True,  # Show time in hover
            'size': False  # Optionally control if size is shown based on button toggle
        },  
        projection="natural earth",  # More realistic earth projection
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

    # Controls Container
    html.Div(className='control-bar', children=[
        dcc.DatePickerSingle(
            id='date-picker-single',
            date=datetime.now().date(),
            display_format='YYYY-MM-DD'
        ),
        html.Button('Export Data', id='export-button'),
        dcc.Download(id="download-data"),
        dcc.Dropdown(
    id='scaling-dropdown',
    options=[
        {'label': 'Minimal', 'value': 'none'},
        {'label': 'Linear Scaling', 'value': 'linear'},
        {'label': 'Logarithmic Scaling', 'value': 'logarithmic'}
    ],
    value='none',  # Set default to no scaling
    clearable=False,
    searchable=False,
        ),
    ]),

    # Graph Container
    html.Div(className='graph-container', children=[
        dcc.Graph(id='earthquake-map', style={'height': '80vh', 'width': '80vw'})
    ]),
    
    html.Div(className='info-container', children=[
     html.H2("About", className='info-title'),
     html.H4("This tool visualizes global earthquake activity by utilizing data from the United States Geological Survey (USGS) API to provide real-time and historical earthquake information. Users can select a specific date range to view detailed earthquake events on an interactive map, which displays the locations, magnitudes, and additional details of seismic activities around the world. Users can tailor the visualization experience by adjusting the scaling of earthquake magnitudes. The application also offers the capability to export earthquake data for the selected date range into a CSV file for further analysis or record-keeping.", className='note'),
     html.H2("Performance Recommendation for Users", className='info-title'),
     html.H4("For the best experience when interacting with the map, it is advisable to choose a date range of no longer than one week. This ensures that the map loads quickly and remains responsive. However, if you need to visualize or export data for extensive research or personal use, you can select much longer periods, even spanning several years. Please be aware that processing large amounts of data for export may take some time. Additionally, using the 'Minimal' scaling option is recommended for rendering more data at once, as it provides a streamlined visualization that prioritizes performance over detailed visual effects.", className='note'),
     html.H2("Exported Data Documentation", className='info-title'),
     html.H4([
    "You can export earthquake data in a formatted CSV file that includes columns such as 'id', 'time', 'mag', 'magType', 'place', 'longitude', 'latitude', 'depth', 'type', 'status', 'sig', 'net', 'rms', 'url'. For a detailed understanding of each of these columns, take a look at the ",
    html.A('USGS website', href='https://earthquake.usgs.gov/data/comcat/data-eventterms.php#mag')
], className='note')
    ])
])

@app.callback(
    Output('earthquake-map', 'figure'),
    [Input('date-picker-single', 'date'),
     Input('scaling-dropdown', 'value')],  # Change this from minimize-visuals-button to scaling-dropdown
)
def update_map(selected_date, scaling):
    if not selected_date:
        raise PreventUpdate
    data = get_data(selected_date)
    # Adjust scaling based on dropdown selection
    if scaling == 'linear':
        return generate_figure(data, include_size=True, scaling='linear')
    elif scaling == 'logarithmic':
        return generate_figure(data, include_size=True, scaling='logarithmic')
    else:
        return generate_figure(data, include_size=False)  # Minimal visual means no size scaling




@app.callback(
    Output('download-data', 'data'),
    Input('export-button', 'n_clicks'),
    State('date-picker-single', 'date'),
    prevent_initial_call=True
)
def export_button_click(n_clicks, selected_date):
    if n_clicks is not None:
        csv_string = export_data_to_csv(selected_date)
        return dcc.send_string(csv_string, "earthquake_data.csv")

if __name__ == '__main__':
    app.run_server( port=8050, debug=True, dev_tools_ui=True)
