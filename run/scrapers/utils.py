from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import DBSCAN
from keybert import KeyBERT
from collections import defaultdict
from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer, util
from sklearn.cluster import AgglomerativeClustering
import spacy
import pandas as pd
import numpy as np
import psycopg2
import requests
import re
import ast
import warnings
import boto3
import json
warnings.filterwarnings("ignore")

#   Note: models Spacy and SentenceTransformer are saved in the 'models' folder.

#==================================================================================
#       keyword_extraction
#==================================================================================

def init_keywords():
    nlp = spacy.load('./models/spacy')
    kw_model = KeyBERT()
    weights = {'pos':1,'ner':2,'manual':1.1}
    common_keywords = [
        # Geopolitical and Regional Keywords
        "israel", "palestine", "gaza", "russia", "ukraine", "china", 
        "taiwan", "usa", "america", "iran", "india", "middle east", 
        "north korea", "un", "eu", "border","u.s.","afghanistan","iraq",

        # Technology and Business Keywords
        "ai", "artificial intelligence", "machine learning", 
        "cryptocurrency", "blockchain", "stocks", "economy", "recession", 
        "inflation", "interest rates", "big tech", "startup", 
        "ipo", "merger", "acquisition", "amazon", "google", "meta", "tesla",

        # Political and Legal Keywords
        "election", "president", "congress", "senate", "supreme court", 
        "legislation", "sanctions", "campaign", "investigation", 
        "impeachment", "protest", "vote", "ballot", "governor","government",

        # Health and Environmental Keywords
        "covid", "vaccine", "pandemic", "climate change", 
        "global warming", "wildfire", "hurricane", "earthquake", 
        "flood", "outbreak", "healthcare", "hospitals",

        # Crime and Security Keywords
        "hamas", "terrorism", "cybersecurity", "hacking", 
        "police", "shooting", "arrest", "fbi", "war", 
        "conflict", "defense", "military",'secret service',"immigration",

        # Social and Cultural Keywords
        "celebrity", "tiktok", "twitter", "x", "sports", 
        "olympics", "world cup", "movies", "hollywood", 
        "netflix", "protest", "rally", "social media", 
        "influencer",

        # Popular Politicians/People
        #   Try only last names to avoid redunancy
        "musk","trump","harris","biden","pelosi","obama"
    ]
    return nlp,kw_model,common_keywords,weights

#=========================================
#       Keyword Extraction Functions
#=========================================

#   Part of Speech 
def POS(title,nlp):
    doc = nlp(title.lower())
    title_words = []
    # Focus on nouns, proper nouns, and (possibly) adjectives
    for token in doc:
        if token.pos_ in ('NOUN', 'PROPN') and not token.is_stop:
            title_words.append(token.lemma_)
        elif token.pos == 'VERB' and not token.is_stop:
            title_words.append(token.lemma_)
    return title_words

#   Named Entity Recognition
def NER(text,nlp):
    doc = nlp(text)
    excluded_labels = ['DATE', 'ORDINAL', 'CARDINAL', 'MONEY', 'TIME', 'QUANTITY', 'PERCENT']  
    entities = [
        (ent.text, ent.label_) 
        for ent in doc.ents 
        if ent.label_ not in excluded_labels
    ]
    return entities

def common_keyword_check(text,common_keywords):
    normalized_headline = re.sub(r"[^\w\s']", "", text.lower())
    words = normalized_headline.split()

    matches = [word for word in words if word in common_keywords]
    for kw in common_keywords:
        cleaned_word = kw+' '
        if cleaned_word in normalized_headline and kw not in matches:
            matches.append(kw)
    return set(matches)

#=========================================
#       Helper Functions
#=========================================
#   Normalize the confidence interval of KeyBERT
def normalize_confidence(conf, min_conf=0.5, max_conf=1.0, target_max=2.0):
    """Normalize confidence scores from KeyBERT to match the weight scale."""
    return ((conf - min_conf) / (max_conf - min_conf)) * target_max

def normalize_keyword(keyword):
    """Extract and normalize the keyword text."""
    if isinstance(keyword, tuple):
        keyword = keyword[0]  # Extract the text from (text, label) tuples
        
    return keyword.lower()

# Aggregate keywords from all sources
def aggegate_keywords(weights, pos, ner, kbrt, common_kw):
    keyword_scores = defaultdict(float)  # Store only scores (no sources)

    # Add POS keywords
    for kw in pos:
        normalized_kw = normalize_keyword(kw)
        keyword_scores[normalized_kw] += weights["pos"]

    # Add NER keywords
    for kw, _ in ner:  # Unpack (keyword, label) tuples
        normalized_kw = normalize_keyword(kw)
        keyword_scores[normalized_kw] += weights["ner"]

    # Add KeyBERT keywords with normalized confidence
    for kw, confidence in kbrt:
        normalized_kw = normalize_keyword(kw)
        normalized_score = normalize_confidence(confidence)
        keyword_scores[normalized_kw] += normalized_score

    # Add common keywords
    for kw in common_kw:
        normalized_kw = normalize_keyword(kw)
        keyword_scores[normalized_kw] += weights['manual']

    # Sort keywords by their aggregated scores
    sorted_keywords = sorted(keyword_scores.items(), key=lambda x: -x[1])
    sorted_keywords = [k for k, score in sorted_keywords if score > 1]  # Return only keywords
    return sorted_keywords


#       Must pass init_keywords() values
def get_keywords(title, nlp, kw_model, common_keywords, weights):
    keybert_keywords = kw_model.extract_keywords(title)
    pos_keywords = POS(title, nlp)
    ner_keywords = NER(title, nlp)
    manually_found = common_keyword_check(title, common_keywords)
    
    # Aggregate keywords and return the list
    keywords = aggegate_keywords(weights, pos_keywords, ner_keywords, keybert_keywords, manually_found)
    
    return keywords

#==================================================================================
#       dbconnect
#==================================================================================


def connect_db():
    # Establish the connection to PostgreSQL
    connection = psycopg2.connect(
        dbname='postgres',
        user='postgres',
        password='P7c0Eg(9{NYwv7tpV5S6J{Bw8(J?',
        host='news-site-db.c5ecco0sis2u.us-west-1.rds.amazonaws.com',
        port='5432'
    )
    return connection

def insert_articles(connection, df):
    # Create a cursor object using the connection
    cursor = connection.cursor()

    # Insert articles using ON CONFLICT to handle duplicates
    for index, row in df.iterrows():
        cursor.execute("""
            INSERT INTO raw_articles (article_source, article_section, section_url, title, url, article_keywords, date, image, subheading)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO NOTHING
        """, (row['Source'], row['Section'], row['Section URL'], row['Article Title'], row['Article URL'], row['Keywords'], row['Date'], row['Image'], row['Subheading']))


    # Commit and close
    connection.commit()
    cursor.close()

def insert_summaries(connection,df):
    # Create a cursor object using the connection
    cursor = connection.cursor()

    # Insert articles using ON CONFLICT to handle duplicates
    for index, row in df.iterrows():
        cursor.execute("""
            INSERT INTO similar_article_summaries (simart_id,summary)
            VALUES (%s, %s)
            ON CONFLICT (simart_id) DO NOTHING
        """, (row['simart_id'], row['summary']))

    # Commit and close
    connection.commit()
    cursor.close()

#==================================================================================
#       match_finder
#==================================================================================

def insert_similar_articles(connection, df):
   # Create a cursor object using the connection
    cursor = connection.cursor()

    # Insert articles using ON CONFLICT to handle duplicates
    for index, row in df.iterrows():
        cursor.execute("""
            INSERT INTO raw_similar_articles (article_urls, article_headlines, keywords, similar_weight)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (article_urls) DO NOTHING
        """, (row['Article URLs'], row['Article Headlines'], row['Keywords'], row['Similarity Weights']))


    # Commit and close
    connection.commit()
    cursor.close()

def remove_duplicates_article_rows(article_df):
    # Remove rows with same "Article URL" (exact duplicates)
    article_df_cleaned = article_df.drop_duplicates(subset=['Article URL'], keep='first').reset_index(drop=True)

    unique_urls = set()

    # Check if the URL is a duplicate
    def is_duplicate(url):
        return any(url in other_url and url != other_url for other_url in unique_urls) or \
               any(other_url in url and url != other_url for other_url in unique_urls)

    # Apply is_duplicate to each URL
    article_df_cleaned['is_duplicate'] = article_df_cleaned['Article URL'].apply(is_duplicate)

    # Filter the duplicates and remove is_duplicate column
    article_df_cleaned = article_df_cleaned[article_df_cleaned['is_duplicate'] == False].drop(columns=['is_duplicate']).reset_index(drop=True)

    return article_df_cleaned


def get_similar_articles(article_df):
    # Initialize
    model = SentenceTransformer('./models/sentence_transformer')
    titles = article_df['Article Title'].tolist()
    keywords = article_df['Keywords'].tolist()
    sources = article_df['Source'].tolist()
    embeddings = model.encode(titles)
    simart_df = pd.DataFrame(columns=['Article Headlines', 'Article URLs', 'Keywords', 'Similarity Weights'])

    #   Get cosine similarity
    similarity_matrix = cosine_similarity(embeddings)

    #   Iterate through similarity matrix and emphasize weights of clusters with:
    #       - Diversity of sources
    #       - Common keywords
    for i in range(len(article_df)):
        for j in range(i + 1,len(article_df)):
            #   Diversity of Sources
            if sources[i] != sources[j]:
                similarity_matrix[i,j] += 0.1
            else:
                similarity_matrix[i,j] -= 0.5
            #   Keywords in Common
            #       For some reason, keywords are stored as strings. Convert back to list, then get set
            if isinstance(keywords[i], str):
                s1 = set(ast.literal_eval(keywords[i]))
            else:
                s1 = set(keywords[i])
            if isinstance(keywords[j], str):
                s2 = set(ast.literal_eval(keywords[j]))
            else:
                s2 = set(keywords[j])
            keyword_match_count = len(s1.intersection(s2))

            similarity_matrix[i,j] += keyword_match_count*0.033
            #   Maintain symmetry
            similarity_matrix[j,i] = similarity_matrix[i,j]

    #   Clip to avoid negative weights. Slightly alters matches, however DBSCAN cannot take negative weights.
    #       This will only affect the least-similar articles, making them slightly more similar. 
    #       (They will be cut by the similarity threshold anyways)
    similarity_matrix = np.clip(similarity_matrix, 0, 1)
    sim_thresh = 0.9
    clustering = DBSCAN(metric='precomputed',eps=1-sim_thresh,min_samples=2)
    labels = clustering.fit_predict(1-similarity_matrix)

    # Tie 'labels' group back to article titles
    cluster_dict = defaultdict(list)
    for label, row in zip(labels, article_df.iterrows()):  # Iterate over DataFrame rows
        index, row_data = row  # Unpack index and the row's data
        if label != -1:  # Exclude articles with no cluster
            cluster_dict[label].append(row_data)  

    # Calculate similarity score for each cluster
    cluster_similarity_scores = {}
    for label in set(labels):
        if label != -1:  # Ignore noise points (articles without clusters)
            # Get indices of articles in the current cluster
            cluster_indices = [i for i, lbl in enumerate(labels) if lbl == label]
            # Calculate average similarity within the cluster
            cluster_similarities = [similarity_matrix[i, j] for i in cluster_indices for j in cluster_indices if i != j]
            cluster_similarity_scores[label] = np.mean(cluster_similarities) if cluster_similarities else 0

    # Print clusters and similarity scores
    for cluster_id, articles in cluster_dict.items():
        similarity_weight = round(float(cluster_similarity_scores[cluster_id]),2)
        #print(f"Cluster {cluster_id} (Similarity Score: {similarity_weight}):")
        url_clust = [article['Article URL'] for article in articles]
        title_clust = [article['Article Title'] for article in articles]
        # Get Keywords shared by all articles
        #   Aggregate keyword lists from each title into a 2d list
        raw_keywords_clust = [article['Keywords'] for article in articles]
        raw_keywords_clust = [ast.literal_eval(keywords) if isinstance(keywords, str) else keywords for keywords in raw_keywords_clust]
        #   Start with the set of the first article's keywords
        keywords_clust = set(raw_keywords_clust[0])
        #   Get all interesection keywords (those that appear in all)
        for sublst in raw_keywords_clust[1:]:
            keywords_clust.intersection_update(sublst)
        keywords_clust = list(keywords_clust)
        simart_df.loc[len(simart_df)] = [title_clust,url_clust,keywords_clust,similarity_weight]
    
    return simart_df

#   Start the 2nd instance
def trigger_second_instance():
    try:
        lambda_client = boto3.client('lambda')
        response = lambda_client.invoke(
            FunctionName='Manage_EC2_Instance',
            InvocationType='RequestResponse',
            Payload=json.dumps({"instance": "second"})
        )
        print("Second instance started")
        return True
    except Exception as e:
        print(f"Error starting second instance: {str(e)}")
        return False


#==================================================================================
#       Send article text df to bucket for summarizing
#==================================================================================
def send_to_bkt():
    connection = connect_db()
    df = pd.read_sql_query("""
        SELECT 
            sa.simart_id,
            a.article_id,
            atx.article_content
        FROM similar_articles sa
            JOIN junct_simart_articles jsa ON jsa.simart_id = sa.simart_id
            JOIN articles a ON a.article_id = jsa.article_id
            JOIN article_text atx ON atx.article_id = a.article_id
        WHERE sa.similar_weight >= 0.8
        AND EXISTS (
            SELECT 1
            FROM articles a2 
            JOIN junct_simart_articles jsa2 ON jsa2.article_id = a2.article_id
            WHERE jsa2.simart_id = sa.simart_id
            AND a2.date >= NOW() - INTERVAL '2 days'
        )
        GROUP BY sa.simart_id,a.article_id,atx.article_content
        ORDER BY sa.simart_id;
                        """,con=connection)
    connection.close()

    completed_check = pd.DataFrame({'status':['incomplete']})
    completed_check.to_csv('s3://news.summ.bkt/completed.txt', index=False)
    df.to_csv('s3://news.summ.bkt/unsummarized.csv', index=False)

send_to_bkt()
