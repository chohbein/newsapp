from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from selenium.common.exceptions import StaleElementReferenceException

import time
from datetime import datetime
import re
import pandas as pd
import warnings
warnings.filterwarnings("ignore")
from datetime import datetime
import spacy
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


class DataCollector:
    def __init__(self):
        # Store the data as a list of dictionaries (each row is a dictionary)
        self.data_list = []

    def append_data(self, new_data):
        # Append each new data as a dictionary to the list
        self.data_list.append(new_data)

    def get_dataframe(self):
        # Convert the list of dictionaries to a DataFrame when retrieving
        return pd.DataFrame(self.data_list)

collector = DataCollector()

#===================================================================================
#   Functions
#===================================================================================

# Function to extract significant words from a single title using POS filtering
def extract_significant_words_from_title(title,nlp):
    doc = nlp(title.lower())
    title_words = []
    # Focus on nouns, proper nouns, and possibly adjectives
    for token in doc:
        if token.pos_ in ('NOUN', 'PROPN', 'ADJ') and not token.is_stop:
            title_words.append(token.lemma_)
    return title_words

# Function to extract significant words from a list of titles
def extract_significant_words(titles,nlp):
    processed_titles = []  # List to store processed titles
    for title in titles:
        title_words = extract_significant_words_from_title(title,nlp)
        processed_titles.append(' '.join(title_words))  # Join and add to processed titles
    return processed_titles

# Function to find common significant words across all titles
def find_common_significant_words(titles):
    processed_titles = extract_significant_words(titles)
    
    # Flatten list of words for all titles
    all_words = ' '.join(processed_titles).split()
    
    # Count the frequency of each word
    word_counts = Counter(all_words)
    
    # Find words that appear in more than one title (common significant words)
    common_words = [word for word, count in word_counts.items() if count > 1]
    
    return common_words

#===================================================================================
#   News Site Scraping
#===================================================================================
#       Fox
#===================================================================================
def foxnews(collector,nlp):
    url = 'https://www.foxnews.com/'

    driver = webdriver.Firefox()
    driver.get(url)
    driver.find_element(By.CLASS_NAME,'js-menu-toggle').click()

    # Get Sectors
    sector_dict = {}
    sectors = driver.find_elements(By.CLASS_NAME,'nav-title') 
    for i in sectors:
        sector = i.find_element(By.TAG_NAME,'a').get_attribute('aria-label')
        sector_url = i.find_element(By.TAG_NAME,'a').get_attribute('href')
        if sector not in sector_dict:
            sector_dict[sector] = sector_url
        else:
            break
    driver.quit()
    
    # Collect all data in a list
    all_data = []

    # Into Sector Dicts
    for s in sector_dict:
        driver = webdriver.Firefox()
        driver.get(sector_dict[s])
        print(s, sector_dict[s])

        # Scroll to load more articles
        for i in range(8):
            driver.execute_script("window.scrollTo(0, window.pageYOffset + 700);")
            time.sleep(0.3)

        # Extract article data
        for ele in driver.find_elements(By.XPATH, '//a[@href]'):
            url = ele.get_attribute('href')
            if url.count('-') <= 2 or len(ele.text) <= 2 or 'police-and-law-enforcement' in url or not url.startswith(sector_dict[s]):
                continue
            text = ele.text
            keywords = extract_significant_words_from_title(text,nlp)
            date = datetime.today().strftime('%Y-%m-%d')

            # Collect the row data in a dictionary
            row_data = {
                'Source': 'FOX',
                'Section': s,
                'Section URL': sector_dict[s],
                'Article Title': text,
                'Article URL': url,
                'Keywords': keywords,
                'Date': date
            }
            all_data.append(row_data)

        driver.quit()

    # Append all data at once to the DataFrame
    for row in all_data:
        collector.append_data(row)



#===================================================================================
#       CNN
#===================================================================================
def cnn(collector,nlp):
    url = 'https://www.cnn.com/'

    driver = webdriver.Firefox()
    driver.get(url)

    driver.find_element(By.CLASS_NAME, 'header__menu-icon-svg').click()

    # Get Sectors
    sector_dict = {}
    sectors = driver.find_elements(By.CLASS_NAME, 'subnav__section-link')
    for i in sectors:
        sector = i.text
        sector_url = i.get_attribute('href')
        if 'about' in sector.lower():
            break
        sector_dict[sector] = sector_url

    driver.quit()

    # Collect all data in a list
    all_data = []

    # Into Sector Dicts
    for s in sector_dict:
        driver = webdriver.Firefox()
        driver.get(sector_dict[s])
        print(s)

        # Scroll to load more articles
        for i in range(8):
            driver.execute_script("window.scrollTo(0, window.pageYOffset + 700);")
            time.sleep(0.3)

        # Extract article data
        for ele in driver.find_elements(By.XPATH, '//a[@href]'):
            text = ele.text
            url = ele.get_attribute('href')

            # Filter out unwanted URLs and titles
            if len(text) < 10 or url.count('-') < 3 or text.count(' ') < 2 or url in ['', ' '] or 'cnn.com/audio/podcasts' in url:
                continue

            # Extract keywords and current date
            keywords = extract_significant_words_from_title(text,nlp)
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Collect the row data in a dictionary
            row_data = {
                'Source': 'CNN',
                'Section': s,
                'Section URL': sector_dict[s],
                'Article Title': text,
                'Article URL': url,
                'Keywords': keywords,
                'Date': date
            }
            all_data.append(row_data)

        driver.quit()

    # Append all data at once to the DataFrame
    for row in all_data:
        collector.append_data(row)


#===================================================================================
#       WAPO
#===================================================================================
def get_element_with_retry(driver,by,thing):
    i = 0
    while i < 100:
        try:
            element = driver.find_element(by,thing)
            break
        except:
            driver.execute_script("arguments[0].scrollTop += 50;", driver)
    return element
    
def wapo(collector,nlp):
    url = 'https://www.washingtonpost.com'

    driver = webdriver.Firefox()
    driver.get(url)
    driver.find_element(By.XPATH, '//*[@data-testid="sc-header-sections-menu-button"]').click()
    
    sec = driver.find_element(By.ID, 'sc-sections-nav-drawer')
    l = sec.find_elements(By.XPATH, "//*[starts-with(@id, '/')]")
    
    sector_dict = {}
    actions = ActionChains(driver)

    # Collecting sector URLs
    for i in l:
        dropdown_trigger = i.find_element(By.TAG_NAME, 'div')
        actions.move_to_element(dropdown_trigger).perform()  # Hover over the element to trigger the dropdown
        
        test = driver.find_elements(By.TAG_NAME, 'ul')
        t = test[len(test) - 1].find_elements(By.TAG_NAME, 'li')
        
        for j in t:
            try:
                # Use a retry mechanism to handle stale elements
                sector_url = get_element_with_retry(driver, By.TAG_NAME, 'a').get_attribute('href')
                txt = j.find_element(By.TAG_NAME, 'a').text
                main = i.find_element(By.TAG_NAME, 'a').text.replace("+", " ")
                subcat = f"{main}/{txt}"
                sector_dict[subcat] = sector_url
            except StaleElementReferenceException:
                print("Stale element detected. Retrying...")

        driver.execute_script("arguments[0].scrollTop += 85;", sec)

    driver.quit()

    # Collect all data in a list
    all_data = []

    # Navigate into each sector and collect articles
    for s in sector_dict:
        driver = webdriver.Firefox()
        driver.get(sector_dict[s])
        print("~~~~~~~~~")
        print(s)

        for i in range(8):
            driver.execute_script("window.scrollTo(0, window.pageYOffset + 700);")
            time.sleep(0.3)

            # Re-fetch elements after scrolling
            elements = driver.find_elements(By.CSS_SELECTOR, '[data-feature-id="homepage/story"]')

            for ele in elements:
                text = ele.text.replace("\n", '')
                article_url = ele.find_element(By.TAG_NAME, 'a').get_attribute('href')

                if len(text) < 3 or article_url.count('-') < 3 or text.count(' ') < 3 or len(article_url) < 5:
                    continue
                
                keywords = extract_significant_words_from_title(text,nlp)
                date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                row_data = {
                    'Source': 'WAPO',
                    'Section': s,
                    'Section URL': sector_dict[s],
                    'Article Title': text,
                    'Article URL': article_url,
                    'Keywords': keywords,
                    'Date': date
                }
                all_data.append(row_data)

        driver.quit()

    # Append all data at once to the DataFrame
    for row in all_data:
        collector.append_data(row)


#===================================================================================
#       NYT
#===================================================================================
def nyt(collector,nlp):
    driver = webdriver.Firefox()
    driver.get('https://www.nytimes.com/')
    
    # Collect section URLs
    t = driver.find_elements(By.CSS_SELECTOR, '[data-testid^="nav-item-"]')
    sector_dict = {}
    for i in t:
        ele = i.find_element(By.TAG_NAME, 'a')
        url = ele.get_attribute('href')
        text = ele.text
        if 'nytimes.com/spotlight/' in url or text in ['', ' ', 'Games', 'Wirecutter', 'Cooking']:
            continue
        sector_dict[text] = url

    driver.quit()

    # Collect all data in a list
    all_data = []

    # Iterate through sectors
    for s in sector_dict:
        driver = webdriver.Firefox()
        driver.get(sector_dict[s])
        print("~~~~~~~~~")
        print(s)

        # Scroll to load more articles
        for i in range(8):
            driver.execute_script("window.scrollTo(0, window.pageYOffset + 700);")
            time.sleep(0.3)

        try:
            region = driver.find_element(By.CSS_SELECTOR, '[data-testid="asset-stream"]')
        except:
            driver.quit()
            continue

        print('len: ', len(region.find_elements(By.TAG_NAME, 'article')))

        for ele in region.find_elements(By.TAG_NAME, 'article'):
            lnkreg = ele.find_element(By.TAG_NAME, 'a')
            url = lnkreg.get_attribute('href')
            text = lnkreg.text.replace('\n', '')

            # Skip unwanted content
            stop_hls = [
                'contact us', 'your ad choices', 'terms of service', 'terms of sale', 
                '© 2024 the new york times company', 'skip to main content', 'skip to site index'
            ]
            if 'nytimes.com/' not in url or len(text) < 3 or text.count(' ') < 3 or text.lower() in stop_hls:
                continue

            try:
                date = ele.find_element(By.XPATH, '..').find_element(By.CSS_SELECTOR, '[data-testid="todays-date"]').text
            except:
                date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # If date not found, use current date

            print(date, text, url)
            
            # Extract keywords and collect data
            keywords = extract_significant_words_from_title(text,nlp)
            row_data = {
                'Source': 'NYT',
                'Section': s,
                'Section URL': sector_dict[s],
                'Article Title': text,
                'Article URL': url,
                'Keywords': keywords,
                'Date': date
            }
            all_data.append(row_data)

        driver.quit()

    # Append all data at once to the DataFrame
    for row in all_data:
        collector.append_data(row)


#===================================================================================
#   
#===================================================================================

def get_similar_articles_with_source_names(datasets, source_names,model):
    """
    Find similar articles across multiple datasets with emphasis on multi-source similarity.
    Avoid repetitions in the output and use source names instead of indices.
    
    Args:
        datasets (list of DataFrames): List of DataFrames where each DataFrame contains articles from a different source.
        source_names (list of str): List of source names corresponding to each DataFrame in datasets.
    
    Returns:
        list of tuples: Each tuple contains (weighted_similarity_score, [title1, title2, ...], [(index1, source1_name), (index2, source2_name), ...])
    """
    # Store all headlines and their embeddings in a dictionary
    embeddings_dict = {}
    
    for idx, df in enumerate(datasets):
        headline_list = df['Article Title'].tolist()
        embeddings = model.encode(headline_list)
        embeddings_dict[idx] = (headline_list, embeddings)

    # List to store aggregated results
    aggregated_results = []
    processed_pairs = set()
    used_articles = set()  # Track used articles

    # Iterate over all headlines in all datasets
    for i in range(len(datasets)):
        headlines1, embeddings1 = embeddings_dict[i]
        
        for k, title1 in enumerate(headlines1):
            if (k, source_names[i]) in used_articles:
                continue  # Skip if already used in a high-scoring match

            # Initialize variables to aggregate similarity scores
            total_similarity_score = 0
            num_sources_matched = 0
            similar_titles = [title1]
            similar_indices = [(k, source_names[i])]
            
            # Compare against all other datasets
            for j in range(len(datasets)):
                if i == j:
                    continue  # Skip comparison with itself

                headlines2, embeddings2 = embeddings_dict[j]
                
                # Compute cosine similarity between the current headline and all headlines in the other dataset
                cosine_matrix = cosine_similarity([embeddings1[k]], embeddings2)[0]
                
                # Find the most similar headline in the other dataset
                max_sim_index = np.argmax(cosine_matrix)
                max_similarity = cosine_matrix[max_sim_index]
                
                # If similarity is above a threshold, consider it a match
                if max_similarity >= 0.52:  # Threshold to consider as a match
                    pair = tuple(sorted([(k, i), (max_sim_index, j)]))  # Sort to avoid ordering issues
                    if pair in processed_pairs or (max_sim_index, source_names[j]) in used_articles:
                        continue  # Skip if this pair has already been processed or article is already used
                    processed_pairs.add(pair)

                    total_similarity_score += max_similarity
                    num_sources_matched += 1
                    similar_titles.append(headlines2[max_sim_index])
                    similar_indices.append((max_sim_index, source_names[j]))
            
            # Calculate weighted similarity score
            weighted_similarity_score = total_similarity_score * (num_sources_matched / len(datasets))
            
            # Store result if there is at least one match (i.e., num_sources_matched > 1)
            if num_sources_matched > 1:  # Ensure at least one other source matches
                aggregated_results.append((weighted_similarity_score, similar_titles, similar_indices))
                # Mark all articles in the current match as used
                used_articles.update(similar_indices)
    
    # Sort results by weighted similarity score in descending order
    aggregated_results.sort(reverse=True, key=lambda x: x[0])

    return aggregated_results

#===================================================================================
#
#===================================================================================
def get_sim_article_df(similar_articles_across_sources,data):
    similar_articles_df = pd.DataFrame(columns=['Article Headlines','Article URLs','Keywords','Similarity Weights'])
    for i in range(len(similar_articles_across_sources)):
        titles = similar_articles_across_sources[i][1]
        #print(similar_articles_across_sources[i])
            # Extract processed titles
        processed_titles = find_common_significant_words(titles)
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(processed_titles)

        feature_names = vectorizer.get_feature_names_out()
        tfidf_scores = tfidf_matrix.sum(axis=0).A1  # Sum across all documents for global score

        tfidf_ranking = list(zip(feature_names, tfidf_scores))
        tfidf_ranking = sorted(tfidf_ranking, key=lambda x: x[1], reverse=True)

        keywords = [word for word, score in tfidf_ranking if score > 0]
        urls = []
        for k in similar_articles_across_sources[i][2]:
            urls.append(data[data['Source'] == k[1]].iloc[k[0]]['Article URL'])

        #print(keywords)
        #print(urls)
        similar_articles_df.loc[len(similar_articles_df)] = [titles,urls,keywords,similar_articles_across_sources[i][0]]
    return similar_articles_df


def main():
    nlp = spacy.load('en_core_web_sm')
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    foxnews(collector,nlp)
    cnn(collector,nlp)
    wapo(collector,nlp)
    nyt(collector,nlp)

    data = collector.get_dataframe()
    CNN = data[data['Source'] == 'CNN']
    FOX = data[data['Source'] == 'FOX']
    WAPO = data[data['Source'] == 'WAPO']
    NYT = data[data['Source'] == 'NYT']

    datasets = [CNN, FOX, WAPO, NYT]
    source_names = ['CNN', 'FOX', 'WAPO', 'NYT']
    similar_articles_across_sources = get_similar_articles_with_source_names(datasets, source_names,model)
    similar_articles_df = get_sim_article_df(similar_articles_across_sources,data)

    print(similar_articles_df)
    print("=========================")
    print(collector.get_dataframe())
    print(type(similar_articles_df))

if __name__ == "__main__":
    main()