# News Aggregator


## ML applications
### Summarizing Topics (For notebook, see <i>summary_extraction.ipynb</i>)
I created a system to automatically summarize multiple news articles about the same topic. It focuses on extracting key information from clusters of related news articles, (see next step for how that was done). \
I tested 2 different approaches to summarizing and ended up using the best one. See 'news_site_vid.mov' for a quick demo.
<br>
<br>
<br>
##### Approach 1: Centroid-Based Approach to Multi-Doc Summarizing (ref. https://aclanthology.org/W00-0403.pdf)
This paper, by Dragomir R. Radev et al., tackles the problem by highlighting a centroid-based approach to collecting the most important sentences among the cluster of articles. \
Briefly put, it works by applying a utility score to each sentence based on its relevance to the cluster, or the average topic of the articles, and eliminates redundancy by identifying when one sentence's information is subsumed by another. \
Steps:
1. Vectorize with TF-IDF
2. Calculated centroids to get the average representation of the group of articles.
3. Get cosine scores of each individual sentence to the centroid.
4. Redundant sentences identified by computing similarity scores among the chosen sentences, and eliminating those that exceed a threshold.

##### Approach 2: PRIMERA (Pyramid-based Masked Sentence Pre-Training for MDS)
PRIMERA is a leading model for multi-doc summarization. It uses a pre-trained method "Entity Pyramid" to identify important sentences by looking at frequency across articles and how representative they are. \
Steps:
1. Leveraged the pre-trained model from Hugging Face
2. Fine-tuned parameters for optimal length and quality
3. Build a pipeline to clean and process the data into the model.

##### Results
I elected to manually analyze the results to determine which approach was better. Both approaches produced similar resulting summaries; they both generally conveyed the same information, with alterations to which sentences were being used. \
However, PRIMERA's summaries were much smoother than approach 1. While the cluster-based approach did just as well at conveying the information, it's flow from sentence to sentence was often choppy and messy compared to PRIMERA. \

### Matching Similar Articles
1. I encoded article headlines using a transformer model. Unlike vectorizers like TF-IDF, which encodes words independently, Sentence-BERT captures contextual relationships and semantic meaning, which is helpful for our usage.
2. Then, I computed cosine similarity scores. This was better than other scores such as euclidian distance; cosine similarity computes the angle between 2 vectors which better captures semantic similarity. Euclidian distance, for example, is for lexical similarities.
3. Similarity scores are weighted; promoting diversity of sources and similar keywords, (see next).
4. Lastly, DBSCAN was used to cluster articles using their similarity scores between eachother, without any predefined number of clusters.

### Keyword Extraction
I used a combination of methods to create high-quality keywords for each article topic. 
1. Part-of-Speech Extraction with (spaCy) \
   Using spaCy's pretrained model, I lemmatized words to ensure relevance; focusing on nouns, proper nouns, and verbs. 
2. Named Entity Recognition (spaCy) \
   Identified named entities (organizations, people, locations, etc.), and filtered out generic tokens such as dates, values, percents. 
3. Semantically relevant words (KeyBERT) \
   Utilized their confidence score in the final weight calculation.
4. Custom Keyword Matching \
   Lastly, I put together a list of common buzzwords found in news headlines; regions, businesses, tech, political/legal, health, crime, social, and people. 

Finally, the extracted keywords were weighted based on their method and summed to produce the best keywords.



