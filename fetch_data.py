import requests
from pymongo import MongoClient
from datetime import datetime, timedelta
import logging, os

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration directly from environment variables
database_url = os.getenv('DATABASE_URL')
base_url = os.getenv('USGS_BASE_URL')

client = MongoClient(database_url)
db = client.earthquake_db
collection = db.earthquakes

# Ensure an index on the 'properties.time' field
collection.create_index([("properties.time", 1)])  # 1 for ascending order

def parse_date(date_str):
    """Attempt to parse the date with or without time and microseconds."""
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"date_str {date_str} is not in the expected format")

def fetch_earthquake_data(start_date, end_date):
    url = f"{base_url}?format=geojson&starttime={start_date}&endtime={end_date}"
    logging.debug(f"Fetching data from URL: {url}")
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data['features']
    except requests.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err}")
    except Exception as err:
        logging.error(f"An error occurred: {err}")

def store_data(data):
    try:
        if data:
            for feature in data:
                collection.update_one(
                    {'id': feature['id']},  # Condition to find the document
                    {'$setOnInsert': feature},  # Set fields only if it's an insert operation
                    upsert=True  # Create a new document if one doesn't exist
                )
            logging.info("Data upserted successfully.")
        else:
            logging.info("No data to insert")
    except Exception as e:
        logging.error(f"Error storing data: {e}")


def check_and_fetch_data(start_date, end_date):
    try:
        start_datetime = parse_date(start_date)
        end_datetime = parse_date(end_date)
        current_date = start_datetime

        while current_date <= end_datetime:
            next_date = current_date + timedelta(days=1)
            data_count = collection.count_documents({
                'properties.time': {
                    '$gte': current_date.timestamp() * 1000,
                    '$lt': next_date.timestamp() * 1000
                }
            })
            if data_count == 0:
                fetched_data = fetch_earthquake_data(current_date.strftime('%Y-%m-%d'), next_date.strftime('%Y-%m-%d'))
                if fetched_data:
                    store_data(fetched_data)
            current_date = next_date

        logging.info("Data fetching and storage completed as required.")

    except Exception as e:
        logging.error(f"Error in check_and_fetch_data: {e}")

if __name__ == '__main__':
    # Example to check and fetch data
    # check_and_fetch_data('2024-04-01', '2024-04-02')
    pass
