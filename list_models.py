import requests

API_KEY = "AIzaSyD6NlcfSsDPTxNzefz6M8z_mEpEsJVaGkE"
URL = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"

try:
    response = requests.get(URL)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
