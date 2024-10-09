import pandas as pd
import psycopg2

def connect_db():
    # Establish the connection to PostgreSQL
    connection = psycopg2.connect(
        dbname='postgres',
        user='postgres',
        password='P7c0Eg(9{NYwv7tpV5S6J{Bw8(J?',
        host='database-postgresql.c5ecco0sis2u.us-west-1.rds.amazonaws.com',
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

# Example usage
'''
# Connect and insert
connection = connect_db()
insert_articles(connection, articles_df)
insert_similar_articles(connection, similar_articles_df)
connection.close()
'''
