"""Generate a local, interactive rendering of the same blocks sent to Telegram.

    python tools/preview_post.py

This creates review artifacts only, without sending a Telegram message.
"""

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from post_builder import build_post
from rich_schema import validate_blocks


def rich_text(value):
    if isinstance(value, str):
        return html.escape(value)
    if isinstance(value, list):
        return "".join(rich_text(v) for v in value)
    text = rich_text(value.get("text", ""))
    if value["type"] == "bold":
        return f"<strong>{text}</strong>"
    if value["type"] == "url":
        return f'<a href="{html.escape(value["url"], quote=True)}">{text}</a>'
    if value["type"] == "anchor_link":
        return f'<a href="#{html.escape(value["anchor_name"], quote=True)}">{text}</a>'
    return text


def render(blocks):
    parts = []
    for block in blocks:
        kind = block["type"]
        if kind == "heading":
            level = block["size"]
            parts.append(f'<h{level}>{rich_text(block["text"])}</h{level}>')
        elif kind == "photo":
            parts.append('<img class="cover" src="../assets/nova-grants-cover.png" alt="Nova Grants — Xalqaro imkoniyatlar">')
        elif kind in {"paragraph", "footer"}:
            tag = "footer" if kind == "footer" else "p"
            parts.append(f'<{tag}>{rich_text(block["text"])}</{tag}>')
        elif kind == "divider":
            parts.append("<hr>")
        elif kind == "blockquote":
            parts.append('<blockquote class="benefit">' + render(block["blocks"]) + '</blockquote>')
        elif kind == "anchor":
            parts.append(f'<a id="{html.escape(block["name"], quote=True)}"></a>')
        elif kind == "table":
            rows = []
            for row in block["cells"]:
                cells = []
                for cell in row:
                    tag = "th" if cell.get("is_header") else "td"
                    cells.append(f'<{tag}>{rich_text(cell.get("text", ""))}</{tag}>')
                rows.append("<tr>" + "".join(cells) + "</tr>")
            parts.append("<table><caption>" + rich_text(block.get("caption", "")) + "</caption>" + "".join(rows) + "</table>")
        elif kind == "details":
            parts.append(f'<details><summary>{rich_text(block["summary"])}</summary>{render(block["blocks"])}</details>')
        elif kind == "list":
            parts.append("<ul>" + "".join("<li>" + render(i["blocks"]) + "</li>" for i in block["items"]) + "</ul>")
        elif kind == "buttons":
            buttons = []
            for button in block["buttons"]:
                if "url" in button:
                    buttons.append(f'<a class="primary" href="{html.escape(button["url"], quote=True)}">{rich_text(button["text"])}</a>')
            parts.append('<div class="actions">' + "".join(buttons) + "</div>")
    return "\n".join(parts)


def main():
    cards = [{
        "name": "Global Flourishing Scholarship (2027)",
        "url": "https://www.sussex.ac.uk/study/fees-funding/masters-scholarships/view/1959-Global-Flourishing-Scholarship",
        "summary": "Sussex universitetida magistratura xarajatlarini kamaytirish uchun kontrakt chegirmasi.",
        "benefits": ["Birinchi yil kontraktidan £5 000 chegirma"],
        "eligibility": "Tegishli magistratura kursiga qabul olgan, Overseas fee statusiga ega nomzodlar. Kontrakti boshqa tashkilot tomonidan to‘liq qoplanadiganlar qatnasha olmaydi.",
    }, {
        "name": "ETH Student Summer Research Fellowship",
        "url": "https://inf.ethz.ch/studies/summer-research-fellowship.html",
        "summary": "ETH Zurich yozgi tadqiqot fellowship dasturi. Ushbu kartochka yangi formatni ko‘rsatish uchun berilgan.",
        "eligibility": "Amaldagi fuqarolik, o‘qish bosqichi va muddat talablarini rasmiy sahifada tekshiring.",
    }, {
        "name": "NUS Amgen Scholars Program",
        "url": "https://www.dbs.nus.edu.sg/outreach/amgen-scholars-program/",
        "summary": "Singapurdagi NUS Amgen dasturi. Kartochka avtomatik saralash natijasi sifatida e’lon qilinmagan.",
        "eligibility": "Tegishli qabul siklining talablarini rasmiy sahifada tekshiring.",
    }]
    blocks, fallback = build_post("Xalqaro ta’lim imkoniyatlari", cards)
    errors = validate_blocks(blocks)
    if errors:
        raise ValueError(errors)
    output = Path(__file__).resolve().parents[1] / "docs"
    output.mkdir(exist_ok=True)
    body = render(blocks)
    page = '''<!doctype html><html lang="uz"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nova Grants — xabar ko‘rinishi</title><style>
*{box-sizing:border-box}body{margin:0;background:#edf1f5;color:#17212b;font:16px/1.6 system-ui,sans-serif}main{max-width:710px;margin:48px auto;padding:0 20px}.note{font-size:13px;color:#566775;margin-bottom:16px}.message{padding:32px;background:white;border:1px solid #dce3e9;border-radius:18px;box-shadow:0 8px 24px #17212b08}h2{font-size:23px;line-height:1.3;margin:0 0 20px}h3{font-size:19px;line-height:1.4;margin-top:26px}hr{border:0;border-top:1px solid #e7ebf0;margin:24px 0}a{color:#176eaa;text-decoration:none}details{background:#f5f7fa;border:1px solid #e8ecf0;border-radius:10px;padding:12px 16px;margin:16px 0}summary{cursor:pointer;font-weight:600}details p{margin:9px 0}ul{padding-left:22px}.actions{display:flex;gap:9px;flex-wrap:wrap;margin-top:20px}.actions a,.actions button{font:600 14px system-ui;padding:12px 16px;border-radius:8px;border:1px solid #ced9e2;background:#f4f7fa;color:#234b67;cursor:pointer}.actions .primary{background:#2481cc;color:white;border-color:#2481cc}footer{font-size:14px;color:#7c8a96;margin-top:24px}@media(max-width:600px){main{margin:20px auto}.message{padding:22px}.actions>*{flex:1;text-align:center}}
</style><main><p class="note">Ko‘rinish namunasi · Telegram klientida shrift va ranglar moslashadi.</p><article class="message">''' + body + '''</article></main></html>'''
    page = page.replace("</style>", ".cover{display:block;width:calc(100% + 64px);max-width:none;margin:-32px -32px 26px;border-radius:18px 18px 0 0}@media(max-width:600px){.cover{width:calc(100% + 44px);margin:-22px -22px 24px}}.benefit{margin:15px 0;padding:12px 16px;border-left:3px solid #2481cc;border-radius:4px 10px 10px 4px;background:#edf5fc;color:#164e79}.benefit p{margin:0}table{width:100%;border-collapse:collapse;font-size:14px}caption{text-align:left;font-weight:600;margin-bottom:9px}td,th{text-align:left;padding:10px 8px;border-bottom:1px solid #edf1f5}tr:nth-child(even){background:#f7f9fb}td:last-child{font-size:12px}a[id]{scroll-margin-top:24px}html{scroll-behavior:smooth}</style>")
    (output / "post_preview.html").write_text(page, encoding="utf-8")
    (output / "post_payload_10_4.json").write_text(json.dumps({"rich_message": {"blocks": blocks}, "html_fallback": fallback}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output / "post_preview.html")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
