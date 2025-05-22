#=======================================
#    Main.py
#        This file defines the processing pipeline of the entire project.
#=======================================

import glob
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from selenium.common.exceptions import StaleElementReferenceException

from selenium.webdriver.firefox.service import Service

import requests
from bs4 import BeautifulSoup

import time
from datetime import datetime, timedelta
from datetime import date
import re
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

import spacy
from sentence_transformers import SentenceTransformer

from concurrent.futures import ThreadPoolExecutor,wait

import utils
import scrape
import get_full_article

import boto3
import os

class DataCollector:
    def __init__(self):
        self.data_list = []

    def append_data(self, new_data):
        self.data_list.append(new_data)

    def get_dataframe(self):
        return pd.DataFrame(self.data_list)

#=====
#   helpers
#=====

def safe_join(value):
    if isinstance(value, list):
        return '|||'.join(value)  # Use the unique delimiter
    elif isinstance(value, str):
        # Already a string, return as is
        return value
    else:
        # Handle other types if necessary
        return str(value)

#   Avoid shitty chars
def clean_text(text):
    return re.sub(r'[^\x00-\x7F]+', '', text) 

#=====
#   Main
#=====
def scrape_site(site):
    name, func, output = site
    print(name)
    collector = DataCollector()
    func(collector)
    collector.get_dataframe().to_csv(output, index=False)

def run():
    sites = [
        ("FOX", scrape.foxnews, "fox.csv"),
        ("AP", scrape.ap, "ap.csv"),
        ("CBS", scrape.cbs, "cbs.csv"),
        ("CNN", scrape.cnn, "cnn.csv"),
        ("HUFF", scrape.huffpost, "huffpost.csv"),
        ("NPR", scrape.npr, "npr.csv"),
        ("NYT", scrape.nyt, "nyt.csv"),
        ("WAPO",scrape.wapo,"wapo.csv")
    ]
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(scrape_site, site) for site in sites]
        wait(futures)


import boto3
import logging
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def stop_ec2_instance(instance_id):
    """
    Stops an EC2 instance and handles errors gracefully.
    
    Args:
        instance_id (str): The ID of the EC2 instance to stop.
    """
    try:
        # Create an EC2 client
        ec2_client = boto3.client('ec2', region_name='us-west-1')
        
        # Stop the EC2 instance
        logging.info(f"Attempting to stop instance {instance_id}...")
        response = ec2_client.stop_instances(InstanceIds=[instance_id])
        
        # Extract the stopping status
        stopping_status = response.get('StoppingInstances', [{}])[0]
        current_state = stopping_status.get('CurrentState', {}).get('Name', 'Unknown')
        previous_state = stopping_status.get('PreviousState', {}).get('Name', 'Unknown')
        
        logging.info(f"Instance {instance_id} stopped successfully. "
                     f"State changed from {previous_state} to {current_state}.")
    
    except NoCredentialsError:
        logging.error("AWS credentials not found. Ensure credentials are properly configured.")
    except PartialCredentialsError:
        logging.error("Incomplete AWS credentials. Please check your AWS configuration.")
    except ClientError as e:
        logging.error(f"An AWS ClientError occurred: {e.response['Error']['Message']}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")



if __name__ == "__main__":
    run()

    #   Combine CSV's
    csv_files = glob.glob("*.csv")
    excluded_csvs = ['articles.csv','simart.csv','test.csv','combined_data.csv']
    dataframes = [pd.read_csv(file) for file in csv_files if file not in excluded_csvs and os.path.getsize(file) > 2] # Specify the scraped csv's + exclude the list
    data = pd.concat(dataframes, ignore_index=True) if dataframes else pd.DataFrame()

    print("Pulled df")
    
    #   Get Keywords
    data['Article Title'] = data['Article Title'].astype(str)
    nlp,kw_model,common_keywords,weights = utils.init_keywords()
    data['Keywords'] = data['Article Title'].apply(lambda title: utils.get_keywords(title, nlp, kw_model, common_keywords, weights))
    

    #   process data, create similar_articles_df, send to db
    data['Date'] = pd.to_datetime(data['Date'], errors='coerce')

    # Fill missing dates (NaT) with the current date
    data['Date'] = data['Date'].fillna(pd.Timestamp(date.today()))

    # Convert to string format 'YYYY-MM-DD' for database insertion
    data['Date'] = data['Date'].dt.strftime('%Y-%m-%d')

    cleaned_art_df = utils.remove_duplicates_article_rows(data)
    similar_articles_df = utils.get_similar_articles(cleaned_art_df)
    
    #   Fix shitty chars
    data['Keywords'] = data['Keywords'].fillna('').astype(str)
    similar_articles_df['Keywords'] = similar_articles_df['Keywords'].fillna('').astype(str)
    data['Keywords'] = data['Keywords'].apply(clean_text)
    similar_articles_df['Keywords'] = similar_articles_df['Keywords'].apply(clean_text)

    # Apply the safe_join function to the columns
    similar_articles_df['Article Headlines'] = similar_articles_df['Article Headlines'].apply(safe_join)
    similar_articles_df['Article URLs'] = similar_articles_df['Article URLs'].apply(safe_join)
    similar_articles_df['Keywords'] = similar_articles_df['Keywords'].apply(safe_join)
    
    data.to_csv('articles.csv')
    similar_articles_df.to_csv('simart.csv')

    print("Saved df's")

    #data = pd.read_csv('articles.csv')
    #similar_articles_df = pd.read_csv('simart.csv')

    # upload to db
    print("Attempting db connection...")
    connection = utils.connect_db()
    print("connected to db")

    # Change keywords from list to comma-separated string
    data['Keywords'] = data['Keywords'].apply(lambda x: ','.join(x) if isinstance(x, list) else x)

    print('connected, inserting...')
    utils.insert_articles(connection, data)
    utils.insert_similar_articles(connection,similar_articles_df)

    print("Processing data via sql script...")
    with connection.cursor() as cursor:
        with open('insert.sql','r') as sql_file:
            sql_script = sql_file.read()
        statements = [stmt.strip() for stmt in sql_script.split(';') if stmt.strip()]
        
        for statement in statements:
            cursor.execute(statement)
    connection.commit()
    connection.close()
    print("Data processing done")

    #   get article text
    get_full_article.run_daily()

    #   Send text df to bucket for summarizing
    utils.send_to_bkt()

    #   Start 2nd instance
    utils.trigger_second_instance()

    #   Wait for 2nd instance process to complete.
    while True:
        try:
            # Read the status file
            status_df = pd.read_csv('s3://news.summ.bkt/completed.txt')
            
            # Check if status is 'complete'
            if 'complete' in status_df['status'].values:
                print("Processing complete! Reading data...")
                summary_df = pd.read_csv('s3://news.summ.bkt/summarized.csv')
                break
            else:
                print("Still processing, waiting...")
        except Exception as e:
            print(f"Error waiting for completed status on 2nd instance: {e}")

        time.sleep(30)  # Check every 30 seconds
    
    #   2nd instance completed, sending data to database.
    connection = utils.connect_db()
    utils.insert_summaries(connection,summary_df)
    connection.close()

    #   Stop instance
    instance_id = "i-0ef94ad5baad81920"
    stop_ec2_instance(instance_id)
