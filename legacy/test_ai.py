import os
import sys
from ai_agent import format_grant_post

# Force utf-8
sys.stdout.reconfigure(encoding='utf-8')

dummy_grant = {
    "title": "Global Innovation Fund 2026",
    "url": "https://example.com/grant",
    "summary": "The Global Innovation Fund provides up to $50,000 for innovative projects in developing countries. Age limit: 18-35. Full financial support provided. Deadline is Dec 31, 2026."
}

post = format_grant_post(dummy_grant)
with open("sample_post.txt", "w", encoding="utf-8") as f:
    f.write(post)
print("Saved to sample_post.txt")
