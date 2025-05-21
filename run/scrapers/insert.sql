BEGIN;

-- Clean up data
UPDATE raw_articles
SET article_keywords = TRIM(
    REGEXP_REPLACE(
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(article_keywords, '\[|\]', '', 'g'),
                '"', '', 'g'
            ),
            '''', '', 'g'
        ),
        '\s*,\s*', ',', 'g'
    )
);

-- Insert into Articles
INSERT INTO articles (article_id, title, url, date, article_section, section_url, article_source, image, subheading)
SELECT article_id, title, url, date, article_section, section_url, article_source, image, subheading
FROM raw_articles
ON CONFLICT(url) DO NOTHING;

-- Insert into Keywords
WITH split_keywords AS (
    SELECT DISTINCT unnest(string_to_array(article_keywords, ',')) AS keyword
    FROM raw_articles
)
INSERT INTO keywords (keyword)
SELECT keyword
FROM split_keywords
ON CONFLICT (keyword) DO NOTHING;

-- Insert into junct_article_keywords
INSERT INTO junct_article_keywords (article_id, keyword_id)
SELECT a.article_id AS article_id, k.keyword_id
FROM articles a
JOIN raw_articles ra ON a.url = ra.url
JOIN keywords k ON k.keyword = ANY(string_to_array(ra.article_keywords, ','))
ON CONFLICT (article_id, keyword_id) DO NOTHING;

-- Create a temporary table to hold split URLs and keywords
CREATE TEMP TABLE temp_split_urls AS
SELECT 
    simart_id,
    unnest(string_to_array(article_urls, '|||')) AS url
FROM raw_similar_articles;

-- tmp tbl for keywords
CREATE TEMP TABLE temp_split_keywords AS
SELECT
	simart_id,
	unnest(string_to_array(REGEXP_REPLACE(keywords, '\[|\]|''', '', 'g'), ',')) AS similar_keywords
FROM raw_similar_articles;

-- Insert into similar_articles
INSERT INTO similar_articles (simart_id, similar_weight)
SELECT simart_id, similar_weight
FROM raw_similar_articles
ON CONFLICT (simart_id) DO NOTHING;

-- Insert into junct_simart_articles
INSERT INTO junct_simart_articles (article_id, simart_id)
SELECT a.article_id, tsu.simart_id
FROM temp_split_urls tsu
JOIN articles a ON a.url = tsu.url
ON CONFLICT (article_id, simart_id) DO NOTHING;

-- Insert into junct_simart_keywords
INSERT INTO junct_simart_keywords (simart_id, keyword_id)
SELECT tsk.simart_id, kw.keyword_id
FROM temp_split_keywords tsk
JOIN keywords kw ON TRIM(LOWER(kw.keyword)) = TRIM(LOWER(tsk.similar_keywords))
ON CONFLICT (simart_id, keyword_id) DO NOTHING;

-- Drop temporary table
DROP TABLE IF EXISTS temp_split_urls;
DROP TABLE IF EXISTS temp_split_keywords;

-- Empty raw tables
TRUNCATE TABLE raw_articles;
TRUNCATE TABLE raw_similar_articles;

COMMIT;