import os
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client, Client
from datetime import datetime, timezone

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
    """Supabase ulanishini tekshirish."""
    if supabase:
        try:
            # Ulanishni sinab ko'rish
            response = supabase.table("posted_grants").select("id").limit(1).execute()
            print(f"Supabase bazasi tayyor. Jami {len(response.data)} ta yozuv topildi (test so'rov).")
        except Exception as e:
            print(f"Supabase bazasiga ulanishda muammo: {e}")
    else:
        print("OGOHLANTIRISH: Supabase kalitlari topilmadi (.env faylini tekshiring).")

def is_grant_posted(grant_url: str) -> bool:
    """Grant URL orqali oldin yuborilganini tekshirish."""
    if not supabase:
        return False
        
    try:
        response = supabase.table("posted_grants").select("id").eq("url", grant_url).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Bazada tekshirishda xatolik: {e}")
        return False

def mark_grant_posted(title: str, grant_url: str):
    """Grantni yuborilganlar ro'yxatiga (Supabase) qo'shish."""
    if not supabase:
        return
        
    try:
        data = {"title": title, "url": grant_url}
        supabase.table("posted_grants").insert(data).execute()
        print(f"  ✅ Bazaga saqlandi: {title[:50]}...")
    except Exception as e:
        print(f"  ❌ Bazaga yozishda xatolik: {e}")

def get_last_post_time():
    """
    Bazadagi eng oxirgi yuborilgan grant vaqtini qaytaradi.
    Agar baza bo'sh bo'lsa yoki xatolik yuz bersa None qaytaradi.
    """
    if not supabase:
        return None
    
    try:
        response = (supabase.table("posted_grants")
                    .select("posted_date")
                    .order("posted_date", desc=True)
                    .limit(1)
                    .execute())
        
        if response.data and len(response.data) > 0:
            date_str = response.data[0]["posted_date"]
            # ISO format'dagi vaqtni parse qilamiz
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return None
    except Exception as e:
        print(f"Oxirgi post vaqtini olishda xatolik: {e}")
        return None

if __name__ == "__main__":
    init_db()
    last = get_last_post_time()
    if last:
        print(f"Oxirgi post vaqti: {last.isoformat()}")
    else:
        print("Bazada hali post yo'q.")
