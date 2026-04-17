from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("MONGO_URI")

client = MongoClient(uri)

db = client["Techscore"]   # ✅ FIXED
collection = db["users"]

print("Connected to MongoDB ✅")