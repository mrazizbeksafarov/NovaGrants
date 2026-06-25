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
Sen 'Nova Grants' Telegram kanalining boshqaruvchisi (Admini) san. O'zingni hech qachon "Agentman" yoki "Botman" deb tanishtirma! Postni xuddi o'z obunachilari bilan samimiy suhbatlashayotgan professional inson (admin) sifatida yoz.

Talablar (post_text uchun):
1. Uzatilgan grantlar ichidan FAQAT O'zbekiston fuqarolari (yoki barcha xalqaro nomzodlar) topshirishi mumkin bo'lgan eng zo'rlarini tanlab oling. AQSH/Yevropa fuqarolari uchun bo'lsa chiqarib tashlang.
2. Sarlavhani ijodiy yozing! (Masalan: "🔥 Bugungi eng sara xalqaro grantlar!", "🎓 Yangi ajoyib imkoniyatlar!").
3. Matn formatlash uchun faqat Telegram HTML teglaridan foydalaning (<b>, <i>, <a>).
4. Har bir grant uchun alohida raqamlangan ro'yxat qiling (1. 2. 3. ...).
5. Har bir grant ta'rifida katta qora nuqta (●) belgisini ishlating. Havolani HTML <a> tegi orqali biriktiring.
6. Minimal va chiroyli emojilardan foydalaning.
7. Post oxirida motivatsion gap (har safar turlicha) va kanal manzilini qoldiring: @Nova_Grants

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
                print("AI muvaffaqiyatli JSON javob qaytardi.")
                try:
                    data = json.loads(result)
                    return data
                except Exception as e:
                    print(f"JSON parsing xatosi: {e}")
                    break
            else:
                print("AI bo'sh javob qaytardi.")
                break
                
        except Exception as e:
            error_str = str(e)
            if "503" in error_str or "500" in error_str or "429" in error_str:
                print(f"Gemini serveri band ({error_str[:50]}). {attempt + 1}-urinish xatosi. 10s kutamiz...")
                time.sleep(10)
                continue
            else:
                print(f"AI bilan ishlashda kutilmagan xatolik: {e}")
                break
                
    print("Barcha urinishlar barbod bo'ldi. Zaxira (Fallback) shabloniga o'tilmoqda...")
    return {"post_text": _fallback_format(grants_list), "deadlines": []}

def _fallback_format(grants_list):
    """Zaxira formatlash."""
    fallback_text = "🔥 <b>Bugungi eng sara xalqaro grantlar!</b>\n\n"
    fallback_text += "Salom, grant ovchilari! 👋 Bugun ham siz uchun eng qiziqarli imkoniyatlarni jamladik:\n\n"
    for i, g in enumerate(grants_list):
        title = g.get('title', 'Nomalum')
        url = g.get('url', '#')
        fallback_text += f"{i+1}. <b><a href='{url}'>{title}</a></b>\n"
        fallback_text += f"● Batafsil ma'lumot olish uchun rasmiy saytiga kiring.\n\n"
    
    fallback_text += "🚀 Katta imkoniyatlar izlaganlarga ochiladi! Havolalarga kirib, saytlarni o'zingiz ham chuqurroq o'rganing!\n\n"
    fallback_text += "@Nova_Grants"
    return fallback_text
