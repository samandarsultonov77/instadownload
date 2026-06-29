from instagrapi import Client
import os

cl = Client()
try:
    cl.login("sultonov_gym77", "Samandar5070.")
    print("Instagrapi login success!")
    # Test downloading a reel
    url = "https://www.instagram.com/reel/DNa1kuCz9JI/"
    media_pk = cl.media_pk_from_url(url)
    media_path = cl.video_download(media_pk, folder=".")
    print("Video downloaded to:", media_path)
except Exception as e:
    print("Instagrapi error:", e)
