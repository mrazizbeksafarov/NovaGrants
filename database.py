import os
from dotenv import load_dotenv
load_dotenv() # Local muhit uchun
from supabase import create_client, Client

# Supabase ulanishi
url = str(os.getenv("SUPABASE_URL", "")).strip()
key = str(os.getenv("SUPABASE_KEY", "")).strip()

# Faqat kalitlar kiritilgan bo'lsagina ulanadi
try:
    if url and key and "your_supabase" not in url:
        supabase: Client = create_client(url, key)
        print("Supabase obyekti muvaffaqiyatli yaratildi.")
    else:
        supabase = None
        print("DIQQAT: Supabase URL yoki KEY topilmadi!")
except Exception as e:
    print(f"Supabase ulanishida xatolik yuz berdi: {e}")
    supabase = None

def init_db():
    """
    Supabase'da jadvalni dastur ichidan avtomatik yaratib bo'lmaydi.
    Buning uchun Supabase SQL Editor'da quyidagi kodni ishga tushirishingiz kerak:
    
    CREATE TABLE posted_grants (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        url TEXT NOT NULL UNIQUE,
        posted_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """
    if supabase:
        print("Supabase ma'lumotlar bazasiga muvaffaqiyatli ulandi.")
    else:
        print("OGOHLANTIRISH: Supabase kalitlari topilmadi (.env faylini tekshiring).")

def is_grant_posted(url: str) -> bool:
    """Grant URL orqali oldin yuborilganini tekshirish."""
    if not supabase:
        return False # Agar ulanmagan bo'lsa, doim yangi deb o'ylaydi
        
    try:
        response = supabase.table("posted_grants").select("*").eq("url", url).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Bazada tekshirishda xatolik: {e}")
        return False

def mark_grant_posted(title: str, url: str):
    """Grantni yuborilganlar ro'yxatiga (Supabase) qo'shish."""
    if not supabase:
        return
        
    try:
        data = {"title": title, "url": url}
        supabase.table("posted_grants").insert(data).execute()
    except Exception as e:
        print(f"Bazaga yozishda xatolik: {e}")

if __name__ == "__main__":
    init_db()
