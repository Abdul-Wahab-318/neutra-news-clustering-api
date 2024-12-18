import pandas as pd
import json
import time
import csv
from fastapi import FastAPI
from datetime import datetime , timedelta

from config.db import db
from utils.model import model
from utils.helpers import get_articles_grouped_by_date , get_story_headlines_map ,insert_story_headlines , insert_story , assign_story_id_to_articles
from utils.helpers import get_cluster_pipeline , update_article , update_story_blindspot_status

# Initialize FastAPI
app = FastAPI()

@app.post("/articles/cluster")
def process_articles_endpoint():
    """
    Endpoint to trigger article processing.
    """
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
    
    return {"status": "success", "results": results}

def fetch_articles_last_24_hours():
    articles = db['articles']
    
    now = datetime.now()
    twenty_four_hours_ago = now - timedelta(days=1)
    #'source' : {'$ne' : 'Geo'}
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
                'blindspot' : {'$ifNull': ['$blindspot', None]},
                'story_id': {'$ifNull': ['$story_id', None]}  # Assign null if missing
            }
        }
    ]
    
    recent_articles = list(articles.aggregate(pipeline))
    return recent_articles

@app.post("/articles/cluster/test")
def cluster_articles_test():
    """
        Endpoint to group together similar articles together by creating stories.
    """
    recent_articles = fetch_articles_last_24_hours()
    
    if( len(recent_articles) == 0):
        return {"status" : "success" , "message" : "No articles to cluster in the past 24hours" , "result" : None}
    
    df = pd.DataFrame(recent_articles)
    recent_titles = df['title']

    pipeline = get_cluster_pipeline()
    y_pred = pipeline.fit_predict(recent_titles)
    
    df['label'] = y_pred
    cluster_labels = set(y_pred)
    
    if( -1 in cluster_labels ):
        cluster_labels.remove(-1)
    
    #FIRST HANDLE BLINDSPOT ARTICLES AND STORIES
    df_blindspots = df[ (df['label'] == -1) & (df['story_id'].isna()) ]
    for index , blindspot_article in df_blindspots.iterrows():
        print("\n\nBlindspot article : " , blindspot_article['title'] )
        print("Previous blindspot status : " , blindspot_article['blindspot'])
        story_id = insert_story( blindspot_article['title'] , blindspot_article['scraped_date'] , blindspot=True )
        updated_article = update_article(blindspot_article['_id']  , story_id , blindspot_article['status'] , blindspot=True)
    
    #NEXT HANDLE GROUPED ARTICLES
    
    for label in cluster_labels:
        df_cluster = df[ df['label'] == label ]
        
        first_existing_story_index = df_cluster['story_id'].first_valid_index()
        
        if first_existing_story_index is None: # if all articles dont belong to an already existing story in the past 24 hours
            new_story = df_cluster.iloc[0,:]
            isBlindspot = False
            print('\n\nCompletely New cluster of news : ' , df_cluster['title'].values )
            new_story_id = insert_story(new_story['title'] , new_story['scraped_date'] , isBlindspot) 
            assign_story_id_to_articles(df_cluster['_id'].tolist() , new_story_id , isBlindspot)
            
        else: # if we have an existing story in the past 24 hours

            article_with_story_id = df_cluster.loc[first_existing_story_index]
            isBlindspot = article_with_story_id['blindspot']
            articles_to_update = df_cluster[ df_cluster['story_id'].isna() ]
            
            if(isBlindspot): #if story was previously blindspot but now new articles have appeared then update story blindspot status 
                update_story_blindspot_status(article_with_story_id['story_id'] , False)
                print("\n\nArticle was blindspot but now new articles have appeared : " , article_with_story_id['title'])
            print("New articles : " , articles_to_update['title'].values)
            assign_story_id_to_articles(articles_to_update['_id'].tolist() , article_with_story_id['story_id'] , blindspot=False )
            
            pass
            
        print("\n\n")
    
    
    return {"status": "success", "results": "bruh"}
    
@app.patch("/articles/review")
def review_articles_endpoint():
    
    article_collection = db['articles']
    unreviewed_articles = article_collection.find(
        {'status' : 'scraped'},
        {'_id' : 1 , 'content' : 1 , 'title' : 1}
    ).limit(900)
    unreviewed_articles = list(unreviewed_articles)
    
    if(len(unreviewed_articles) == 0):
        return {"status": "success", "result" : None , "message" : 'No articles to review' }

    for article in unreviewed_articles:
        try:
            prompt = article['title'] + "\n" + article['content']
            chat_session = model.start_chat(history=[])
            response = chat_session.send_message(prompt)
            result = json.loads(response.text)
            print("title : " , article['title'])
            print("result : ")
            print(result)
            
            if( "bias_reason" not in result or "bias_labels" not in result ):
                print("Invalid result")
                continue
            
            result['bias_labels'] = [label.lower() for label in result['bias_labels'] ]
            
            updated_article = article_collection.update_one(
                { "_id" : article['_id'] } ,
                { "$set" : { "bias_labels" : result['bias_labels'] , "bias_reason" : result['bias_reason'] , "status" : 'reviewed' }}
            )
            time.sleep(4.1)
            
        except Exception as e:
            print("Error : " , e.message)
            return {"status":"failed" , result : None , "message":e.mesasge}
    
    return {"status": "success", "result" : None , "message" : f"Reviewed {len(unreviewed_articles)} articles" }

@app.get('/articles/csv')
def get_articles_csv():
    
    bias_labels = sorted(['spin' , 'opinion statements presented as fact' , 'sensationalism' , 'mudslinging' , 'omission of source' , 'factual'])
    column_names = ['_id' , 'title' , 'link' , 'source' , 'bias_reason'] + bias_labels
    article_collection = db['articles']
    articles = list(article_collection.find( {"bias_reason" : {"$exists" : True}} , {'_id':1, 'title':1, 'link':1, 'source':1, 'bias_reason':1 ,"bias_labels":1} ))
    print("Length : " , len(articles))
    
    for article in articles:
        article_labels = [ 1 if label in article['bias_labels'] else 0 for label in bias_labels  ]
        
        article_data = {
            '_id': article.get('_id'),
            'title': article.get('title'),
            'link': article.get('link'),
            'source': article.get('source'),
            'bias_reason': article.get('bias_reason', ''),  # Default to empty string if not present
        }
        
        for i , label in enumerate(bias_labels):
            article_data[label] = article_labels[i]
        
        
        with open('neutra_news_dataset.csv', mode='a', newline='') as file:
            
            writer = csv.DictWriter(file, fieldnames=column_names)
            
            #if file is empty then write column names first
            if(file.tell() == 0):
                # Write the header (column names)
                writer.writeheader()

            # Write the data rows
            writer.writerow(article_data)
        
    return {"status" : "success"}
    
