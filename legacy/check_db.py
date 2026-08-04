import os
from dotenv import load_dotenv
load_dotenv()

from database import supabase

response = supabase.table("posted_grants").select("*").execute()
for row in response.data:
    print(row)
