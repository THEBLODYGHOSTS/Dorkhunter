#!/usr/bin/env python3
"""
dorkhunter v3 — multi-provider dork aggregator
providers: google, google_gbv, ddg_html, ddg_lite, bing, mojeek, searx (multi)

install:
  pip install curl_cffi beautifulsoup4 lxml fake-useragent

usage:
  python3 dorkhunter.py -d 'inurl:.php?id=' --pages 5
  python3 dorkhunter.py -d 'inurl:.php?id=' --deep
  python3 dorkhunter.py -f dorks.txt --pages 10 --workers 12 -o out.json
"""

import argparse
import base64
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus, unquote, urlparse, parse_qs, urlunparse

try:
    from curl_cffi import requests as cffi
    from curl_cffi.requests.exceptions import RequestException as CffiError
except ImportError:
    sys.exit("[!] pip install curl_cffi")

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("[!] pip install beautifulsoup4 lxml")

try:
    from fake_useragent import UserAgent
    UA = UserAgent()
except Exception:
    UA = None

GOOGLE = "https://www.google.com/search"
IMPERSONATE = ["chrome131", "chrome124", "chrome123", "chrome120", "chrome110"]
COMMON_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Upgrade-Insecure-Requests": "1",
}

SEARX_INSTANCES = [
    "https://searx.be",
    "https://searx.tiekoetter.com",
    "https://priv.au",
    "https://searxng.site",
    "https://opnxng.com",
    "https://search.inetol.net",
    "https://baresearch.org",
    "https://search.hbubli.cc",
    "https://searx.work",
    "https://search.rhscz.eu",
]

PRINT_LOCK = threading.Lock()

def log(m):
    with PRINT_LOCK:
        print(m, flush=True)

def hr(t):
    log(f"\n{'='*12} {t} {'='*12}")

def rand_ua():
    if UA:
        try: return UA.random
        except Exception: pass
    return random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    ])

def sleep_h(a=1.0, b=3.0):
    time.sleep(random.uniform(a, b))

def normalize_url(u):
    try:
        p = urlparse(u)
        scheme = p.scheme.lower()
        host = p.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        path = p.path.rstrip("/") or "/"
        qs = sorted(parse_qs(p.query, keep_blank_values=True).items())
        q = "&".join(f"{k}={v}" for k, vs in qs for v in vs)
        return urlunparse((scheme, host, path, "", q, ""))
    except Exception:
        return u

def is_blocked(html, status):
    low = (html or "").lower()
    if status in (429, 503): return True
    if "unusual traffic" in low: return True
    if "captcha" in low and ("sorry" in low or "recaptcha" in low): return True
    if "our systems have detected" in low: return True
    return False

def unwrap_google(href):
    if not href: return None
    if href.startswith("/url?"):
        qs = parse_qs(urlparse(href).query)
        for k in ("q", "url"):
            if k in qs: return unquote(qs[k][0])
        return None
    return href if href.startswith("http") else None

def unwrap_bing(href):
    if not href: return None
    if "bing.com/ck/a" not in href:
        return href if href.startswith("http") else None
    qs = parse_qs(urlparse(href).query)
    u = qs.get("u", [None])[0]
    if not u: return None
    if u.startswith("a1"): u = u[2:]
    pad = "=" * (-len(u) % 4)
    try:
        d = base64.urlsafe_b64decode(u + pad).decode("utf-8", "ignore")
    except Exception:
        return None
    return d if d.startswith("http") else None

def unwrap_ddg(href):
    if not href: return None
    if "duckduckgo.com/l/" in href:
        qs = parse_qs(urlparse(href).query)
        href = unquote(qs.get("uddg", [href])[0])
    return href if href.startswith("http") else None

# ── providers ──────────────────────────────────────────────────────────────

class BaseProvider:
    name = "base"
    def __init__(self, proxy=None):
        self.proxy = proxy
        self.impersonate = random.choice(IMPERSONATE)
        kwargs = {"impersonate": self.impersonate}
        if proxy:
            kwargs["proxies"] = {"http": proxy, "https": proxy}
        self.session = cffi.Session(**kwargs)
        self.session.headers.update(COMMON_HEADERS)
        self.session.headers["User-Agent"] = rand_ua()

    def search(self, query, pages):
        raise NotImplementedError

    def close(self):
        try: self.session.close()
        except Exception: pass

# ── Google ─────────────────────────────────────────────────────────────────

class GoogleProvider(BaseProvider):
    def __init__(self, proxy=None, basic=False):
        super().__init__(proxy)
        self.basic = basic
        self.name = "google_gbv" if basic else "google"
        try:
            self.session.get("https://www.google.com/", timeout=15)
        except Exception:
            pass

    def search(self, query, pages):
        out, seen = [], set()
        for p in range(pages):
            url = f"{GOOGLE}?q={quote_plus(query)}&start={p*10}&hl=en&num=10"
            if self.basic: url += "&gbv=1"
            log(f"  [{self.name}] page {p+1}")
            try:
                r = self.session.get(url, timeout=25)
            except CffiError as e:
                log(f"  [{self.name}] net {e}")
                return out
            if is_blocked(r.text, r.status_code):
                log(f"  [{self.name}] blocked")
                return out
            soup = BeautifulSoup(r.text, "lxml")
            anchors = []
            for sel in ("div.yuRUbf > a", "div#search a[href^='/url?']",
                        "div.g a[href^='http']", "a[jsname='UWckNb']"):
                anchors.extend(soup.select(sel))
            added = 0
            for a in anchors:
                u = unwrap_google(a.get("href", ""))
                if not u or "google.com" in u: continue
                n = normalize_url(u)
                if n in seen: continue
                seen.add(n)
                t = a.get_text(" ", strip=True) or ""
                out.append((t, u)); added += 1
            log(f"  [{self.name}] +{added} (total {len(out)})")
            if added == 0: break
            if p < pages - 1: sleep_h(2, 5)
        return out

# ── DuckDuckGo (html + lite) ──────────────────────────────────────────────

class DDGProvider(BaseProvider):
    def __init__(self, proxy=None, lite=False):
        super().__init__(proxy)
        self.lite = lite
        self.name = "ddg_lite" if lite else "ddg_html"

    def search(self, query, pages):
        out, seen = [], set()
        for p in range(pages):
            offset = p * 10
            log(f"  [{self.name}] page {p+1} (offset {offset})")
            r = None
            if self.lite:
                try:
                    r = self.session.get(
                        "https://lite.duckduckgo.com/lite/",
                        params={"q": query, "kl": "us-en", "s": offset},
                        timeout=25,
                    )
                except CffiError as e:
                    log(f"  [{self.name}] net {e}")
            else:
                try:
                    r = self.session.post(
                        "https://html.duckduckgo.com/html/",
                        data={"q": query, "kl": "us-en", "s": offset},
                        headers={"Referer": "https://html.duckduckgo.com/"},
                        timeout=25,
                    )
                except CffiError as e:
                    log(f"  [{self.name}] net {e}")
            if not r or r.status_code != 200:
                log(f"  [{self.name}] http {r.status_code if r else 'err'}")
                return out
            soup = BeautifulSoup(r.text, "lxml")
            anchors = soup.select("a.result__a") if not self.lite else soup.select("a.result-link")
            added = 0
            for a in anchors:
                u = unwrap_ddg(a.get("href", ""))
                if not u: continue
                n = normalize_url(u)
                if n in seen: continue
                seen.add(n)
                out.append((a.get_text(" ", strip=True), u)); added += 1
            log(f"  [{self.name}] +{added} (total {len(out)})")
            if added == 0: break
            if p < pages - 1: sleep_h(2, 4)
        return out

# ── Bing ───────────────────────────────────────────────────────────────────

class BingProvider(BaseProvider):
    name = "bing"

    def search(self, query, pages):
        out, seen = [], set()
        for p in range(pages):
            first = p * 10 + 1
            url = (f"https://www.bing.com/search?q={quote_plus(query)}"
                   f"&first={first}&setlang=en-us&cc=US&mkt=en-US&count=10")
            log(f"  [{self.name}] page {p+1}")
            try:
                r = self.session.get(
                    url, timeout=25,
                    headers={"Accept-Language": "en-US,en;q=0.9",
                             "Referer": "https://www.bing.com/"},
                    cookies={"SRCHHPGUSR": "SRCHLANG=en&BRW=W&BRH=S"},
                )
            except CffiError as e:
                log(f"  [{self.name}] net {e}")
                return out
            if r.status_code != 200:
                log(f"  [{self.name}] http {r.status_code}")
                return out
            soup = BeautifulSoup(r.text, "lxml")
            added = 0
            for li in soup.select("li.b_algo"):
                h2 = li.find("h2")
                a = h2.find("a") if h2 else None
                if not a: continue
                u = unwrap_bing(a.get("href", ""))
                if not u: continue
                n = normalize_url(u)
                if n in seen: continue
                seen.add(n)
                out.append((h2.get_text(" ", strip=True), u)); added += 1
            log(f"  [{self.name}] +{added} (total {len(out)})")
            if added == 0: break
            if p < pages - 1: sleep_h(2, 4)
        return out

# ── Mojeek (very scraper-friendly) ────────────────────────────────────────

class MojeekProvider(BaseProvider):
    name = "mojeek"

    def search(self, query, pages):
        out, seen = [], set()
        for p in range(pages):
            offset = p * 10
            url = f"https://www.mojeek.com/search?q={quote_plus(query)}&s={offset}"
            log(f"  [{self.name}] page {p+1}")
            try:
                r = self.session.get(url, timeout=25)
            except CffiError as e:
                log(f"  [{self.name}] net {e}")
                return out
            if r.status_code != 200:
                log(f"  [{self.name}] http {r.status_code}")
                return out
            soup = BeautifulSoup(r.text, "lxml")
            added = 0
            for li in soup.select("ul.results-standard li"):
                a = li.select_one("a.title") or li.select_one("h2 a")
                if not a: continue
                u = a.get("href", "")
                if not u.startswith("http"): continue
                n = normalize_url(u)
                if n in seen: continue
                seen.add(n)
                out.append((a.get_text(" ", strip=True), u)); added += 1
            log(f"  [{self.name}] +{added} (total {len(out)})")
            if added == 0: break
            if p < pages - 1: sleep_h(2, 4)
        return out

# ── SearXNG (aggregator — many engines per instance) ──────────────────────

class SearxInstance(BaseProvider):
    def __init__(self, base, proxy=None):
        super().__init__(proxy)
        self.base = base.rstrip("/")
        self.name = "searx:" + self.base.split("//", 1)[1][:25]

    def search(self, query, pages):
        out, seen = [], set()
        for p in range(pages):
            # searx pagination via pageno
            params = {"q": query, "pageno": p + 1, "language": "en", "safesearch": "0"}
            try:
                r = self.session.get(f"{self.base}/search", params=params, timeout=20)
            except CffiError as e:
                log(f"  [{self.name}] net {e}")
                return out
            if r.status_code != 200:
                log(f"  [{self.name}] http {r.status_code}")
                return out
            soup = BeautifulSoup(r.text, "lxml")
            added = 0
            for art in soup.select("article.result"):
                a = art.select_one("h3 a") or art.select_one("a.url_wrapper") or art.find("a")
                if not a: continue
                u = a.get("href", "")
                if not u.startswith("http"): continue
                n = normalize_url(u)
                if n in seen: continue
                seen.add(n)
                title_el = art.select_one("h3") or a
                out.append((title_el.get_text(" ", strip=True), u)); added += 1
            log(f"  [{self.name}] page {p+1} +{added} (total {len(out)})")
            if added == 0: break
            if p < pages - 1: sleep_h(1, 3)
        return out

# ── searx aggregator (parallel instances) ────────────────────────────────

def run_searx(query, pages, workers=6):
    results = []
    seen = set()
    active = list(SEARX_INSTANCES)
    random.shuffle(active)
    log(f"  [searx] {len(active)} instances")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(SearxInstance(base).search, query, pages): base
                for base in active}
        for fut in as_completed(futs):
            base = futs[fut]
            try:
                res = fut.result()
            except Exception as e:
                log(f"  [searx] {base} err {e}")
                continue
            added = 0
            for t, u in res:
                n = normalize_url(u)
                if n in seen: continue
                seen.add(n)
                results.append((t, u)); added += 1
            if added:
                log(f"  [searx] {base} +{added} (total {len(results)})")
    return results

# ── orchestrator ──────────────────────────────────────────────────────────

def all_providers(proxy, use_searx=True):
    provs = [
        GoogleProvider(proxy=proxy, basic=False),
        GoogleProvider(proxy=proxy, basic=True),
        DDGProvider(proxy=proxy, lite=False),
        DDGProvider(proxy=proxy, lite=True),
        BingProvider(proxy=proxy),
        MojeekProvider(proxy=proxy),
    ]
    return provs

def run_provider(provider, query, pages):
    try:
        return provider.name, provider.search(query, pages)
    except Exception as e:
        log(f"  [{provider.name}] err {e}")
        return provider.name, []
    finally:
        provider.close()

def hunt(query, pages, workers=6, use_searx=True, proxy=None):
    hr(f"DORK: {query}")
    results = []
    seen = set()
    stats = {}

    provs = all_providers(proxy, use_searx=use_searx)

    # parallel providers
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(run_provider, p, query, pages) for p in provs]
        if use_searx:
            futs.append(ex.submit(lambda: ("searx", run_searx(query, pages, workers=workers))))

        for fut in as_completed(futs):
            try:
                name, res = fut.result()
            except Exception as e:
                log(f"[!] provider failed: {e}")
                continue
            stats[name] = len(res)
            added = 0
            for t, u in res:
                n = normalize_url(u)
                if n in seen:
                    continue
                seen.add(n)
                results.append({"title": t, "url": u, "source": name})
                added += 1
            log(f"[{name}] {len(res)} raw -> {added} new")

    hr("AGGREGATED")
    log(f"total unique urls: {len(results)}")
    log("\nper-provider raw counts:")
    for name, count in sorted(stats.items(), key=lambda x: -x[1]):
        log(f"  {name:20s} {count}")

    log("\nresults:")
    for r in results:
        log(f"  [{r['source']:10s}] {r['url']}")
        if r["title"]:
            log(f"       {r['title'][:100]}")
    return results

def main():
    ap = argparse.ArgumentParser(description="dorkhunter v3 — multi-provider aggregator")
    ap.add_argument("-d", "--dork", action="append", help="dork (repeatable)")
    ap.add_argument("-f", "--file", help="file with one dork per line")
    ap.add_argument("-p", "--pages", type=int, default=5, help="pages per provider (default 5)")
    ap.add_argument("-w", "--workers", type=int, default=6, help="parallel providers")
    ap.add_argument("-o", "--out", default="dork_results.json")
    ap.add_argument("--deep", action="store_true", help="pages=15, workers=10")
    ap.add_argument("--no-searx", action="store_true", help="skip searx instances")
    ap.add_argument("--proxy", default=None, help="http(s) proxy url")
    args = ap.parse_args()

    if args.deep:
        args.pages = 15
        args.workers = 10

    dorks = []
    if args.dork:
        dorks = [d.strip() for d in args.dork if d.strip()]
    elif args.file:
        with open(args.file, encoding="utf-8") as f:
            dorks = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    if not dorks:
        sys.exit("[!] give -d or -f")

    log(f"[+] {len(dorks)} dork(s), pages={args.pages}, workers={args.workers}, "
        f"searx={'off' if args.no_searx else 'on'}")

    all_results = {}
    for dork in dorks:
        try:
            res = hunt(dork, args.pages, args.workers,
                       use_searx=not args.no_searx, proxy=args.proxy)
            all_results[dork] = res
        except KeyboardInterrupt:
            break
        except Exception as e:
            log(f"[!] dork failed: {e}")
            all_results[dork] = []

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    total = sum(len(v) for v in all_results.values())
    hr("FINAL")
    log(f"[+] {total} unique urls across {len(all_results)} dork(s)")
    log(f"[+] archived -> {args.out}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
