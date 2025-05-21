import pandas as pd
import numpy as np
import os
import re
import boto3
import logging
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from rouge import Rouge

import utils

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

def preprocess(texts):
    cleaned = []
    for t in texts:
        #   Remove missing articles
        if pd.isna(t):
            continue
        t_clean = re.sub(r'[^\w\s\'\"$£€;\-:.,]', '', str(t)) # remove excessive punctuation, keep periods, quotes
        t_clean = t_clean.replace('  ',' ')
        #   Empty texts
        if t_clean.lower() == 'nan' or not t_clean.strip():
            continue
        
        cleaned.append(t_clean)
        #   check for dupe text
    
    return cleaned

def clean(df):
    rows_to_drop = []   # Drop empty matches after cleaning

    for i,r in df.iterrows():
        text_list = r['article_content']
        
        #   Clean texts
        cleaned_texts = preprocess(text_list)
        seen = set()
        unique_lst = [
            x
            for x in cleaned_texts 
            if not (x.strip().lower() in seen or seen.add(x.strip().lower()))
        ]
 
        df.at[i,'article_content'] = unique_lst
        if len(cleaned_texts) < 2:
            rows_to_drop.append(i)

    df.drop(rows_to_drop,inplace=True)
        
    return df

def generate_summary2(model, tokenizer, article_clust):
    # Check if empty cluster
    if not article_clust:
        return "No content to summarize."

    # Join articles, use <doc-sep> to separate them
    article_text = "<doc-sep>".join(article_clust)
    
    inputs = tokenizer(article_text, return_tensors="pt", max_length=2048, truncation=True).to("cuda")
    #   max_length is in tokens, not chars

    summary_ids = model.generate(inputs["input_ids"], max_length=200, min_length=50, length_penalty=2.0, num_beams=6)
    #   length_pentalty -> Penalty set on length of summary, >1 penalizes long summaries, <1 favors
    #   num_beams -> # of beams used in beam search (deciding over summary candidates): high = better quality, slower, less diverse

    summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
    return summary

#   Takes dataframe of grouped articles
#   Returns dataframe of summaries and simart_id's
def summarize(df):
    grouped_df = df.groupby('simart_id')['article_content'].apply(list).reset_index()
    grouped_df = clean(grouped_df)
    tokenizer = AutoTokenizer.from_pretrained("allenai/PRIMERA")
    model = AutoModelForSeq2SeqLM.from_pretrained("allenai/PRIMERA").to("cuda")

    a2_summary_df = pd.DataFrame(columns=['simart_id','summary'])

    for i,r in grouped_df.iterrows():
        simart_id = r['simart_id']
        cluster_articles = r['article_content']
        
        summary = generate_summary2(model,tokenizer,cluster_articles)
        
        a2_summary_df = pd.concat([
            a2_summary_df,
            pd.DataFrame({'simart_id': [simart_id], 'summary': [summary]})
        ], ignore_index=True)
    
    return a2_summary_df

#   Temp test
if __name__ == '__main__':
    os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
    df = pd.read_csv('s3://news.summ.bkt/unsummarized.csv')

    summary_df = summarize(df)
    summary_df.to_csv('s3://news.summ.bkt/summarized.csv', index=False)

    #   Mark that process is completed, 1st instance can proceed
    completed_check = pd.DataFrame({'status': ['complete']})
    completed_check.to_csv('s3://news.summ.bkt/completed.txt', index=False)

    #   Stop instance
    instance_id = "i-0a29d5cdee7289cde"
    stop_ec2_instance(instance_id)
