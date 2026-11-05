<!--
  ██████╗  ██████╗ ██████╗ ██╗  ██╗██╗  ██╗██╗   ██╗███╗   ██╗████████╗███████╗██████╗
  ██╔══██╗██╔═══██╗██╔══██╗██║ ██╔╝██║  ██║██║   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗
  ██║  ██║██║   ██║██████╔╝█████╔╝ ███████║██║   ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝
  ██║  ██║██║   ██║██╔══██╗██╔═██╗ ██╔══██║██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗
  ██████╔╝╚██████╔╝██║  ██║██║  ██╗██║  ██║╚██████╔╝██║ ╚████║   ██║   ███████╗██║  ██║
  ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝
-->

<div align="center">

```

```

# `dorkhunter`

### multi-provider google-dork aggregator · TLS-impersonated · zero-browser by default

[![Python](https://img.shields.io/badge/python-3.8%2B-0d1117?style=for-the-badge&logo=python&logoColor=green)](https://python.org)
[![Version](https://img.shields.io/badge/version-3.0-0d1117?style=for-the-badge&logo=git&logoColor=white)]()
[![Engine](https://img.shields.io/badge/engine-curl__cffi%20%2B%20selenium-0d1117?style=for-the-badge&logo=googlechrome&logoColor=cyan)]()
[![Providers](https://img.shields.io/badge/providers-6%20%2B%2010%20searx-0d1117?style=for-the-badge&logo=duckduckgo&logoColor=orange)]()
[![License](https://img.shields.io/badge/license-MIT-0d1117?style=for-the-badge&logo=opensourceinitiative&logoColor=red)]()

**`Build it. Break it. Understand it. Rebuild it better.`**

</div>

---

```bash
root@localhost:~# cat README.md
```

one dork. six engines. ten searx instances. one deduplicated list of everything that leaked.

dorkhunter takes a search operator, fires it at every provider it can reach in parallel, unwraps every redirect wrapper, normalizes every URL, and hands back a clean unique list — with the source engine stamped on each hit.

---

>_ why this exists

Most dork scanners pick one engine. When Google blocks the IP — which it does, every time, on every VPS — the tool dies. dorkhunter doesn't die. It fans out.

Layer What it does
TLS impersonation curl_cffi replays a real Chrome ClientHello — byte-for-byte, not just headers
Parallel providers Google, Google Basic, DDG-HTML, DDG-Lite, Bing, Mojeek, and 10 SearXNG nodes — all at once
Redirect unwrapping google.com/url?q= → real URL · bing.com/ck/a?u=a1<base64> → real URL · duckduckgo.com/l/?uddg= → real URL
Global dedup Scheme + host + path + sorted query. www. stripped. Trailing slashes gone. One hit per real page
Pagination depth 5 pages per provider by default. 15 with --deep. 100+ unique URLs from a single dork
Optional browser selenium-stealth engine with CDP patches, off-screen window, human scroll — for when you need Google itself

---

>_ provider matrix

Provider Wrapper decoded Pagination Needs browser Notes
google /url?q= ✅ ❌ usually blocked from datacenter IPs
google_gbv /url?q= ✅ ❌ basic HTML — survives longer
ddg_html uddg= ✅ ❌ html.duckduckgo.com POST
ddg_lite uddg= ✅ ❌ lite.duckduckgo.com GET
bing ck/a?u=a1 base64url ✅ ❌ forced en-US market, cookie-pinned
mojeek direct ✅ ❌ scraper-friendly, rarely blocks
searx × 10 direct ✅ ❌ each node = 5–10 backends behind it
selenium-stealth /url?q= ✅ ✅ real Chrome, CDP-patched, xvfb ready

SearX is the cheat code. You're not blocked from Google — but a SearX node on a clean residential IP isn't either, and it hands you Google's results anyway.

---

>_ install

```bash
# core — no browser needed
pip install curl_cffi beautifulsoup4 lxml fake-useragent

# optional — only for --engine chrome
pip install selenium
sudo apt install -y google-chrome-stable xvfb
```

---

>_ usage

```bash
# single dork, every provider, 5 pages each
python3 dorkhunter.py -d 'inurl:.php?id='

# deep mode — 15 pages, 10 parallel workers
python3 dorkhunter.py -d 'inurl:.php?id=' --deep

# dork file, custom output
python3 dorkhunter.py -f dorks.txt --pages 10 -o leaks.json

# skip searx — just the native engines
python3 dorkhunter.py -d 'site:target.com ext:env' --no-searx

# residential proxy for the whole session
python3 dorkhunter.py -d 'site:target.com ext:log' --proxy 'http://user:pass@host:8080'

# browser engine, real display via xvfb
xvfb-run -a --server-args="-screen 0 1920x1080x24" \
  python3 dorkhunter.py -d 'site:target.com' --engine chrome
```

flags

flag default meaning
-d, --dork — dork, repeatable
-f, --file — one dork per line, # = comment
-p, --pages 5 pages per provider
-w, --workers 6 parallel providers
-o, --out dork_results.json output file
--deep off forces pages=15, workers=10
--no-searx off native engines only
--engine auto auto · cffi · chrome
--proxy none http://user:pass@host:port
--impersonate random chrome131 · chrome124 · …

---

>_ what the output looks like

```
============ DORK: inurl:.php?id= ============
  [google] page 1
  [google_gbv] page 1
  [ddg_html] page 1 (offset 0)
  [ddg_lite] page 1 (offset 0)
  [bing] page 1
  [mojeek] page 1
  [searx] 10 instances

  [bing] +10 (total 10)
  [mojeek] +15 (total 15)
  [ddg_html] +10 (total 10)
  [searx] https://searx.be +15 (total 15)
  [searx] https://opnxng.com +8 (total 23)
  [google] blocked
  [google_gbv] +10 (total 10)
  ...

============ AGGREGATED ============
total unique urls: 187

per-provider raw counts:
  searx                142
  bing                  20
  mojeek                15
  ddg_html              10
  google_gbv            10
  ddg_lite              10
```

JSON shape

```json
{
  "inurl:.php?id=": [
    {
      "title": "Product page — Example",
      "url": "https://example.com/product.php?id=42",
      "source": "searx"
    }
  ]
}
```

source tells you which engine found it. Dedup happens before serialization — if two providers return the same page, only the first one wins.

---

>_ architecture

```
                 ┌─────────────────────────────┐
                 │        orchestrator          │
                 │   ThreadPoolExecutor (N)     │
                 └──────────────┬──────────────┘
        ┌───────────┬───────────┼───────────┬───────────┐
        ▼           ▼           ▼           ▼           ▼
   ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
   │ Google │  │  DDG   │  │  Bing  │  │ Mojeek │  │ SearX  │
   │ gbv1   │  │ html   │  │ b_algo │  │  std   │  │ × 10   │
   └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘
       │           │           │           │           │
       └───────────┴─────┬─────┴───────────┴───────────┘
                         ▼
              ┌────────────────────┐
              │  normalize + dedup │
              │  scheme/host/path  │
              │  sorted query      │
              └─────────┬──────────┘
                        ▼
                 unique results[]
```

Redirect decoders run inside each provider before normalization:

```python
# google
/url?q=<url>                    -> unquote(q)

# bing  (base64url, a1-prefixed)
/ck/a?...&u=a1<B64URL>          -> b64url_decode(u[2:])

# duckduckgo
/l/?uddg=<url>                  -> unquote(uddg)
```

---

>_ tuning

More providers. Drop instances into SEARX_INSTANCES — there are hundreds. Ten is the sweet spot before timeouts start eating results.

More depth. --pages 20 works, but Bing starts rate-limiting around page 10 and DDG around page 8. SearX nodes tolerate 3–5.

Fingerprint rotation. IMPERSONATE holds the curl_cffi profiles. Add chrome133 / safari18 if your curl_cffi build supports them.

Browser path. --engine chrome needs chromedriver matching your Chrome major version. Grab it from chrome-for-testing and drop it in /usr/local/bin/.

---

>_ roadmap

· --async rewrite with asyncio + httpx
· Yandex + Brave + Startpage native providers
· Automatic SearX node health-checking (drop dead ones)
· Response caching to ~/.cache/dorkhunter/ for repeat dorks
· --diff mode: only show URLs that are new since the last run
· HTML report export

---

>_ the fine print

This is a reconnaissance tool. It queries public search engines for publicly indexed pages. It does not authenticate, does not bypass login walls, and does not touch the target — it only asks search engines what they already know.

Use it on assets you own or have written permission to test. Every URL you feed into a second-stage scanner is your responsibility, not the tool's.

```bash
root@localhost:~# echo "Build it. Break it. Understand it. Rebuild it better."
```

---

<div align="center">

```
     .-.
    (o o)  ·  still here  ·  still watching the wire
    | O \
     \   \
      `~~~'
```

THEBLODYGHOSTS · thenightghost@proton.me · @NulInetwork

based in your localhost — really, i live in the INTERNET

</div>
