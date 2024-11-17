from fastapi import FastAPI
from pymongo import MongoClient
from sklearn.pipeline import Pipeline
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.decomposition import PCA
from sklearn.cluster import DBSCAN
from sentence_transformers import SentenceTransformer
from sklearn.metrics import silhouette_score
from typing import List

# Initialize FastAPI
app = FastAPI()

# MongoDB connection
URI = "mongodb://localhost:27017/"
client = MongoClient(URI)
db = client['neutra_news_mid']
news_articles_collection = db['news_articles']
story_collection = db['stories']

# Define custom transformer
class EmbeddingTransformer(BaseEstimator, TransformerMixin):
    def _init_(self, model_name="all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
    
    def fit(self, X, y=None):
        return self
    
    def transform(self, X):
        return self.model.encode(X)

# Initialize pipeline
embeddingTransformer = EmbeddingTransformer()
pca = PCA(n_components=0.90)
dbscan = DBSCAN(eps=0.6, min_samples=2, n_jobs=-1)

pipeline = Pipeline([
    ('embedding', embeddingTransformer),
    ('pca', pca),
    ('dbscan', dbscan)
])

# Utility functions
def get_articles_grouped_by_date():
    aggregate_query = [
        {
        '$match': {'story_id': {'$exists': False} } #those who are not clustered
        },
        {
            '$group' : {
                '_id' : {
                    '$dateToString': {
                        'format': '%Y-%m-%d',  # Format the date to include only year, month, and day
                        'date': '$scraped_date'
                    }
                },
                'titles' : {'$push' : '$title'},
                'ids' : {'$push' : '$_id'}
            }
        },
        {
            '$sort': {'_id': 1}  # Sort by the formatted date in ascending order
        }
    ]
    aggregated_result = news_articles_collection.aggregate(aggregate_query)
    aggregated_result = list(aggregated_result)
    print(len(aggregated_result))
    return aggregated_result

def insert_story(title, date, blindspot=False):
    story = story_collection.insert_one({
        'title': title,
        'date': date,
        'blindspot': blindspot
    })
    return story.inserted_id

def update_article(_id, story_id, blindspot=False):
    news_articles_collection.update_one(
        {'_id': _id},
        {'$set': {'story_id': story_id, 'blindspot': blindspot}}
    )
    return _id

def get_story_headlines_map(articles_in_day):
    headlines_map = {}
    for article in articles_in_day:
        if article[2] == -1 or article[2] in headlines_map:
            continue
        else:
            headlines_map[article[2]] = article[1]
    return headlines_map

def insert_story_headlines(story_headlines_map, date):
    headlines_objectId_map = {}
    for key, value in story_headlines_map.items():
        inserted_doc = story_collection.insert_one({
            'title': value,
            'date': date,
            'blindspot': False
        })
        headlines_objectId_map[key] = inserted_doc.inserted_id
    return headlines_objectId_map

def process_articles_by_day():
    articles_grouped_by_date = get_articles_grouped_by_date()
    results = []

    for articles_in_day in articles_grouped_by_date:
        blindspots = 0
        titles = articles_in_day['titles']
        title_ids = articles_in_day['ids']
        
        labels_pred = pipeline.fit_predict(titles)
        articles = list(zip(title_ids, titles, labels_pred))
        articles.sort(key=lambda x: x[2])

        # Generate story headlines map
        headlines_map = get_story_headlines_map(articles)
        # Save story to database
        headlines_objectId_map = insert_story_headlines(headlines_map, articles_in_day['_id'])
        
        # Update articles with 'group_headline' and 'blindspot'
        for article in articles:
            if article[2] == -1:
                blindspots += 1
                story_inserted = insert_story(article[1], articles_in_day['_id'], blindspot=True)
                update_article(article[0], story_inserted, blindspot=True)
            else:
                update_article(article[0], headlines_objectId_map[article[2]], blindspot=False)
        
        results.append({
            "date": articles_in_day['_id'],
            "total_articles": len(titles),
            "total_headlines": len(headlines_map),
            "total_blindspots": blindspots
        })
    
    return results

# Define the FastAPI endpoint
@app.post("/process-articles/")
def process_articles_endpoint():
    """
    Endpoint to trigger article processing.
    """
    results = process_articles_by_day()
    return {"status": "success", "results": results}