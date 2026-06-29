import requests
import re
from urllib.parse import unquote

def test_snapinsta():
    print("Testing snapinsta...")
    try:
        url = "https://snapinsta.app/action.php"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Origin": "https://snapinsta.app",
            "Referer": "https://snapinsta.app/"
        }
        data = {"url": "https://www.instagram.com/reel/DNa1kuCz9JI/", "action": "post"}
        r = requests.post(url, headers=headers, data=data, timeout=10)
        print("Snapinsta code:", r.status_code)
        if r.status_code == 200:
            print("Snapinsta success snippet:", r.text[:200])
    except Exception as e:
        print("Snapinsta err:", e)

def test_igdownloader():
    print("Testing igdownloader...")
    try:
        url = "https://v3.igdownloader.app/api/ajaxSearch"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest"
        }
        data = {"q": "https://www.instagram.com/reel/DNa1kuCz9JI/", "t": "media", "lang": "en"}
        r = requests.post(url, headers=headers, data=data, timeout=10)
        print("IGDownloader code:", r.status_code)
        if r.status_code == 200:
            print("IGDownloader success snippet:", r.text[:200])
    except Exception as e:
        print("IGDownloader err:", e)
        
test_snapinsta()
test_igdownloader()
