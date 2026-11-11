"""Offline validation for the Bot API 10.4 subset emitted by NovaGrants.

This is intentionally a validator for our output, not the entire Telegram API.
"""

from urllib.parse import urlparse

BLOCKS = {
    "heading": ({"type", "text", "size"}, set()),
    "paragraph": ({"type", "text"}, set()),
    "footer": ({"type", "text"}, set()),
    "divider": ({"type"}, set()),
    "list": ({"type", "items"}, set()),
    "details": ({"type", "summary", "blocks"}, {"is_open"}),
    "blockquote": ({"type", "blocks"}, {"credit"}),
    "buttons": ({"type", "buttons"}, {"align"}),
    "anchor": ({"type", "name"}, set()),
    "table": ({"type", "cells"}, {"is_bordered", "is_striped", "is_compact", "caption"}),
    "photo": ({"type", "photo"}, set()),
}
TEXT = {
    "bold": {"type", "text"}, "italic": {"type", "text"},
    "url": {"type", "text", "url"},
    "date_time": {"type", "text", "unix_time", "date_time_format"},
    "custom_emoji": {"type", "custom_emoji_id", "alternative_text"},
    "anchor_link": {"type", "text", "anchor_name"},
}


def valid_web_url(value):
    if not isinstance(value, str):
        return False
    try:
        p = urlparse(value)
        return p.scheme in {"http", "https"} and bool(p.hostname) and not p.username and not p.password
    except ValueError:
        return False


def rich_usage(blocks):
    count = 0
    chars = 0
    def text(value):
        nonlocal chars
        if isinstance(value, str):
            chars += len(value)
        elif isinstance(value, list):
            for part in value:
                text(part)
        elif isinstance(value, dict):
            text(value.get("text", value.get("alternative_text", "")))
    def walk(items):
        nonlocal count
        for block in items:
            count += 1
            text(block.get("text", ""))
            text(block.get("summary", ""))
            text(block.get("caption", ""))
            walk(block.get("blocks", []))
            for item in block.get("items", []):
                count += 1
                walk(item.get("blocks", []))
            for button in block.get("buttons", []):
                text(button.get("text", ""))
            for row in block.get("cells", []):
                count += 1
                for cell in row:
                    text(cell.get("text", ""))
    walk(blocks)
    return count, chars


def validate_blocks(blocks):
    errors = []
    anchors = set()
    anchor_links = []
    def fail(path, message):
        errors.append(f"{path}: {message}")
    def fields(value, required, optional, path):
        if not isinstance(value, dict):
            fail(path, "object required")
            return False
        if required - value.keys():
            fail(path, f"missing fields {sorted(required - value.keys())}")
        if value.keys() - required - optional:
            fail(path, f"unknown fields {sorted(value.keys() - required - optional)}")
        return True
    def text(value, path, depth):
        if depth > 16:
            fail(path, "nesting exceeds 16")
            return
        if isinstance(value, str):
            return
        if isinstance(value, list):
            for i, part in enumerate(value):
                text(part, f"{path}[{i}]", depth + 1)
            return
        if not isinstance(value, dict) or value.get("type") not in TEXT:
            fail(path, "unsupported rich text type")
            return
        t = value["type"]
        fields(value, TEXT[t], set(), path)
        if "text" in value:
            text(value["text"], path + ".text", depth + 1)
        if t == "url" and not valid_web_url(value.get("url")):
            fail(path, "invalid application URL")
        if t == "date_time":
            if type(value.get("unix_time")) is not int:
                fail(path, "unix_time must be an integer")
            if value.get("date_time_format") not in {"r", "d", "D", "t", "T", "dt", "dT", "Dt", "DT", "wDT"}:
                fail(path, "unsupported date format")
        if t == "custom_emoji":
            if not str(value.get("custom_emoji_id", "")).isdigit() or not value.get("alternative_text"):
                fail(path, "custom emoji requires ID and fallback emoji")
        if t == "anchor_link":
            if not isinstance(value.get("anchor_name"), str) or not value["anchor_name"]:
                fail(path, "anchor_name required")
            else:
                anchor_links.append((value["anchor_name"], path))
    def walk(items, path, depth):
        if depth > 16:
            fail(path, "nesting exceeds 16")
            return
        if not isinstance(items, list) or not items:
            fail(path, "non-empty block array required")
            return
        for i, b in enumerate(items):
            p = f"{path}[{i}]"
            if not isinstance(b, dict) or b.get("type") not in BLOCKS:
                fail(p, "unsupported block type")
                continue
            t = b["type"]
            fields(b, *BLOCKS[t], p)
            if t == "photo":
                photo = b.get("photo")
                if not isinstance(photo, dict) or photo.get("type") != "photo" or photo.get("media") != "attach://nova_cover" or set(photo) != {"type", "media"}:
                    fail(p, "only the bundled brand cover attachment is supported")
            for key in ("text", "summary", "caption"):
                if key in b:
                    text(b[key], p + "." + key, depth + 1)
            if t == "anchor":
                name = b.get("name")
                if not isinstance(name, str) or not name or name in anchors:
                    fail(p, "unique anchor name required")
                else:
                    anchors.add(name)
            if t == "table":
                rows = b.get("cells")
                if not isinstance(rows, list) or not rows:
                    fail(p, "table rows required")
                else:
                    for j, row in enumerate(rows):
                        if not isinstance(row, list) or not 1 <= len(row) <= 20:
                            fail(p, "table row must contain 1-20 columns")
                            continue
                        for k, cell in enumerate(row):
                            cp = f"{p}.cells[{j}][{k}]"
                            if not fields(cell, {"align", "valign"}, {"text", "is_header", "colspan", "rowspan"}, cp):
                                continue
                            if cell.get("align") not in {"left", "center", "right"} or cell.get("valign") not in {"top", "middle", "bottom"}:
                                fail(cp, "invalid cell alignment")
                            if "is_header" in cell and cell["is_header"] is not True:
                                fail(cp, "is_header must be True or omitted")
                            if "text" in cell:
                                text(cell["text"], cp + ".text", depth + 1)
                for flag in ("is_bordered", "is_striped", "is_compact"):
                    if flag in b and b[flag] is not True:
                        fail(p, flag + " must be True or omitted")
            if t == "heading" and (type(b.get("size")) is not int or not 1 <= b["size"] <= 6):
                fail(p, "heading size must be 1-6")
            if t == "details":
                if "is_open" in b and b["is_open"] is not True:
                    fail(p, "is_open must be True or omitted")
                walk(b.get("blocks"), p + ".blocks", depth + 1)
            if t == "blockquote":
                walk(b.get("blocks"), p + ".blocks", depth + 1)
                if "credit" in b:
                    text(b["credit"], p + ".credit", depth + 1)
            if t == "list":
                items = b.get("items")
                if not isinstance(items, list) or not items:
                    fail(p, "list items required")
                else:
                    for j, item in enumerate(items):
                        ip = f"{p}.items[{j}]"
                        if fields(item, {"blocks"}, {"has_checkbox", "is_checked", "value", "type"}, ip):
                            walk(item.get("blocks"), ip + ".blocks", depth + 1)
            if t == "buttons":
                buttons = b.get("buttons")
                if not isinstance(buttons, list) or not 1 <= len(buttons) <= 8:
                    fail(p, "buttons must contain 1-8 items")
                    continue
                if b.get("align", "left") not in {"left", "center", "right"}:
                    fail(p, "invalid button alignment")
                for j, button in enumerate(buttons):
                    bp = f"{p}.buttons[{j}]"
                    if not fields(button, {"text"}, {"style", "url", "copy_text"}, bp):
                        continue
                    if not isinstance(button.get("text"), str) or not button["text"].strip():
                        fail(bp, "button text required")
                    if sum(key in button for key in ("url", "copy_text")) != 1:
                        fail(bp, "exactly one action required")
                    if button.get("style", "primary") not in {"primary", "success", "danger"}:
                        fail(bp, "invalid URL/copy button style")
                    if "url" in button and not valid_web_url(button["url"]):
                        fail(bp, "invalid button URL")
                    if "copy_text" in button:
                        copied = button["copy_text"]
                        if not isinstance(copied, dict) or set(copied) != {"text"} or not isinstance(copied.get("text"), str) or not 1 <= len(copied["text"]) <= 256:
                            fail(bp, "copy_text must contain 1-256 characters")
    walk(blocks, "blocks", 0)
    for name, path in anchor_links:
        if name not in anchors:
            fail(path, "anchor target is missing from this message")
    if not errors:
        count, chars = rich_usage(blocks)
        if count > 500:
            fail("blocks", "block count exceeds 500")
        if chars > 32768:
            fail("blocks", "text exceeds 32768 characters")
    return errors
