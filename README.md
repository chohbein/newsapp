# News Aggregator


## ML applications
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

### Matching Similar Articles
1. I encoded article headlines using a transformer model. Unlike vectorizers like TF-IDF, which encodes words independently, Sentence-BERT captures contextual relationships and semantic meaning, which is helpful for our usage.
2. Then, I computed cosine similarity scores. This was better than other scores such as euclidian distance; cosine similarity computes the angle between 2 vectors which better captures semantic similarity. Euclidian distance, for example, is for lexical similarities.
3. Similarity scores are weighted; promoting diversity of sources and similar keywords.
4. Lastly, DBSCAN was used to cluster articles using their similarity scores between eachother, without any predefined number of clusters.
  
