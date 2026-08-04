from scraper import fetch_grants
from ai_agent import format_grant_post

def check_raw_output():
    grants = fetch_grants()
    if not grants:
        return
    post_text = format_grant_post(grants[0])
    with open("post_output.txt", "w", encoding="utf-8") as f:
        f.write(post_text)

if __name__ == "__main__":
    check_raw_output()
