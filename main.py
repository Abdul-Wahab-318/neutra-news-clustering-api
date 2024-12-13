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
import os
from datetime import datetime , timedelta
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content
from utils.prompt_instructions import instructions
import pandas as pd

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
@app.post("/cluster-articles")
def process_articles_endpoint():
    """
    Endpoint to trigger article processing.
    """
    results = process_articles_by_day()
    return {"status": "success", "results": results}

def fetch_articles_last_24_hours():
    articles = db['articles']
    
    now = datetime.now()
    twenty_four_hours_ago = now - timedelta(days=1)
    
    pipeline = [
        {
        '$match': {'scraped_date': {'$gte': twenty_four_hours_ago}}
        },
        {
            '$project': {
                'link': 1,
                'title': 1,
                'story_id': {'$ifNull': ['$story_id', None]}  # Assign null if missing
            }
        }
    ]
    
    recent_articles = list(articles.aggregate(pipeline))
    return recent_articles

@app.post("/cluster-articles-test")
def cluster_articles_test():
    """
        Endpoint to group together similar articles together by creating stories.
    """
    recent_articles = fetch_articles_last_24_hours()
    df = pd.DataFrame(recent_articles)
    recent_titles = df['title']
    recent_story_ids = df['story_id']
    
    pipeline = get_cluster_pipeline()
    y_pred = pipeline.fit_predict(recent_titles)
    
    results = zip(recent_titles , y_pred)
    results = sorted(results, key=lambda x : x[1])

    #print(df.head())
    print(df['title'].values)
    # for title , label in results:
    #     print(title , " : " , label)
    
    return {"status": "success", "results": "bruh"}
    

@app.patch("/review_articles")
def review_articles_endpoint():
    
    article_collection = db['articles']
    unreviewed_articles = list(article_collection.find({'status' : 'scraped'}).limit(1))
    
    genai.configure(api_key="AIzaSyATk9QPe9VjGfyg5VajajNPsp-9PcigZnU")

    # Create the model
    generation_config = {
    "temperature": 0.8,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_schema": content.Schema(
        type = content.Type.OBJECT,
        enum = [],
        required = ["bias_labels", "bias_reason"],
        properties = {
        "bias_labels": content.Schema(
            type = content.Type.ARRAY,
            items = content.Schema(
            type = content.Type.STRING,
            ),
        ),
        "bias_reason": content.Schema(
            type = content.Type.STRING,
        ),
        },
    ),
    "response_mime_type": "application/json",
    }

    model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    system_instruction=instructions,
    )
    
    for article in unreviewed_articles:
        prompt = article['title'] + "\n" + article['content']
        chat_session = model.start_chat(history=[])
        response = chat_session.send_message(prompt)
        print(response.text)
    
    return {"status": "success", "result" : response.text }
    pass