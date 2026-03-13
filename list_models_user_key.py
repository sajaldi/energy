import google.generativeai as genai

API_KEY = "AIzaSyAgSvWelKxKHKPL1iFm3M7kKi7zPrcy1n8"
genai.configure(api_key=API_KEY)

try:
    print("Listing models with user key...")
    for m in genai.list_models():
        print(f"ID: {m.name}")
        # Explicitly check for embedContent in the m.supported_methods list
        is_embedding = 'embedContent' in m.supported_methods
        print(f"  Supports Embedding: {is_embedding}")
except Exception as e:
    print(f"Error: {e}")
