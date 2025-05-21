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
from datetime import datetime, timedelta, date

import re
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

#===================================================================================
#   Helper Functions
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

def get_img(row):
    url = row['Article URL']
    source = row['Source']
    if source == 'FOX':
        # Send a GET request to the URL
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        # Find all image tags
        images = soup.find_all('img')
        
        # Loop through images and filter out ones starting with 'https://static.'
        for img in images[1:]:  # Skipping the first image (if necessary)
            image_url = img.get('src')
            if image_url and not image_url.startswith('https://static.'):
                return image_url

        # Return None if no valid image is found
        return None
    
    elif source == 'CNN':
        response = requests.get(url)
        soup = BeautifulSoup(response.content,'html.parser')

        images = soup.find_all('img')
        for img in images:
            image_url = img.get('src')
            if image_url and not 'face' in image_url and image_url.startswith('https://'):
                return image_url
        return None

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

def fox_popup_close(driver):
    try:
        WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, 'iframe[title="Modal Message"]')))
    except:
        pass
    try:
        ele = driver.find_element(By.XPATH, '//*[@aria-label="Close Message"]')

        ele.click()
    finally:
        return

def wapo_popup(driver):
    try:
        time.sleep(2)
        driver.find_element(By.CSS_SELECTOR,'[data-qa="close-button-container"]').click()
    except:
        return

def Find_if_available(driver,by,val):
    try:
        ele = driver.find_element(by,val)
        return ele
    except:
        return None

#   Clean date format, for Fox specifically 
def clean_fox_date(raw_date):
    if any(s in raw_date for s in ['day ago','days ago']):
        raw_date = int(raw_date.split(' ')[0])
        date = (datetime.today() - timedelta(days=raw_date)).strftime('%Y-%m-%d')
    elif any(s in raw_date for s in ['hour ago','hours ago']):
        raw_date = int(raw_date.split(' ')[0])
        date = (datetime.today() - timedelta(hours=raw_date)).strftime('%Y-%m-%d')
    elif any(s in raw_date for s in ['year ago','years ago']):
        raw_date - int(raw_date.split(' ')[0])
        date = (datetime.today() - timedelta(years=raw_date)).strftime('%Y-%m-%d')

    return date

#   Clean date formats, specifically for CBS
def clean_cbs_date(raw_date):
    raw_date = raw_date.lower()
    #   For dates with 'ago'
    if 'ago' in raw_date:
        if 'update' in raw_date:
            clean_date = raw_date.split()[1]
        else:
            clean_date = raw_date.split()[0]

        currdate = datetime.now()

        if 'h' in clean_date:
            hours = int(clean_date.replace('h',''))
            clean_date = currdate - timedelta(hours=hours)

        elif 'm' in clean_date:
            mins = int(clean_date.replace('m',''))
            clean_date = currdate - timedelta(minutes=mins)
        
        elif 'd' in clean_date:
            days = int(clean_date.replace('d',''))
            clean_date = currdate - timedelta(days=days)

        clean_date = clean_date.strftime("%Y-%m-%d %H:%M:%S")

    #   For dates of form 'JAN 06'
    else:
        raw_date = f'{raw_date} {datetime.now().year}'
        clean_date = datetime.strptime(raw_date, "%b %d %Y")

    return clean_date

def clean_nyt_date(raw_date):
    if 'ago' in raw_date.lower():
        if any(s in raw_date for s in ['m ']):
            raw_date = raw_date.split(' ')[0]
            raw_date = int(''.join(re.findall(r'\d', raw_date)))
            date = (datetime.today() - timedelta(minutes=raw_date)).strftime('%Y-%m-%d')
        elif any(s in raw_date for s in ['d ']):
            raw_date = raw_date.split(' ')[0]
            raw_date = int(''.join(re.findall(r'\d', raw_date)))
            date = (datetime.today() - timedelta(days=raw_date)).strftime('%Y-%m-%d')
        elif any(s in raw_date for s in ['h ']):
            raw_date = raw_date.split(' ')[0]
            raw_date = int(''.join(re.findall(r'\d', raw_date)))
            date = (datetime.today() - timedelta(hours=raw_date)).strftime('%Y-%m-%d')
    else:
        if ',' in raw_date:
            if '.' in raw_date:
                date = datetime.strptime(raw_date, '%b. %d, %Y').strftime('%Y-%m-%d')
            else:
                date = datetime.strptime(raw_date, '%B %d, %Y').strftime('%Y-%m-%d')
        else:
            if '.' in raw_date:
                date = datetime.strptime(raw_date, '%b. %d %Y').strftime('%Y-%m-%d')
            else:
                date = datetime.strptime(raw_date, '%B %d %Y').strftime('%Y-%m-%d')

    
    return date

#===================================================================================
#   News Site Scraping
#===================================================================================
#       Fox
#===================================================================================
def foxnews(collector):
    url = 'https://www.foxnews.com/'

    options = Options()
    options.add_argument('-headless')
    driver = webdriver.Firefox(options=options)
    driver.fullscreen_window()
    driver.get(url)
    try:
        driver.find_element(By.CLASS_NAME,'js-menu-toggle').click()
    except:
        fox_popup_close(driver)
        driver.switch_to.default_content()
        time.sleep(2)
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
    
    # Collect all data in a list
    all_data = []

    # Into Sector Dicts
    for s in sector_dict:
        driver.get(sector_dict[s])

        # Scroll to load more articles
        for i in range(8):
            driver.execute_script("window.scrollTo(0, window.pageYOffset + 700);")
            time.sleep(0.3)

        # Extract article data
        for ele in driver.find_elements(By.TAG_NAME,'article'):
            url = ele.find_element(By.TAG_NAME,'a').get_attribute('href')
            try:
                txtloc = ele.find_elements(By.TAG_NAME,'a')
                text = txtloc[2].text
            except:
                for i in txtloc:
                    if i.text == '':
                        continue
                    text = i.text
                    break
            # Try/Catch for url is null
            # Ignore video pulls, along with these dumb 'quiz' things.
            try:
                if url.startswith('https://www.foxnews.com/video') or 'quiz' in text.lower() or 'political cartoons of the day' in text.lower():
                    continue
            except:
                continue

            try:
                img = ele.find_element(By.TAG_NAME,'img').get_attribute('src')
            except:
                row_data = {
                    'Source': 'FOX',
                    'Section': s,
                    'Section URL': sector_dict[s],
                    'Article Title': text,
                    'Article URL': url,
                    'Date': date,
                }
                try:
                    img = get_img(row_data)
                except:
                    img = None

            # Get date
            try:
                raw_date = ele.find_element(By.CLASS_NAME, 'time').text
                date = clean_fox_date(raw_date)
            except:
                date = datetime.today().strftime('%Y-%m-%d')
            
            # Collect the row data in a dictionary
            row_data = {
                'Source': 'FOX',
                'Section': s,
                'Section URL': sector_dict[s],
                'Article Title': text,
                'Article URL': url,
                'Date': date,
                'Image': img,
                'Subheading': None
            }
            all_data.append(row_data)

    driver.quit()

    # Append all data at once to the DataFrame
    for row in all_data:
        collector.append_data(row)
    
    return True

#===================================================================================
#       CNN
#===================================================================================
def cnn(collector):
    url = 'https://www.cnn.com/'

    options = Options()
    options.add_argument('-headless')
    driver = webdriver.Firefox(options=options)
    driver.fullscreen_window()
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
        options = Options()
        options.add_argument('-headless')
        driver = webdriver.Firefox(options=options)
        driver.fullscreen_window()
        driver.get(sector_dict[s])

        # Scroll to load more articles
        for i in range(8):
            driver.execute_script("window.scrollTo(0, window.pageYOffset + 700);")
            time.sleep(0.3)

        # Extract article data
        for ele in driver.find_elements(By.XPATH, '//a[@href]'):
            text = ele.text
            url = ele.get_attribute('href')

            # Filter out unwanted URLs and titles
            if len(text) < 10 or url.count('-') < 3 or text.count(' ') < 2 or url in ['', ' '] or 'cnn.com/audio' in url:
                continue

            # Extract current date
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Collect the row data in a dictionary
            row_data = {
                'Source': 'CNN',
                'Section': s,
                'Section URL': sector_dict[s],
                'Article Title': text,
                'Article URL': url,
                'Date': date,
                'Subheading': None
            }
            try:
                img = get_img(row_data)
            except:
                img = None
            row_data['Image'] = img

            all_data.append(row_data)

        driver.quit()

    # Append all data at once to the DataFrame
    for row in all_data:
        collector.append_data(row)

    return True

#===================================================================================
#       WAPO
#===================================================================================    
def wapo(collector):
    url = 'https://www.washingtonpost.com'

    options = Options()
    options.add_argument('-headless')
    driver = webdriver.Firefox(options=options)
    driver.fullscreen_window()
    driver.get(url)
    wapo_popup(driver)
    driver.find_element(By.XPATH, '//*[@data-testid="sc-header-sections-menu-button"]').click()
    
    sec = driver.find_element(By.ID, 'sc-sections-nav-drawer')
    l = sec.find_elements(By.XPATH, "//*[starts-with(@id, '/')]")
    
    sector_dict = {}
    actions = ActionChains(driver)

    # Collecting sector URLs
    for i in l:
        try:
            dropdown_trigger = i.find_element(By.TAG_NAME, 'div')
            actions.move_to_element(dropdown_trigger).perform()  # Hover over the element to trigger the dropdown
            
            test = driver.find_elements(By.TAG_NAME, 'ul')
            t = test[len(test) - 1].find_elements(By.TAG_NAME, 'li')
            
            for j in t:
                try:
                    # Use a retry mechanism to handle stale elements
                    sector_url = get_element_with_retry(j, By.TAG_NAME, 'a').get_attribute('href')
                    txt = j.find_element(By.TAG_NAME, 'a').text
                    main = i.find_element(By.TAG_NAME, 'a').text.replace("+", " ")
                    subcat = f"{main}/{txt}"
                    sector_dict[subcat] = sector_url
                except StaleElementReferenceException:
                    print("Stale element detected.")

            driver.execute_script("arguments[0].scrollTop += 85;", sec)
        except:
            driver.execute_script("arguments[0].scrollTop += 85;", sec)

    # Collect all data in a list
    all_data = []
    # Navigate into each sector and collect articles
    for s in sector_dict:
        driver.get(sector_dict[s])

        for i in range(8):
            driver.execute_script("window.scrollTo(0, window.pageYOffset + 700);")
            time.sleep(0.3)

        # Re-fetch elements after scrolling
        elements = driver.find_elements(By.CSS_SELECTOR, '[data-feature-id="homepage/story"]')
        for ele in elements:
            try:
                text = ele.find_element(By.CSS_SELECTOR,'[data-qa="card-title"]').text.replace("\n", '')
                article_url = ele.find_element(By.TAG_NAME, 'a').get_attribute('href')
                if not text or len(text) < 3:
                    continue
            except:
                continue

            if len(text) < 3 or article_url.count('-') < 3 or text.count(' ') < 3 or len(article_url) < 5:
                continue

            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            #   Get image and subheading (if available)
            try:
                image = ele.find_element(By.TAG_NAME,'img').get_attribute('src')
            except:
                image = None
            try:
                subheading = ele.find_element(By.TAG_NAME,'p').text
            except:
                subheading = None

            row_data = {
                'Source': 'WAPO',
                'Section': s,
                'Section URL': sector_dict[s],
                'Article Title': text,
                'Article URL': article_url,
                'Date': date,
                'Image': image,
                'Subheading': subheading
            }
            all_data.append(row_data)

    driver.quit()

    # Append all data at once to the DataFrame
    for row in all_data:
        collector.append_data(row)

    return True
#===================================================================================
#       NYT
#===================================================================================
def nyt(collector):
    options = Options()
    options.add_argument('-headless')
    driver = webdriver.Firefox(options=options)
    driver.fullscreen_window()
    driver.get('https://www.nytimes.com/')

    all_data = []
    viewport_height = driver.execute_script("return window.innerHeight;")

    # Collect section URLs
    t = driver.find_elements(By.CSS_SELECTOR, '[data-testid^="nav-item-"]')
    sector_dict = {}
    for i in t:
        ele = i.find_element(By.TAG_NAME, 'a')
        url = ele.get_attribute('href')
        text = ele.text
        if 'nytimes.com/spotlight/' in url or text in ['', ' ', 'Games', 'Wirecutter', 'Cooking','Athletic']:
            continue
        sector_dict[text] = url

    visited_urls = set()
    # Iterate through sectors
    for s in sector_dict:
        driver.get(sector_dict[s])

        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            #   Check for popup and close
            try:
                button = driver.find_element(By.XPATH,"//div[@role='alertdialog']//button")
                button.click()
            except:
                pass
            
            #   Into visible articles
            article_reg = driver.find_elements(By.TAG_NAME,'article')
            for a in article_reg:
                b = a.find_element(By.TAG_NAME,'a')
                url = b.get_attribute('href')
                title = b.text
                if url in visited_urls or title.count(' ') <= 2:
                    continue
                visited_urls.add(url)
                try:
                    subheader = a.find_element(By.TAG_NAME,'p').text
                except:
                    subheader = None
                try:
                    img = a.find_element(By.TAG_NAME,'img').get_attribute('src')
                except:
                    img = None
                try:
                    parent = driver.execute_script("return arguments[0].parentNode;", a)
                    date = parent.find_element(By.CSS_SELECTOR, '[data-testid="todays-date"]').text
                    date = clean_nyt_date(date)
                except:
                    date = datetime.today().strftime('%Y-%m-%d')
                
                row_data = {
                    'Source': 'NYT',
                    'Section': s,
                    'Section URL': sector_dict[s],
                    'Article Title': title,
                    'Article URL': url,
                    'Date': date,
                    'Image': img,
                    'Subheading': subheader
                }
                all_data.append(row_data)

            driver.execute_script(f"window.scrollBy(0, {viewport_height});")
            new_height = driver.execute_script("return window.scrollY;")

            if last_height == new_height or new_height >= 20000:    #   Set an arb. 20k limit on scroll. (infinite scroll, seems like ~3 days worth in high pop sections)
                break
            last_height = new_height

    driver.quit()
    # Append all data at once to the DataFrame
    for row in all_data:
        collector.append_data(row)

    return True
#===================================================================================
#       AP News
#===================================================================================
def ap(collector):
    all_data = []

    #   Get Sections
    options = Options()
    options.add_argument('-headless')
    driver = webdriver.Firefox(options=options)
    driver.get('https://apnews.com/')
    driver.fullscreen_window()

    #       Get Sections
    sector_dict = {}

    #   Sect dropdown
    driver.find_element(By.CSS_SELECTOR,'.Page-header-menu-trigger.desktop-icon').click()
    t = driver.find_elements(By.CLASS_NAME,'AnClick-Hamburger-NavItem')
    for i in t:
        sector_dict[i.text] = i.get_attribute('href')
        if 'religion' in i.text.lower():
            break

    #   Get Articles
    collected_urls = set() #Set of urls to check for duplicates. Approach to scrolling is pulling lots of duplicates
    for sect in sector_dict:
        section = sect
        section_url = sector_dict[sect]
        
        # Get items from page
        driver.get(section_url)
        driver.fullscreen_window()
        #   Check for popup,close
        wait = WebDriverWait(driver, 5)
        try:
            e = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".bcpNotificationBarClose.bcpNotificationBarCloseIcon.bcpNotificationBarCloseTopRight")))
            e.click()
        except:
            pass
        
        last_height = driver.execute_script("return document.body.scrollHeight")
        end_of_page_checker = 0
        while end_of_page_checker < 3:
            item_segments = driver.find_elements(By.CLASS_NAME,'PageList-items')
            for segment in range(len(item_segments)):
                #   Skip first 2 segments; it's just the header section
                if segment == 0 or segment == 1:
                    continue
                seg = item_segments[segment]
                items = seg.find_elements(By.CLASS_NAME,'PageList-items-item')
                for i in items:
                    img = Find_if_available(i,By.TAG_NAME,'source')
                    img = img.get_attribute('srcset') if img is not None else None
                    #   If no titles or link, skip dat shit
                    try:
                        titles = i.find_elements(By.CLASS_NAME,'PagePromoContentIcons-text')
                        header = titles[0].text
                        url = i.find_element(By.TAG_NAME,'a').get_attribute('href')
                    except:
                        continue
                    #   Subheader if available
                    try:
                        subheader = titles[1].text
                    except:
                        subheader = None
                    if subheader != None and subheader.replace(' ','') == '':
                        subheader = None

                    if header.replace(' ','') == '': # empty title
                        continue

                    row_data = {
                        'Source': 'AP',
                        'Section': sect,
                        'Section URL': sector_dict[sect],
                        'Article Title': header,
                        'Article URL': url,
                        'Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # Date scraped... No published dates on main pages
                        'Image': img,
                        'Subheading': subheader
                    }
                    if url not in collected_urls:
                        collected_urls.add(url)
                        all_data.append(row_data)
            driver.execute_script("window.scrollBy(0, 2000);")
            new_height = driver.execute_script("return window.scrollY;")
            if last_height == new_height:
                end_of_page_checker += 1
            last_height = new_height
    driver.quit()
    for row in all_data:
        collector.append_data(row)

    return True

#===================================================================================
#       NPR
#===================================================================================
def npr(collector):
    #   Initialize
    all_data = []

    #   Get Sections
    options = Options()
    options.add_argument('-headless')
    driver = webdriver.Firefox(options=options)
    driver.get('https://www.npr.org/sections/news/')
    driver.fullscreen_window()
    sec_area = driver.find_element(By.CSS_SELECTOR,'.animated.fadeInRight')
    sections = sec_area.find_elements(By.TAG_NAME,'li')
    section_dict = {}
    for s in sections:
        a = s.find_element(By.TAG_NAME,'a')
        section = a.text
        section_url = a.get_attribute('href')
        # Skip 'codeswitch' (audio articles)
        if 'codeswitch' in section_url.lower():
            continue
        section_dict[section] = section_url

    #   Go into section
    for s in section_dict:
        driver.get(section_dict[s])
        last_height = driver.execute_script("return document.body.scrollHeight")
        collected_urls = set()
        while True:
            #   Check for popup
            try:
                iframe = driver.find_element(By.CSS_SELECTOR,'.tp-iframe-wrapper.tp-active').find_element(By.TAG_NAME,'iframe')
                driver.switch_to.frame(iframe)
                driver.find_element(By.CLASS_NAME,'pn-modal__close').click()
                driver.switch_to.default_content()
            except:
                pass
            eles = driver.find_elements(By.CSS_SELECTOR,'.item.has-image')
            
            for e in eles:
                header = e.find_element(By.CLASS_NAME,'title').find_element(By.TAG_NAME,'a')
                url = header.get_attribute('href')
                title = header.text

                subh_area = e.find_element(By.CLASS_NAME,'teaser')
                date = subh_area.find_element(By.TAG_NAME,'time').get_attribute('datetime')
                subheader = subh_area.find_element(By.TAG_NAME,'a').text.split('•',1)[-1].strip()

                img = e.find_element(By.TAG_NAME,'picture').find_element(By.TAG_NAME,'img').get_attribute('src')
                # check empty title
                if title.replace(" ",'') == '':
                    continue
                if url not in collected_urls:
                    collected_urls.add(url)


                    row_data = {
                            'Source': 'NPR',
                            'Section': s,
                            'Section URL': section_dict[s],
                            'Article Title': title,
                            'Article URL': url,
                            'Date': date,
                            'Image': img,
                            'Subheading': subheader
                        }
                    all_data.append(row_data)
            driver.execute_script("window.scrollBy(0, 2000);")
            new_height = driver.execute_script("return window.scrollY;")
            #   Can load more, not for now
            if last_height == new_height:
                break
            last_height = new_height
    driver.quit()
    for row in all_data:
        collector.append_data(row)

    return True

#===================================================================================
#       HuffPost
#===================================================================================
def huffpost(collector):
    all_data = []
    options = Options()
    options.add_argument('-headless')
    driver = webdriver.Firefox(options=options)
    driver.get('https://www.huffpost.com')
    driver.fullscreen_window()

    section_dict = {}
    dropdown = driver.find_element(By.XPATH, "//*[@aria-label='Open main menu']")
    dropdown.click()
    sec_area = driver.find_element(By.CLASS_NAME,'left-nav__menu')
    sects = sec_area.find_elements(By.TAG_NAME,'a')

    for s in sects:
        section = s.get_attribute('data-vars-item-name')
        section_url = s.get_attribute('href')
        #   Skip '2024 election'
        if '20' in section.lower() and 'election' in section.lower():
            continue
        if 'life' in section.lower():
            break
        section_dict[section] = section_url

    #   For scrolling
    viewport_height = driver.execute_script("return window.innerHeight")
    #   Into sections
    visited_urls = set()
    for s in section_dict:
        page_2_check = False
        driver.get(section_dict[s])
        #time.sleep(5)

        last_height = driver.execute_script("return document.body.scrollHeight")
        #for i in range(5):
            #driver.execute_script("window.scrollBy(0, 1000);")
        while True:
            items = driver.find_elements(By.CSS_SELECTOR,'.card.js-card')
            for i in items:
                try:
                    url = i.find_element(By.TAG_NAME,'a').get_attribute('href')
                except:
                    continue
                try:
                    title = i.find_element(By.CLASS_NAME,'card__headline__text').text
                    title = title.replace('Opinion:','').strip()
                except:
                    continue
                try:
                    img = i.find_element(By.TAG_NAME,'img').get_attribute('src')
                except:
                    img = None
                try:
                    subheader = i.find_element(By.CLASS_NAME,'card__description').text
                except:
                    subheader = None
                
                #   Check if article already recorded
                if url in visited_urls  or title.count(' ') < 3:
                    continue
                visited_urls.add(url)

                row_data = {
                            'Source': 'HuffPost',
                            'Section': s,
                            'Section URL': section_dict[s],
                            'Article Title': title,
                            'Article URL': url,
                            'Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # Date scraped... No published dates on main pages
                            'Image': img,
                            'Subheading': subheader
                        }
                all_data.append(row_data)

            driver.execute_script("window.scrollBy(0, 1000);")
            new_height = driver.execute_script("return window.scrollY;")
            if last_height == new_height:
                #   Try to get next page
                #       - Can edit to go through more pages, for now stick to 2
                #       - Some pages don't have 'next', rather 'show more'
                #           - These seem to be less useful sections, not 
                if not page_2_check:
                    try:
                        btn_next_page = driver.find_element(By.CLASS_NAME,'pagination__next-link')
                        btn_next_page.click()
                    except:
                        break
                    page_2_check = True
                    new_height = driver.execute_script("return window.scrollY;")
                else:
                    break
            last_height = new_height

    driver.quit()
    for row in all_data:
        collector.append_data(row)

    return True

#===================================================================================
#       CBS News
#===================================================================================
def cbs(collector):
    all_data = []

    options = Options()
    options.add_argument('-headless')
    driver = webdriver.Firefox(options=options)
    driver.get('https://www.cbsnews.com/')
    driver.fullscreen_window()

    #   Get sections

    # 1st in list of site-nav__item ('Latest' tab)
    hov_reg = driver.find_element(By.CLASS_NAME,'site-nav__item ')
    hover_ele = hov_reg.find_element(By.CLASS_NAME,'site-nav__item-title')
    hover = ActionChains(driver).move_to_element(hover_ele)
    hover.perform()

    sec_eles = hov_reg.find_elements(By.TAG_NAME,'li')

    section_dict = {}
    for s in sec_eles:
        sec_ele = s.find_element(By.TAG_NAME,'a')
        if 'sport' not in sec_ele.text.lower():
            section_dict[sec_ele.text] = sec_ele.get_attribute('href')

    #   Into Sections
    for s in section_dict:
        driver.get(section_dict[s])

        art_eles = driver.find_elements(By.TAG_NAME,'article')
        
        #   Into articles
        for art in art_eles:
            url = art.find_element(By.TAG_NAME,'a').get_attribute('href')
            title = art.find_element(By.CLASS_NAME,'item__hed ').text
            try:
                subheader = art.find_element(By.CLASS_NAME,'item__dek').text
            except:
                subheader = None

            try:
                img = art.find_element(By.TAG_NAME,'img').get_attribute('src')
            except:
                img = None
            
            try:
                raw_date = art.find_element(By.CLASS_NAME,'item__date').text
                date = clean_cbs_date(raw_date)
            except:
                raw_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            row_data = {
                        'Source': 'CBS',
                        'Section': s,
                        'Section URL': section_dict[s],
                        'Article Title': title,
                        'Article URL': url,
                        'Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # Date scraped... No published dates on main pages
                        'Image': img,
                        'Subheading': subheader
                    }
            all_data.append(row_data)
            
    driver.quit()
    for row in all_data:
        collector.append_data(row)

    return True
