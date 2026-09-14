# Cross-Outlet News Clustering & Multi-Document Summarization

**Solo project · Sept 2024 – 2025**
**Stack:** Python · Selenium · spaCy · KeyBERT · Sentence-Transformers · scikit-learn (DBSCAN) · Hugging Face Transformers (PRIMERA) · PostgreSQL on AWS RDS · AWS EC2 / S3 / Lambda · Node.js/Express · React · Render

---

## Short version

An end-to-end ML system that scrapes eight major U.S. news outlets every day and finds articles from different outlets that cover the same story. For each story, it reads the full text of every article and writes one abstractive summary with a GPU-hosted transformer. The results are served through a web app. Each card is one story and shows which outlets covered it, the story's keywords, and its summary.

---

## The problem

A single event gets covered by Fox, CNN, AP, NPR, the New York Times and others, each with its own headline and framing. To see the full picture, a reader has to find and read every version. I wanted a system that could:

1. **Detect** when articles from different outlets are about the same event, with no labels and headlines that rarely share wording.
2. **Summarize** the full coverage of that event into one readable paragraph.
3. **Run on its own every day** at low cost.

This is an unsupervised problem. New stories appear daily, there's no fixed set of topics, and the number of clusters is unknown ahead of time.

---

## System overview

```
 8 news sites ──► Scrapers (EC2) ──► Keyword extraction ──► Embeddings + clustering ──► Postgres (RDS)
                                                                                                  │
                     Full-text fetch for clustered articles ──► S3 ──► Lambda starts GPU EC2 ◄────┘
                                                                              │
                                             PRIMERA summaries ──► S3 ──► Postgres ──► Express API ──► React
```

---

## 1. Data collection

- I wrote **custom Selenium scrapers for 8 outlets**: AP, CBS, CNN, Fox, HuffPost, NPR, NYT and the Washington Post. The scrapers run **in parallel**, with one headless browser per outlet on its own thread.
- Each scraper finds the outlet's sections from its navigation menu, then works through each section. It handles infinite scroll (with a stopping rule and a scroll cap), dismisses modal and iframe pop-ups, and filters out video, audio and quiz content.
- Each outlet formats dates differently ("3h ago", "JAN 06", "Oct. 9, 2024"), so the scrapers convert them all to one format.
- For articles that end up in a story cluster, a second pass pulls the **full article body** with a text reader written for each outlet's page layout. The NYT and the Washington Post are paywalled, so they count toward clustering but not toward summaries.
- Duplicates are removed by exact URL and by URL containment, since the same article often appears under several section paths.

## 2. Keyword extraction: a weighted ensemble

Each single method was noisy on short headlines, so I combined four signals and scored every candidate keyword by weighted vote:

| Signal | What it catches | Weight |
|---|---|---|
| spaCy **named-entity recognition** (numeric, date and money entities excluded) | People, places, organizations | 2.0 |
| **KeyBERT** (embedding-based) | Phrases that carry the headline's meaning | 0–2.0 (confidence rescaled to match the other weights) |
| Curated **domain vocabulary** (about 100 news terms: countries, institutions, recurring topics) | High-value terms the models miss | 1.1 |
| spaCy **part-of-speech** filter (lemmatized nouns and proper nouns) | General content words | 1.0 |

A candidate is kept only if its combined score is above 1. That means a keyword needs either a strong single signal (such as a named entity) or agreement between weaker ones. The keywords feed into clustering and also power keyword browsing in the app.

## 3. Story clustering

The central problem is deciding which articles are about the same story.

1. **Embed** every headline with a Sentence-Transformer model and compute the pairwise **cosine similarity** matrix.
2. **Adjust similarities with domain priors** before clustering:
   - **+0.1 if the two articles come from different outlets, −0.5 if they come from the same one.** Without this, one outlet's near-duplicate headlines (updates, cross-posts between sections) formed single-outlet clusters, which isn't what the product is for.
   - **+0.033 for each shared keyword**, so agreement on entities and topics adds evidence beyond semantic similarity.
3. Clip the adjusted scores to [0, 1] and run **DBSCAN on the precomputed distance matrix** (1 − similarity), with `eps = 0.1` (similarity ≥ 0.9) and `min_samples = 2`.
   - I chose DBSCAN because the number of stories changes every day, so there's no *k* to pick. Its noise label also handles stories only one outlet covered, which are simply left out.
4. For each cluster, compute a **cohesion score** (mean within-cluster similarity) and a **shared keyword set** (the keywords common to every article in the cluster).

The app only shows clusters with cohesion ≥ 0.8 that include at least one article from the last 48 hours.

## 4. Multi-document summarization: a model comparison

I built and compared two approaches in a notebook before choosing one for the pipeline.

**Preprocessing (both approaches):** drop empty or failed scrapes, strip leftover markup characters, remove exact duplicates (case-insensitive) and near-duplicates (RapidFuzz ratio > 85, keeping the longer text), and drop clusters left with fewer than 2 usable articles.

**Approach 1: centroid-based extractive summarization.** This reimplements the MEAD centroid method from Radev et al. (2000).
- I fit a TF-IDF vectorizer on the article corpus and saved it with joblib. Each cluster's centroid is the mean TF-IDF vector of its articles.
- Every sentence is scored by cosine similarity to the centroid. Top sentences are selected greedily, with a redundancy filter that rejects any sentence with similarity ≥ 0.7 to one already chosen. The chosen sentences are then put back in their original order.

**Approach 2: PRIMERA abstractive summarization.** PRIMERA is a Longformer encoder-decoder that was pretrained specifically for multi-document summarization.
- The cluster's articles are joined with `<doc-sep>` tokens and truncated to 2,048 input tokens. The model generates with beam search (6 beams, length penalty 2.0, 50–200 output tokens) on CUDA.

**Evaluation.** There are no reference summaries for daily news, so I used two checks: ROUGE-2 precision and recall of each summary against the combined source articles, and a manual side-by-side review of sample clusters. I noted the limitation up front: ROUGE against the sources measures overlap, not quality.

**Result.** ROUGE-2 scores were similar for both approaches, and both picked out the same core facts. The difference showed up in the manual review:
- The extractive summaries were choppy and repetitive.
- Because the extractive method copies sentences as-is, it also copied scraping noise: photo captions, "Getty Images" credits, and all-caps promo headlines embedded in article bodies.
- PRIMERA wrote coherent, readable prose.

Approach 1 was much faster, but latency didn't matter for a daily batch job, so **I shipped PRIMERA**.

## 5. Pipeline & infrastructure

The pipeline uses **two EC2 instances** so the GPU is only billed while summaries are being generated:

- **Instance 1 (CPU)** handles scraping, keyword extraction, clustering, the database load and the full-text fetch. It writes the unsummarized cluster text to **S3** along with a status flag, then calls an **AWS Lambda** function that starts the GPU instance.
- **Instance 2 (GPU)** reads the text from S3, runs PRIMERA, writes the summaries and a completion flag back to S3, and **shuts itself down**.
- Instance 1 polls for the completion flag, loads the summaries into Postgres, and **shuts itself down**.

**Data model (PostgreSQL on RDS):**
- The Python jobs bulk-insert into **staging tables**. One transactional SQL script then normalizes the data into `articles`, `keywords`, `similar_articles` (the clusters), junction tables (article↔keyword, cluster↔article, cluster↔keyword), `article_text` and `similar_article_summaries`.
- Every insert uses `ON CONFLICT DO NOTHING`, so rerunning a day's job is safe. The staging tables are truncated at the end of the transaction.

## 6. Serving

- **Express API:**
  - A feed endpoint returns recent, cohesive clusters with their articles and keywords, and fetches their summaries in one batched query.
  - A keyword endpoint returns every article tagged with a given keyword.
- **React front end (deployed on Render):**
  - Each story card shows a representative headline and image (the shortest headline that has a valid image) plus an "As covered by" list linking to each outlet.
  - Clicking a card opens the full list of articles, the summary, and clickable keyword tags that link to that keyword's article history.

---

## What I'd improve next

- **Measure clustering quality instead of hand-tuning it.** The threshold and prior weights were tuned by inspection. The next step is to label a few hundred headline pairs, report pairwise precision and recall (or B-cubed), and grid-search `eps` and the priors.
- **Link clusters across days.** Each run clusters its own batch, so a story that lasts several days gets a new cluster every day. Matching new articles against existing cluster centroids would fix that.
- **Evaluate summary faithfulness.** ROUGE against the sources doesn't catch hallucinations. I'd add an NLI-based consistency check (e.g., SummaC) or an LLM judge. I'd also split the 2,048-token budget across articles, so the ones at the end of the input aren't truncated away.
- **Harden the pipeline.** I'd replace S3 flag polling with Step Functions or Airflow, add retries, and track article counts per outlet so a scraper broken by a site redesign gets flagged instead of failing silently.
- **Scale the similarity step.** The pairwise prior adjustments run in an O(n²) Python loop. Vectorizing them, or using an approximate nearest-neighbor index, would handle much larger daily volumes.
