import os
import django
import logging
import sys
import requests
import time

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from core.models import KnowledgeChunk
from django.conf import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hugging Face Configuration
API_URL = "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2"
HF_TOKEN = os.environ.get("HF_TOKEN", "")
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

def query_huggingface(texts):
    payload = {
        "inputs": texts,
        "options": {"wait_for_model": True}
    }
    response = requests.post(API_URL, headers=headers, json=payload)
    if response.status_code != 200:
        logger.error(f"HF API Error: {response.status_code} - {response.text}")
        return None
    return response.json()

def ingest_contract():
    contract_path = 'contratoapp.md'
    if not os.path.exists(contract_path):
        logger.error(f"Error: {contract_path} not found.")
        return

    logger.info(f"Reading {contract_path}...")
    with open(contract_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # Clear previous chunks of this source
    logger.info("Clearing old chunks...")
    deleted_count, _ = KnowledgeChunk.objects.filter(source=contract_path).delete()
    logger.info(f"Deleted {deleted_count} old chunks.")

    logger.info("Starting chunking...")
    # Chunking
    chunk_size = 1000 # MiniLM likes smaller chunks
    overlap = 100
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            break_point = text.rfind('\n', start, end)
            if break_point == -1 or break_point <= start:
                break_point = text.rfind(' ', start, end)
            if break_point != -1 and break_point > start:
                end = break_point
        
        chunk_content = text[start:end].strip()
        if chunk_content:
            chunks.append(chunk_content)
        
        start = end - overlap
        if start >= len(text):
            break

    logger.info(f"Total chunks: {len(chunks)}")

    # Process in batches for HF Inference API (which can handle multiple inputs)
    batch_size = 20
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        logger.info(f"Processing batch {i//batch_size + 1} ({i} to {i + len(batch)})...")
        
        embeddings = query_huggingface(batch)
        if embeddings is None:
            logger.error(f"Failed to get embeddings for batch starting at {i}")
            continue

        for j, embedding in enumerate(embeddings):
            KnowledgeChunk.objects.create(
                content=batch[j],
                embedding=embedding,
                source=contract_path,
                metadata={'index': i + j, 'total': len(chunks)}
            )
        
        # Avoid rate limits
        time.sleep(1)

    logger.info("Ingestion complete.")

if __name__ == "__main__":
    ingest_contract()
