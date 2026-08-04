import os
from dotenv import load_dotenv
load_dotenv()

from database import init_db, is_grant_posted, mark_grant_posted

init_db()

print("Is posted?", is_grant_posted("https://grantlar.uz/international-chemistry-art-competition/"))

mark_grant_posted("Test Grant", "https://grantlar.uz/international-chemistry-art-competition/")

print("Is posted after?", is_grant_posted("https://grantlar.uz/international-chemistry-art-competition/"))
