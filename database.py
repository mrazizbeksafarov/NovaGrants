import os
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta

# Supabase ulanishi
url = str(os.getenv("SUPABASE_URL", "")).strip()
key = str(os.getenv("SUPABASE_KEY", "")).strip()

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
    if supabase:
        try:
            response = supabase.table("posted_grants").select("id").limit(1).execute()
            print(f"Supabase bazasi tayyor. {len(response.data)} ta yozuv (test).")
        except Exception as e:
            print(f"Supabase bazasiga ulanishda muammo: {e}")
    else:
        print("OGOHLANTIRISH: Supabase kalitlari topilmadi.")

def is_grant_posted(grant_url: str) -> bool:
    if not supabase: return False
    try:
        response = supabase.table("posted_grants").select("id").eq("url", grant_url).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Bazada tekshirishda xatolik: {e}")
        return False

def mark_grant_posted(title: str, grant_url: str, deadline_iso: str = None):
    if not supabase: return
    try:
        data = {
            "title": title, 
            "url": grant_url,
            "deadline": deadline_iso,
            "reminder_sent": False
        }
        supabase.table("posted_grants").insert(data).execute()
        print(f"  ✅ Bazaga saqlandi: {title[:50]}... (Deadline: {deadline_iso})")
    except Exception as e:
        print(f"  ❌ Bazaga yozishda xatolik: {e}")

def get_grants_nearing_deadline(days: int = 5):
    """Deadline'ga `days` kun qolgan va eslatma yuborilmagan grantlarni oladi."""
    if not supabase: return []
    try:
        # Hozirgi vaqt va kelajak (5 kun) vaqti
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=days)
        
        now_str = now.isoformat()
        future_str = future.isoformat()
        
        # deadline is not null AND reminder_sent is false AND deadline > now AND deadline <= future
        response = (supabase.table("posted_grants")
                    .select("*")
                    .eq("reminder_sent", False)
                    .not_.is_("deadline", "null")
                    .gt("deadline", now_str)
                    .lte("deadline", future_str)
                    .execute())
                    
        return response.data
    except Exception as e:
        print(f"Deadline yaqin grantlarni olishda xatolik: {e}")
        return []

def mark_reminder_sent(grant_url: str):
    """Eslatma yuborilganini belgilaydi."""
    if not supabase: return
    try:
        supabase.table("posted_grants").update({"reminder_sent": True}).eq("url", grant_url).execute()
        print(f"  ✅ Eslatma yuborildi deb belgilandi: {grant_url}")
    except Exception as e:
        print(f"Eslatmani saqlashda xatolik: {e}")
