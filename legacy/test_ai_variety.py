import sys
sys.stdout.reconfigure(encoding='utf-8')

from ai_agent import format_multiple_grants_post

grants = [
    {'title': 'Stanford Fellowship', 'url': 'https://example.com/1', 'summary': 'Full scholarship for masters'},
    {'title': 'DAAD Scholarship', 'url': 'https://example.com/2', 'summary': 'Study in Germany'}
]

print("=== BIRINCHI CHAQIRUV ===")
result1 = format_multiple_grants_post(grants)
print(result1)

print("\n\n=== IKKINCHI CHAQIRUV ===")
result2 = format_multiple_grants_post(grants)
print(result2)

print("\n\n=== TAQQOSLASH ===")
if result1 == result2:
    print("⚠️ Ikki natija bir xil! Temperature ko'tarish kerak.")
else:
    print("✅ Ikki natija TURLICHA! AI har safar yangi matn yozmoqda.")
