
from sklearn.decomposition import PCA
from sklearn.pipeline import Pipeline
from sklearn.cluster import DBSCAN
from classes.EmbeddingTransformer import EmbeddingTransformer
from datetime import datetime , timedelta
from config.db import db

news_articles_collection = db['articles']
story_collection = db['stories']

def get_cluster_pipeline():

    embeddingTransformer = EmbeddingTransformer()
    pca = PCA(n_components=0.90)
    dbscan = DBSCAN(eps=0.6, min_samples=2, n_jobs=-1)

    pipeline = Pipeline([
        ('embedding', embeddingTransformer),
        ('pca', pca),
        ('dbscan', dbscan)
    ])
    
    return pipeline

def fetch_articles_last_24_hours():

    now = datetime.now()
    twenty_four_hours_ago = now - timedelta(days=1)

    pipeline = [
        {
        '$match': {'scraped_date': {'$gte': twenty_four_hours_ago} }
        },
        {
            '$project': {
                'link': 1,
                'title': 1,
                'scraped_date' : 1,
                'status' : 1 ,
                'entities' : 1,
                'blindspot' : {'$ifNull': ['$blindspot', None]},
                'story_id': {'$ifNull': ['$story_id', None]}  # Assign null if missing
            }
        }
    ]
    
    recent_articles = list(news_articles_collection.aggregate(pipeline))
    return recent_articles


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

def insert_story(title, date, entities , blindspot=False):
    story = story_collection.insert_one({
        'title': title,
        'date': date,
        'entities' : entities,
        'blindspot': blindspot
    })
    return story.inserted_id

def update_article(_id, story_id, status , blindspot=False):
    new_status = 'grouped' if status == 'scraped' else status
    
    news_articles_collection.update_one(
        {'_id': _id},
        {'$set': {'story_id': story_id, 'blindspot': blindspot , 'status' : new_status}}
    )
    return _id

def assign_story_id_to_articles(articles , story_id , blindspot=False):
    
    filter_query = { '_id' : {'$in' : articles} }
    update_query = { "$set" : { 'story_id' : story_id , 'status' : 'grouped' } }
    
    result = news_articles_collection.update_many(filter_query, update_query)
    return result
    
def update_story_blindspot_status(story_id , blindspot):
        updated_story = story_collection.update_one({ '_id' : story_id } , { '$set' : { 'blindspot' : blindspot } })
        return story_id

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
