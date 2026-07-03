import os
import json
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Optional

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if api_key and api_key != "your_google_gemini_api_key_here":
    client = genai.Client(api_key=api_key)
    print("Gemini AI clienti tayyor.")
else:
    client = None
    print("DIQQAT: GEMINI_API_KEY topilmadi!")

class GrantDeadline(BaseModel):
    url: str = Field(description="Grant URL corresponding to the input")
    deadline_iso: Optional[str] = Field(description="Deadline in ISO 8601 format (e.g. 2026-10-31T23:59:59Z). If no deadline is explicitly mentioned or it is unclear, return null.")

class FormattedPost(BaseModel):
    post_text: str = Field(description="The beautifully formatted Telegram post text containing all grants. Must use <b>, <i>, <a> tags.")
    deadlines: List[GrantDeadline] = Field(description="List of extracted deadlines for each grant provided in the input.")

def format_multiple_grants_post(grants_list):
    """Grantlarni AI yordamida formatlash va JSON orqali deadline larni olish."""
    if not grants_list:
        return None
        
    if not client:
        print("AI ishlamayapti — Fallback (Zaxira) rejimiga o'tildi.")
        return {"post_text": _fallback_format(grants_list), "deadlines": []}
        
    system_instruction = """
Sen 'Nova Grants' Telegram kanalining boshqaruvchisi (Admini) san. O'zingni hech qachon AI yoki Bot deb tanishtirma!
Postni zamonaviy, vizual jihatdan o'ta chiroyli (premium), lekin MINIMAL VA SIFATLI uslubda yoz. Emojilardan deyarli foydalanma (eng muhim joyidagina 1-2 ta ishlat). Bu oddiy ro'yxat emas, har bir grant jiddiy kashfiyotdek taqdim etilishi kerak.

Talablar (post_text uchun):
1. Senga berilgan grantlar ichidan FAQAT O'zbekiston fuqarolariga moslarini (xalqaro ochiq bo'lganlarini) saralab ol. Soni qancha bo'lishidan qat'iy nazar, bari kiritilsin.
2. DIQQAT: Agar grantning oxirgi topshirish muddati (deadline) o'tib ketgan bo'lsa, uni MUTLAQO postga qo'shma! Faqat muddati bor yoki kelajakdagi grantlarni ol. Shuningdek, oddiy yangiliklar yoki "Vebinar boshlandi" kabi e'lonlarni umuman kiritma.
3. ENG MUHIM QOIDA (HAVOLALAR): Hech qachon ochiq (raw) http://... havolalarni matnga yozma! Bu juda xunuk ko'rinadi. Ularni DOIM HTML `<a>` tegi ichiga yashir.
   ❌ Noto'g'ri: 👉 Batafsil (https://...)
   ✅ To'g'ri: 👉 <a href="https://...">Batafsil ma'lumot va ariza topshirish</a>
   
4. Har bir grantni quyidagi "Premium" shablonda yozing:
   <b>[Grant yoki Startap Nomi]</b>
   📝 <i>[Qisqa va lo'nda tavsif - faqat eng asosiy foydasi (masalan, $50,000 investitsiya, to'liq grant)]</i>
   🔗 <a href="[URL]">Batafsil tanishish va ariza topshirish</a>

5. Sarlavhani har safar 100% turlicha, zamonaviy, jiddiy va "qaynoq" uslubda yozing. Bir xil gaplarni takrorlama. Emojilarni minimal darajaga tushiring.
6. Matn formatlash uchun faqat ruxsat etilgan Telegram HTML teglaridan (<b>, <i>, <a>) foydalaning.
7. Agar berilgan ro'yxatda birorta ham munosib grant bo'lmasa, post_text ni bo'sh string ("") qilib qaytar.
8. Post oxirida har safar turlicha, kuchli chaqiriq va kanal manzilini qoldiring: @Nova_Grants

Talablar (deadlines uchun):
Har bir grant matnini o'qib, uning tugash muddati (deadline) ni toping. Agar sanani aniq bilsangiz, uni ISO 8601 formatiga o'tkazib (masalan 2026-12-31T00:00:00Z) yozing. Agar muddat ko'rsatilmagan bo'lsa null qilib qaytaring.
"""

    prompt = "Quyidagi grantlar ro'yxatini qayta ishlab, bitta qisqa post tayyorlang va deadlinelarni ajrating:\n\n"
    for i, g in enumerate(grants_list):
        prompt += f"Grant {i+1}:\n"
        prompt += f"Sarlavha: {g.get('title', 'Nomalum')}\n"
        prompt += f"Havola: {g.get('url', 'Nomalum')}\n"
        prompt += f"Qisqacha mazmuni: {g.get('summary', 'Nomalum')[:500]}...\n\n"
    
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=FormattedPost
    )
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
                config=config
            )
            result = response.text.strip()
            if result:
                # Tozalash: Markdown backtick larni olib tashlash
                if result.startswith("```json"):
                    result = result[7:]
                elif result.startswith("```"):
                    result = result[3:]
                if result.endswith("```"):
                    result = result[:-3]
                result = result.strip()
                
                try:
                    data = json.loads(result)
                    if data.get("post_text") == "":
                        print("AI mos grant topmadi. Post qilinmaydi.")
                        return None
                    return data
                except Exception as e:
                    print(f"JSON parsing xatosi: {e}. Qayta urinib ko'rilmoqda...")
                    time.sleep(5)
                    continue
            else:
                print("AI bo'sh javob qaytardi. Qayta urinish...")
                time.sleep(5)
                continue
                
        except Exception as e:
            error_str = str(e)
            if "503" in error_str or "500" in error_str or "429" in error_str:
                print(f"Gemini serveri band ({error_str[:50]}). {attempt + 1}-urinish xatosi. 10s kutamiz...")
                time.sleep(10)
                continue
            elif "finish_reason" in error_str or "safety" in error_str.lower():
                print(f"AI xavfsizlik filtri ishga tushdi yoki boshqa xato: {e}")
                return None
            else:
                print(f"AI bilan ishlashda kutilmagan xatolik: {e}")
                return None
                
    print("Barcha urinishlar barbod bo'ldi. Post qilinmaydi (qoldiriladi).")
    return None
