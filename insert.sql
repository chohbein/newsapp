--					This script will insert data into the relational database
--					Taking in raw_articles and raw_similar_articles, then clearing them.
BEGIN;
--			Insert keywords from raw_articles
WITH split_keywords AS (
    SELECT DISTINCT unnest(string_to_array(article_keywords, ',')) AS keyword
    FROM raw_articles
)
Insert into keywords (keyword)
	SELECT keyword
	FROM split_keywords
	ON CONFLICT (keyword) DO NOTHING;


--			Insert articles from raw_articles
INSERT INTO articles (title,url,date,article_section,section_url,article_source)
	SELECT title,url,date,article_section,section_url,article_source
	FROM raw_articles
	ON CONFLICT (url) DO NOTHING;

--			Insert junct_article_keywords from articles,keywords,raw_articles
-- Insert junct_article_keywords from articles, keywords, raw_articles
INSERT INTO junct_article_keywords (article_id, keyword_id)
	SELECT a.article_id, k.keyword_id
	FROM articles a
	JOIN raw_articles ra ON a.url = ra.url
	JOIN keywords k ON k.keyword = ANY(string_to_array(ra.article_keywords, ','))
	LEFT JOIN junct_article_keywords jak ON jak.article_id = a.article_id AND jak.keyword_id = k.keyword_id
	WHERE jak.article_id IS NULL;  -- This ensures only new entries are inserted

--			Handling raw_similar_articles
WITH grouped_articles AS (
    -- Step 1: Split article_urls and generate a unique group_id for each group
    SELECT 
        unnest(string_to_array(article_urls, '|||')) AS article_url,
        unnest(string_to_array(keywords, '|||')) AS keyword,  -- Unnest keywords
        similar_weight,
        DENSE_RANK() OVER (ORDER BY similar_weight, article_urls) AS group_id
    FROM raw_similar_articles
),
sim AS (
    -- Step 2: Insert one row per group into similar_articles and return simart_id
    INSERT INTO similar_articles (similar_weight)
    SELECT DISTINCT similar_weight
    FROM grouped_articles
    RETURNING simart_id, similar_weight
),
keywords_insert AS (
    -- Step 3: Insert keywords into the keywords table and get their keyword_id
    INSERT INTO keywords (keyword)
    SELECT DISTINCT keyword
    FROM grouped_articles
    ON CONFLICT (keyword) DO NOTHING
    RETURNING keyword_id, keyword
),
-- Insert both junct_simart_articles and simart_keywords in one query block
combined_insert AS (
    -- Insert into junct_simart_articles
    INSERT INTO junct_simart_articles (article_id, simart_id)
    SELECT a.article_id, s.simart_id
    FROM articles a
    JOIN grouped_articles ga ON a.url = ga.article_url
    JOIN sim s ON ga.similar_weight = s.similar_weight
)
-- Now insert into simart_keywords to link simart_id with keyword_id
INSERT INTO simart_keywords (simart_id, keyword_id)
SELECT s.simart_id, k.keyword_id
FROM grouped_articles ga
JOIN sim s ON ga.similar_weight = s.similar_weight
JOIN keywords_insert k ON ga.keyword = k.keyword;

--DELETE FROM raw_similar_articles;
--DELETE FROM raw_articles;
COMMIT;