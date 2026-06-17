import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()
api_key = os.getenv("SUBDL_API_KEY")

def test_subdl():
    if not api_key:
        print("No SUBDL_API_KEY")
        return
    url = "https://api.subdl.com/api/v1/subtitles"
    params = {
        "api_key": api_key,
        "tmdb_id": "157336",
        "languages": "EN"
    }
    r = requests.get(url, params=params)
    data = r.json()
    dl_url = data["subtitles"][0]["url"]
    dl_url_full = "https://dl.subdl.com" + dl_url
    print("Download URL:", dl_url_full)
    
    r2 = requests.get(dl_url_full)
    import io
    import zipfile
    if r2.status_code == 200:
        with zipfile.ZipFile(io.BytesIO(r2.content)) as z:
            print("Zip contents:", z.namelist())
    else:
        print("Download failed", r2.status_code)

test_subdl()
