import requests
import json

url = "http://localhost:8000/v1/models/load"
data = {
    "model": "Qwen/Qwen2.5-0.5B-Instruct",
    "mode": "fullram"
}
response = requests.post(url, json=data)
print(response.status_code)
print(response.json())
