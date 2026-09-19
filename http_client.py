"""Bitta HTTP mijoz — bot himoyasidan o'ta oladigan.

MUAMMO NIMADA EDI (2026-08-06 da o'lchandi)
-------------------------------------------
Bir qancha sayt Python `requests` ga umuman javob bermasdi, lekin Chrome'da
bemalol ochilardi. Sabab COOKIE emas — TLS BARMOQ IZI.

Har bir HTTP mijoz TLS qo'l berishida shifr to'plamlari, kengaytmalar va
ularning TARTIBINI o'ziga xos ko'rinishda yuboradi (JA3/JA4 barmoq izi).
Python `requests` (OpenSSL) ning izi Chrome nikidan tubdan farq qiladi va
Cloudflare / Akamai Bot Manager buni birinchi paketdayoq aniqlaydi —
User-Agent sarlavhasini qanday yozganingizdan qat'i nazar.

Shu sababli brauzerdan cookie ko'chirish YORDAM BERMAYDI:
  • `cf_clearance` cookie IP + User-Agent + TLS iziga bog'langan. Toshkentdagi
    brauzeringizdan olingan cookie GitHub Actions serveridan yuborilganda
    darrov rad etiladi.
  • Amal qilish muddati odatda 30 daqiqa–24 soat. Bot kuniga bir marta
    ishlaydi, ya'ni cookie ni har kuni qo'lda yangilash kerak bo'lardi —
    avtomatlashtirishning ma'nosi yo'qoladi.
  • Akamai (chevening.org, britishcouncil.org) cookie ga deyarli tayanmaydi,
    u TLS va HTTP/2 kadr tartibiga qaraydi.

YECHIM: `curl_cffi` — Chrome ning aynan o'sha TLS/HTTP2 izini taqlid qiladi.
Cookie ham, brauzer ham, kengaytma ham kerak emas.

O'LCHANGAN NATIJA
-----------------
    sayt                          requests          curl_cffi
    chevening.org                 ReadTimeout   ->  200 (108 KB)
    britishcouncil.org            ConnectionError-> 200 (54 KB)
    opportunitiesforyouth.org     429           ->  200 (254 KB)

Hammasi ham ochilmaydi — `daad.de` va `fellowshipbard.com` TCP darajasida
javob bermaydi (bu bot himoyasi emas, tarmoq/geo to'siq), `eurodesk.eu` va
`scholarshiptab.com` esa 403 da qoladi.

curl_cffi o'rnatilmagan bo'lsa modul jimgina oddiy `requests` ga qaytadi —
bot ishlashdan to'xtamaydi, faqat ba'zi manbalar yopiq qoladi.
"""

import requests as _requests

# Chrome ning taqlid qilinadigan versiyalari
IMPERSONATE_PROFILES = ["chrome124", "chrome120", "safari17_0", "edge101"]
IMPERSONATE = "chrome124"

TIMEOUT = 25

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,uz;q=0.8",
    "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

try:
    from curl_cffi import requests as _curl
    HAS_CURL = True
except Exception:                                 # o'rnatilmagan yoki nosoz
    _curl = None
    HAS_CURL = False


class Client:
    """`requests.Session` ga o'xshash, lekin brauzer izi bilan."""

    def __init__(self, headers: dict = None):
        self._headers = dict(HEADERS)
        if headers:
            self._headers.update(headers)
        self._plain = _requests.Session()
        self._plain.headers.update(self._headers)
        self._curl_session = None
        self._impersonate = IMPERSONATE

        if HAS_CURL:
            try:
                self._curl_session = _curl.Session(headers=self._headers)
            except Exception:
                self._curl_session = None

    # ── ichki ────────────────────────────────────────────────────────────
    def _curl_get(self, url, **kw):
        if self._curl_session is None:
            return None
        for prof in IMPERSONATE_PROFILES:
            try:
                resp = self._curl_session.get(url, impersonate=prof, **kw)
                if resp is not None and resp.status_code != 403:
                    return resp
                if resp is not None and resp.status_code == 403:
                    # Boshqa profil bilan sinab ko'ramiz
                    continue
                return resp
            except TypeError:
                continue
            except Exception:
                continue
        # Barcha profillar o'tmadi — taqlidsiz urinamiz
        try:
            return self._curl_session.get(url, **kw)
        except Exception:
            return None

    # ── ommaviy ──────────────────────────────────────────────────────────
    def get(self, url: str, timeout: int = TIMEOUT, allow_redirects: bool = True, **kw):
        """Avval brauzer izi bilan, bo'lmasa oddiy mijoz bilan."""
        resp = self._curl_get(url, timeout=timeout, allow_redirects=allow_redirects, **kw)
        if resp is not None and resp.status_code not in (403, 503):
            return resp

        try:
            plain_resp = self._plain.get(url, timeout=timeout,
                                         allow_redirects=allow_redirects, **kw)
            return plain_resp if plain_resp is not None else resp
        except Exception:
            return resp

    def post(self, url: str, timeout: int = TIMEOUT, **kw):
        try:
            return self._plain.post(url, timeout=timeout, **kw)
        except Exception:
            return None


# Modul bo'ylab bitta umumiy mijoz — ulanishlar qayta ishlatiladi
session = Client()


def get(url: str, **kw):
    return session.get(url, **kw)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    holat = "bor" if HAS_CURL else "YO'Q - oddiy requests ishlatiladi"
    print(f"curl_cffi: {holat}\n")
    for u in ("https://www.chevening.org/scholarships/",
              "https://opportunitiesforyouth.org/feed/",
              "https://opportunitydesk.org/feed/"):
        r = get(u)
        code = r.status_code if r is not None else "ulanmadi"
        size = len(r.content) if r is not None else 0
        print(f"  {u[:50]:<52} {code}  {size}b")
