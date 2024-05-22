import dash
from dash import html, dcc, Output, Input, State
from pymongo import MongoClient
import plotly.express as px
from datetime import datetime, timezone
import pandas as pd
from fetch_data import check_and_fetch_data
import csv, io, json
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from dash.dash_table import DataTable

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.SPACELAB])
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

controls = dbc.Row([
    dbc.Col(
        dbc.Card(
            dbc.CardBody([
                dbc.Button('Export Data', id='export-button', color='primary', className='w-100')
            ]),
            className="shadow-sm"
        ),
        width=3, md=3
    ),
    dcc.Download(id="download-data"),
    dbc.Col(
        dbc.Card(
            dbc.CardBody([
                dcc.DatePickerSingle(
                    id='date-picker-single',
                    date=datetime.now().date(),
                    display_format='YYYY-MM-DD',
                )
            ],
            style={'padding': '10px', 'textAlign': 'center'},),
        className='center-content h-100',
        ),
        width=3, md=2
    ),
    dbc.Col(
        dbc.Card(
            dbc.CardBody([
                dbc.Select(
                    id='scaling-dropdown',
                    options=[
                        {'label': 'Minimal', 'value': 'none'},
                        {'label': 'Linear Scaling', 'value': 'linear'},
                        {'label': 'Logarithmic Scaling', 'value': 'logarithmic'}
                    ],
                    value='none',
                    className='w-100'
                )
            ]),
            className="shadow-sm"
        ),
        width=3, md=3
    ),
    dbc.Col(
        dbc.Card(
            dbc.CardBody([
                dbc.Button("About", id="open-offcanvas", n_clicks=0, className='w-100')
            ]),
            className="shadow-sm"
        ),
        width=3, md=3
    )
], className="mb-3", justify="center")  # Ensuring the row is centered

# Offcanvas placed outside the controls Row for proper layout
offcanvas = dbc.Offcanvas(
    [
        html.P("Welcome to the Seismic Activity Visualizer! This interactive tool uses data from the United States Geological Survey (USGS) API to bring you real-time and historical insights into global earthquake activity."),
        html.P("Here’s how you can engage with the visualizer:"),
        html.Ul([
            html.Li("Select a Specific Date: Choose a particular day to explore detailed seismic events. The interactive map will display locations, magnitudes, and more about the earthquakes that occurred on that day."),
            html.Li("Adjust the View: Customize how you view earthquake data by adjusting the scaling of earthquake magnitudes through our user-friendly options."),
            html.Li("Export Data: Interested in a deeper analysis or need to keep records? You can export the earthquake data for the chosen date into a CSV file at your convenience.")
        ]),
        html.P("Dive in and tailor your experience as you explore the dynamics of Earth's seismic activities right at your fingertips!"),
    ],
    id="offcanvas",
    title="Hey There!",
    is_open=False,
)


graph_container = dbc.Card(
    dbc.CardBody([
        dcc.Graph(id='earthquake-map', style={'height': '80vh'})
    ]),
    className="mb-3 shadow-sm p-3 bg-white rounded"
)

data_table_container = dbc.Card(
    dbc.CardBody([
        DataTable(
            id='earthquake-data-table',
            columns=[
                {"name": i, "id": i} for i in ['time', 'magnitude', 'place', 'longitude', 'latitude', 'type', 'status', 'url']
            ],
            data=[],  # Initialized as empty
            style_table={'height': '400px', 'overflowY': 'auto'},
            filter_action='none',  # Enables filtering
            sort_action='native',  # Enables sorting
            sort_mode='multi',
            column_selectable=False,
            row_selectable= False,
            page_action="native",
            page_current=0,
            page_size=10,
        )
    ]),
    className="mb-3 shadow-sm p-3 bg-white rounded"
)


info_container = dbc.Card(
    dbc.CardBody([
        html.H4("Exported Data Documentation:", className='mb-3'),
        html.P([
            "This dashboard utilizes data sourced from the ",
            html.A("ANSS Comprehensive Earthquake Catalog (ComCat)", href="https://earthquake.usgs.gov/data/comcat/", target="_blank"),
            ", which includes various earthquake source parameters and products produced by contributing seismic networks."
        ], className='mb-3'),
        html.P([
            "The ComCat database provides a comprehensive record of earthquake data globally, offering parameters such as hypocenters, magnitudes, and seismic phase data. It also includes derived products like moment tensor solutions and ShakeMaps."
        ], className='mb-3'),
        html.P([
            "For detailed information on the data, definitions, and formats available, as well as guidelines on how to access and utilize these resources effectively, please refer to the ",
            html.A("ComCat Documentation", href="https://earthquake.usgs.gov/data/comcat/", target="_blank"),
            "."
        ], className='mb-3'),
        dbc.Button("Learn More", color="info", href="https://earthquake.usgs.gov/data/comcat/data-eventterms.php#mag", external_link=True)
    ]),
    className="mb-3 shadow-sm p-3 bg-white rounded"
)



app.layout = dbc.Container([
    dbc.Row(dbc.Col(html.H1("Seismic Activity Visualizer", className='text-center mb-4'))),
    dbc.Row(dbc.Col(controls)),  # Ensure this variable matches your definition
    dbc.Row(dbc.Col(offcanvas, style={"position": "fixed", "top": 0, "right": 0})),
    dbc.Row(dbc.Col(graph_container)),  # Ensure graph_container is defined similarly using dbc components
    dbc.Row(dbc.Col(data_table_container)), 
    dbc.Row(dbc.Col(info_container)),  # Ensure info_container is adapted similarly
], fluid=True)

@app.callback(
    Output("offcanvas", "is_open"),
    Input("open-offcanvas", "n_clicks"),
    [State("offcanvas", "is_open")],
)
def toggle_offcanvas(n1, is_open):
    if n1:
        return not is_open
    return is_open

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
    Output('earthquake-data-table', 'data'),
    [Input('date-picker-single', 'date')]
)
def update_data_table(selected_date):
    if not selected_date:
        raise PreventUpdate
    data = get_data(selected_date)
    # Transform data into a list of dictionaries suitable for a DataTable
    table_data = [
        {'time': convert_timestamp(d['properties']['time']),  # Convert time for human readability
         'magnitude': d['properties']['mag'],
         'place': d['properties']['place'],
         'longitude': d['geometry']['coordinates'][0],
         'latitude': d['geometry']['coordinates'][1],
         'type': d['properties']['type'],
         'status': d['properties']['status'],
         'url': d['properties']['url'],}
        for d in data
    ]
    return table_data



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
