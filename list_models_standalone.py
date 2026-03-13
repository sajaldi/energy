import google.generativeai as genai

API_KEY = "AIzaSyAUEPk5NmIUWdgTHKcPo9BtDj8sjBSS0_0"
genai.configure(api_key=API_KEY)

try:
    print("Listing models...")
    for m in genai.list_models():
        if 'embedContent' in m.supported_generation_methods:
            print(f"Model ID: {m.name}")
            print(f"  Description: {m.description}")
            print(f"  Supported Tasks: {m.supported_generation_methods}")
except Exception as e:
    print(f"Error: {e}")
