#   get_full_articles.py
#       Scrapes full article text and insert to database.
#       DO NOT CALL 'run_all'. This runs for the entirety of the database.
#
#
#       Questions: 
#           Read every article, or every article with matches (simart_id's)?
#               Every article. In summarization, create 2 different approaches to 1 article vs matching articles.
#


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.firefox.options import Options


import pandas as pd
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import requests
from bs4 import BeautifulSoup

import importlib
import re
import ast

import utils

class DataCollector:
    def __init__(self):
        self.data_list = []

    def append_data(self, new_data):
        self.data_list.append(new_data)

    def get_dataframe(self):
        return pd.DataFrame(self.data_list)

#   Send the text corresponding to the article_id to database.
def insert_articles(connection, df):
    cursor = connection.cursor()
    for index, row in df.iterrows():
        cursor.execute("""
            INSERT INTO article_text (article_id,article_content)
            VALUES (%s, %s)
            ON CONFLICT (article_id) DO NOTHING
        """, (row['article_id'], row['article_content']))
    
    connection.commit()
    cursor.close()

def cnn_reader(driver):
    body = ' '.join([p.text for p in driver.find_elements(By.XPATH, '//*[@data-component-name="paragraph"]') if p])
    return body

def fox_reader(driver):
    ctx = driver.find_element(By.CLASS_NAME,'article-body')
    body_eles = [p for p in ctx.find_elements(By.TAG_NAME,'p')]
    if body_eles[0].get_attribute('class') != "speakable":
        body_eles.pop(0)
    body = ' '.join([p.text for p in body_eles])
    return body

def ap_reader(driver):
    try:
        driver.find_element(By.ID,'onesignal-slidedown-cancel-button').click()
        driver.find_element(By.CSS_SELECTOR,'.bcpNotificationBarClose.bcpNotificationBarCloseIcon.bcpNotificationBarCloseTopRight').click()
    except:
        pass
    try:
        ctx = driver.find_element(By.TAG_NAME,'bsp-story-page')
    except:
        ctx = driver.find_element(By.CSS_SELECTOR,'.Page-content')
    body = ' '.join([p.text for p in ctx.find_elements(By.TAG_NAME,'p')])
    return body

def npr_reader(driver):
    ctx = driver.find_element(By.ID,'storytext')
    body = ' '.join([p.text for p in ctx.find_elements(By.TAG_NAME,'p')])
    return body

def hufpo_reader(driver):
    ctx = driver.find_element(By.ID,'entry-body')
    body = ' '.join([p.text for p in ctx.find_elements(By.TAG_NAME,'p')])
    return body


def cbs_reader(driver):
    ctx = driver.find_element(By.CLASS_NAME,'content__body')
    body = ' '.join([p.text for p in ctx.find_elements(By.TAG_NAME,'p')])
    return body

#   Get text from articles
def read_articles(url_list):
    options = Options()
    options.add_argument('-headless')
    driver = webdriver.Firefox(options=options)
    driver.fullscreen_window()

    source_map = {
        'CNN': cnn_reader,
        'FOX': fox_reader,
        'AP': ap_reader,
        'NPR': npr_reader,
        'HuffPost': hufpo_reader,
        'CBS': cbs_reader
    }
    ready_df = pd.DataFrame(columns=['article_id','article_content'])
    for url,article_id,source in url_list:
        #   Paywalled sources
        if source in ['NYT','WAPO']:
            body = np.NAN
            ready_df.loc[len(ready_df)] = [article_id,body]
            continue
        #print(source,url)
        driver.get(url)
        try:
            reader_function = source_map[source]
            body = reader_function(driver)
        except:
            body = np.NAN

        ready_df.loc[len(ready_df)] = [article_id,body]

    driver.quit()
    return ready_df

#   DO NOT CALL.
#       Runs on all articles in database.
#       For more selective calls, get urls and send to read_articles
def run_all():
    connection = utils.connect_db()

    df = pd.read_sql_query("""
        SELECT a.article_id,a.url,a.article_source FROM articles a
        JOIN junct_simart_articles jsa ON jsa.article_id = a.article_id
        JOIN similar_articles sa ON jsa.simart_id = sa.simart_id
    """, con=connection)
    connection.close()

    print(df)
    url_list = df[['url','article_source']].values.tolist()
    res = read_articles(url_list)


#   Run daily
#       Gets text for articles in matches
def run_daily():
    connection = utils.connect_db()
    df = pd.read_sql_query("""
    SELECT 
	sa.simart_id,
	a.article_id,
	a.url,
	a.date,
	a.article_source
	FROM similar_articles sa
	JOIN junct_simart_articles jsa ON jsa.simart_id = sa.simart_id
	JOIN articles a ON a.article_id = jsa.article_id
	JOIN junct_simart_keywords jsk ON jsk.simart_id = sa.simart_id
	JOIN keywords kw ON kw.keyword_id = jsk.keyword_id
	WHERE sa.similar_weight >= 0.8
	AND EXISTS (
	SELECT 1
	FROM articles a2 
	JOIN junct_simart_articles jsa2 ON jsa2.article_id = a2.article_id
	WHERE jsa2.simart_id = sa.simart_id
	AND a2.date >= NOW() - INTERVAL '2 days'
	)
	GROUP BY sa.simart_id, sa.similar_weight, a.article_id, a.title, a.url, a.date, a.article_section, a.section_url, a.article_source, a.image, a.subheading
	ORDER BY sa.simart_id;
                           """,con=connection)
    try:
        url_list = df[['url','article_id','article_source']].values.tolist()
        res = read_articles(url_list)
        res['article_id'] = res['article_id'].astype(int)

        insert_articles(connection,res)
        connection.close()
    except:
        print("Fucking error")
        pass


#run_daily()
