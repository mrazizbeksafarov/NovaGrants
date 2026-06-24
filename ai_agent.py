import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if api_key and api_key != "your_google_gemini_api_key_here":
    client = genai.Client(api_key=api_key)
    print("Gemini AI clienti tayyor.")
else:
    client = None
    print("DIQQAT: GEMINI_API_KEY topilmadi!")

def format_multiple_grants_post(grants_list):
    """Grantlar ro'yxatini AI yordamida chiroyli Telegram postiga aylantirish."""
    
    if not grants_list:
        return None
    
    if not client:
        print("AI ishlamayapti — Fallback (Zaxira) rejimiga o'tildi.")
        return _fallback_format(grants_list)
        
    system_instruction = """
Sen 'Nova Grants' Telegram kanalining boshqaruvchisi (Admini) san. O'zingni hech qachon "Agentman", "Sun'iy intellektman" yoki "Botman" deb tanishtirma! Buni hech kim bilmasligi kerak. Postni xuddi o'z obunachilari bilan samimiy suhbatlashayotgan professional inson (admin) sifatida yoz.

Talablar:
1. Uzatilgan grantlar ichidan FAQAT O'zbekiston fuqarolari (yoki barcha xalqaro nomzodlar) topshirishi mumkin bo'lgan eng zo'rlarini tanlab oling. Agar grant faqat AQSH, Yevropa yoki faqat Afrika fuqarolari uchun bo'lsa, uni mutlaqo chiqarib tashlang.
2. Sarlavha juda jozibali bo'lsin, lekin "O'zbekistonliklar uchun" deb qotirib qo'ymang (bu qo'pol eshitilishi mumkin). Sarlavhalarni har safar turlicha va ijodiy yozing! (Masalan: "🔥 Bugungi eng sara xalqaro grantlar!", "🎓 Sizni kutayotgan ajoyib imkoniyatlar!", "✨ Bugun e'lon qilingan eng yaxshi grantlar!" va hokazo).
3. Matn formatlash uchun faqat Telegram HTML teglaridan foydalaning: <b>qalin matn</b>, <i>og'ma matn</i>, <u>tagi chizilgan</u>, <a href="url">Havola matni</a>. Hech qanday Markdown formatlashdan (* yoki **) umuman foydalanmang!
4. Har bir grant uchun alohida raqamlangan ro'yxat qiling (1. 2. 3. ...).
5. DIQQAT: Har bir grant ta'rifini boshlashda yulduzcha (*) yoki chiziqcha (-) EMAS, faqatgina katta qora nuqta (●) belgisini ishlating! Havolani (url) o'sha grant nomiga HTML <a> tegi orqali biriktiring.
6. Minimal va chiroyli emojilardan foydalaning.
7. O'quvchilarni mustaqil izlanish (research) qilishga undaydigan, ilhomlantiruvchi 1-2 gaplik motivatsiya (Call to Action) yozing. Bu gaplarni HAR SAFAR TURLICHA va IJODIY yoz, hech qachon bir xil takroriy matn yozma!
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
    )
    
    try:
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt,
            config=config
        )
        result = response.text.strip()
        if result:
            print("AI muvaffaqiyatli javob qaytardi.")
            return result
        else:
            print("AI bo'sh javob qaytardi — Fallback rejimiga o'tildi.")
            return _fallback_format(grants_list)
    except Exception as e:
        print(f"AI bilan ishlashda xatolik: {e}")
        return _fallback_format(grants_list)

def _fallback_format(grants_list):
    """
    AI ishlamay qolganda ham post chiroyli ko'rinishi uchun zaxira formatlash.
    Bu funksiya AI'siz ishlaydi.
    """
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
