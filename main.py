from fastapi import FastAPI
from sklearn.pipeline import Pipeline
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.decomposition import PCA
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score
from typing import List
from config.db import db
from utils.helpers import get_articles_grouped_by_date , get_story_headlines_map ,insert_story_headlines , insert_story
from utils.helpers import get_cluster_pipeline , update_article

# Initialize FastAPI
app = FastAPI()


def process_articles_by_day():
    articles_grouped_by_date = get_articles_grouped_by_date()
    results = []
    pipeline = get_cluster_pipeline()
    
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
@app.post("/process-articles")
def process_articles_endpoint():
    """
    Endpoint to trigger article processing.
    """
    results = process_articles_by_day()
    return {"status": "success", "results": results}

@app.patch("/review_articles")
def review_articles_endpoint():
    pass