import requests

url = "https://api.github.com"

response = requests.get(url, verify=False)

print("Status:", response.status_code)
print("Body:", response.text[:200])
