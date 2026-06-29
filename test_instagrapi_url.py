from instagrapi import Client

cl = Client()
cl.login("sultonov_gym77", "Samandar5070.")

url = "https://www.instagram.com/reel/DNa1kuCz9JI/"
media_pk = cl.media_pk_from_url(url)
media = cl.media_info(media_pk)
print("Is video?", media.media_type == 2)
if media.media_type == 2:
    print("Video URL:", media.video_url)
