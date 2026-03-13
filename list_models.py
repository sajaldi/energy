import os
import google.generativeai as genai
from core.ai_utils import API_KEY

genai.configure(api_key=API_KEY)

print("Listing models...")
for m in genai.list_models():
    if 'embedContent' in m.supported_generation_methods:
        print(f"Model ID: {m.name}")
        print(f"  Description: {m.description}")
        print(f"  Supported Tasks: {m.supported_generation_methods}")
