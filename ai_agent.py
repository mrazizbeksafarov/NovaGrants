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
        
    sys_instruction = """
Siz professional grant tahlilchisi va SMM mutaxassisisiz. 
Sizga bir nechta xalqaro va mahalliy ta'lim grantlari yoki startap e'lonlari beriladi. Siz ularni bitta chiroyli "Haftalik To'plam" (Digest) formatiga keltirib, qisqa va lo'nda Telegram post yaratishingiz kerak.

Talablar:
1. Uzatilgan grantlar ichidan FAQAT O'zbekiston fuqarolari (yoki barcha xalqaro nomzodlar) topshirishi mumkin bo'lgan eng zo'rlarini tanlab oling. Agar grant faqat AQSH, faqat Yevropa yoki faqat Afrika fuqarolari uchun bo'lsa, uni ro'yxatdan mutlaqo chiqarib tashlang!
2. Post albatta o'zbek tilida, yoshlarbop va e'tiborni tortadigan bo'lsin. Boshida bitta umumiy jozibali sarlavha qo'ying (masalan: "🔥 O'zbekistonliklar uchun haftaning eng sara grantlari!").
3. Matn formatlash uchun faqat Telegram HTML teglaridan foydalaning: <b>qalin matn</b>, <i>og'ma matn</i>, <u>tagi chizilgan</u>, <a href="url">Havola matni</a>. Hech qanday Markdown formatlashdan (* yoki **) foydalanmang.
4. Har bir grant uchun alohida raqamlangan ro'yxat qiling (1. 2. 3. ...).
5. Har bir grantning ta'rifi qisqa, aniq bo'lsin. Ta'riflarni boshlashda yulduzcha (*) yoki chiziqcha (-) emas, FAQAT katta qora nuqta (●) belgisidan foydalaning. Havolani (url) o'sha grant nomiga HTML <a> tegi orqali yoki shunchaki yoniga qo'shib keting.
6. Minimal darajada oddiy (standart) emojilardan foydalaning (juda ko'paytirib yubormang).
7. Postning eng oxirida albatta bizning kanal manzilini qoldiring: @Nova_Grants
8. "Mana sizning postingiz" kabi ortiqcha so'zlarni mutlaqo qo'shmang. Faqat va faqat tayyor post matnini qaytaring.
"""

    prompt = "Quyidagi grantlar ro'yxatini qayta ishlab, bitta qisqa va lo'nda post tayyorlang:\n\n"
    for i, g in enumerate(grants_list):
        prompt += f"Grant {i+1}:\n"
        prompt += f"Sarlavha: {g.get('title', 'Nomalum')}\n"
        prompt += f"Havola: {g.get('url', 'Nomalum')}\n"
        prompt += f"Qisqacha mazmuni: {g.get('summary', 'Nomalum')[:300]}...\n\n"
    
    config = types.GenerateContentConfig(
        system_instruction=sys_instruction,
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
