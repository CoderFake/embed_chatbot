import os
import sys
sys.path.append('/app')

from pymilvus import MilvusClient
from app.config.settings import settings

def drop_all():
    uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
    print(f"Connecting to Milvus at {uri}...")
    try:
        client = MilvusClient(uri=uri)
        collections = client.list_collections()
        print(f"Found {len(collections)} collections: {collections}")
        
        for collection in collections:
            print(f"Dropping collection: {collection}")
            client.drop_collection(collection_name=collection)
            print(f"Dropped {collection}")
            
        print("All collections dropped successfully.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    drop_all()
