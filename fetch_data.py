import requests
import json
from pymongo import MongoClient
from datetime import datetime

with open('config.json', 'r') as file:
        config = json.load(file)

base_url = config.get('usgs_base_url', 'default_base_url')
database_url = config['database_url']

def fetch_earthquake_data(start_date, end_date):
    url = f"{base_url}?format=geojson&starttime={start_date}&endtime={end_date}"
    #url = f'https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={start_date}&endtime={end_date}'
    response = requests.get(url)
    data = response.json()
    return data['features']

def store_data(data):
    client = MongoClient(database_url)
    db = client.earthquake_db
    collection = db.earthquakes
    collection.insert_many(data)
    client.close()

def check_and_fetch_data(start_date, end_date):
    client = MongoClient(database_url)
    db = client.earthquake_db
    collection = db.earthquakes
    # Convert date strings to datetime objects for querying
    start_datetime = datetime.strptime(start_date.split('T')[0], '%Y-%m-%d')
    end_datetime = datetime.strptime(end_date.split('T')[0], '%Y-%m-%d')
    # Check if data exists for the given range
    if collection.count_documents({'properties.time': {'$gte': start_datetime.timestamp() * 1000, '$lte': end_datetime.timestamp() * 1000}}) == 0:
        data = fetch_earthquake_data(start_date, end_date)
        if data:
            store_data(data)
    client.close()

if __name__ == '__main__':
    # For testing script directly
    # check_and_fetch_data('2024-04-01', '2024-04-02')
    pass