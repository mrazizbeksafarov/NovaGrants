import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if api_key and api_key != "your_google_gemini_api_key_here":
    client = genai.Client(api_key=api_key)
else:
    client = None

def format_multiple_grants_post(grants_list):
    if not client:
        # Fallback agar AI ishlamasa
        fallback_text = "🎯 YANGI GRANTLAR TO'PLAMI!\n\n"
        for i, g in enumerate(grants_list):
            fallback_text += f"{i+1}. {g.get('title', 'Nomalum')}\nBatafsil: {g.get('url', 'Nomalum')}\n\n"
        fallback_text += "@Nova_Grants"
        return fallback_text
        
    system_instruction = """
Sen 'Nova Grants' Telegram kanalining rasmiy boshqaruvchisi (Admini) va aqlli Sun'iy Intellekt agentisan. Postni xuddi obunachilaringiz bilan samimiy suhbatlashayotgan kanal admini sifatida yoz! (Masalan: "Salom grant ovchilari! Men Nova Grants agentiman va bugun sizlar uchun eng zo'r grantlarni yig'ib keldim...").

Talablar:
1. Uzatilgan grantlar ichidan FAQAT O'zbekiston fuqarolari (yoki barcha xalqaro nomzodlar) topshirishi mumkin bo'lgan eng zo'rlarini tanlab oling. Agar grant faqat AQSH, Yevropa yoki faqat Afrika fuqarolari uchun bo'lsa, uni mutlaqo chiqarib tashlang.
2. Sarlavha juda jozibali bo'lsin.
3. Matn formatlash uchun faqat Telegram HTML teglaridan foydalaning: <b>qalin matn</b>, <i>og'ma matn</i>, <u>tagi chizilgan</u>, <a href="url">Havola matni</a>. Hech qanday Markdown formatlashdan (* yoki **) umuman foydalanmang!
4. Har bir grant uchun alohida raqamlangan ro'yxat qiling (1. 2. 3. ...).
5. DIQQAT: Har bir grant ta'rifini boshlashda yulduzcha (*) yoki chiziqcha (-) EMAS, faqatgina katta qora nuqta (●) belgisini ishlating! Havolani (url) o'sha grant nomiga HTML <a> tegi orqali biriktiring.
6. Minimal va chiroyli emojilardan foydalaning.
7. O'quvchilarni faqat tayyoriga uchmasdan, mustaqil izlanish (research) qilishga undaydigan, ilhomlantiruvchi 1-2 gaplik motivatsiya (Call to Action) yozing. 
8. Postning eng oxirida kanal manzilini qoldiring: @Nova_Grants
9. Faqat va faqat tayyor post matnini qaytaring. Ortiqcha so'zlar yozmang.
"""

    prompt = "Quyidagi grantlar ro'yxatini qayta ishlab, bitta qisqa va lo'nda post tayyorlang:\n\n"
    for i, g in enumerate(grants_list):
        prompt += f"Grant {i+1}:\n"
        prompt += f"Sarlavha: {g.get('title', 'Nomalum')}\n"
        prompt += f"Havola: {g.get('url', 'Nomalum')}\n"
        prompt += f"Qisqacha mazmuni: {g.get('summary', 'Nomalum')[:300]}...\n\n"
    
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.4,
    )
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=config
        )
        return response.text.strip()
    except Exception as e:
        print(f"AI bilan ishlashda xatolik: {e}")
        fallback_text = "🎯 YANGI GRANTLAR TO'PLAMI!\n\n"
        for i, g in enumerate(grants_list):
            fallback_text += f"{i+1}. {g.get('title', 'Nomalum')}\nBatafsil: {g.get('url', 'Nomalum')}\n\n"
        fallback_text += "@Nova_Grants"
        return fallback_text
