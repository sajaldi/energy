import os
import django
import sys
import requests

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from core.models import KnowledgeChunk
from pgvector.django import L2Distance, CosineDistance

# HF Config
API_URL = "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2"
HF_TOKEN = os.environ.get("HF_TOKEN", "")
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

def get_embedding(text):
    payload = {"inputs": [text], "options": {"wait_for_model": True}}
    response = requests.post(API_URL, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()[0]
    return None

def test_search(query):
    print(f"Query: {query}")
    embedding = get_embedding(query)
    if not embedding:
        print("Error getting embedding")
        return

    # Semantic search using Cosine Distance
    results = KnowledgeChunk.objects.annotate(
        distance=CosineDistance('embedding', embedding)
    ).order_by('distance')[:3]

    print("\nTop Results:")
    for i, res in enumerate(results):
        print(f"\n--- Result {i+1} (Distance: {res.distance:.4f}) ---")
        # Print first 200 chars of content
        print(res.content[:300] + "...")

if __name__ == "__main__":
    # Test with a question about the contract (KPIs are a big part of it)
    test_search("Cuales son las multas por incumplimiento de KPIs?")
