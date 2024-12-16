from pymongo import MongoClient

MONGODB_URI = "mongodb://localhost:27017/"
client = MongoClient(MONGODB_URI)
db = client['neutra_news_test']