#!/usr/bin/env python3
import socket, urllib.request, urllib.error, json, time

HOSTS = ["23.161.169.51", "193.32.204.199"]
PORTS = [22, 80, 81, 443, 3000, 3306, 5000, 8000, 8080, 8081, 8099, 8443, 9000, 9090, 27017]
PATHS = ["/", "/health", "/status", "/api", "/targets", "/targets/list",
         "/targets/export", "/stats", "/export", "/keys", "/batch/actions"]
SECRET = "eEbxNgEEkxlHWN8t5r9XeonXMYX"
HDRS = {"X-Reaper-Key": "actions-runner", "X-Api-Secret": SECRET,
        "User-Agent": "curl/8.5.0", "Accept": "*/*"}


def tcp(h, p, to=4):
    try:
        t0 = time.time()
        s = socket.create_connection((h, p), timeout=to)
        s.close()
        return "open %.2fs" % (time.time() - t0)
    except Exception as e:
        return "fail " + type(e).__name__


def hit(method, url, data=None, to=6):
    try:
        r = urllib.request.Request(url, data=data, headers=HDRS, method=method)
        with urllib.request.urlopen(r, timeout=to) as resp:
            return [resp.status, resp.read(4000).decode("utf-8", "ignore")]
    except urllib.error.HTTPError as e:
        return [e.code, e.read(1500).decode("utf-8", "ignore")]
    except Exception as e:
        return [0, type(e).__name__ + ": " + str(e)[:120]]


def main():
    out = {}
    for h in HOSTS:
        o = {"ports": {}, "http": {}}
        for p in PORTS:
            o["ports"][p] = tcp(h, p)
        for p in [p for p in PORTS if o["ports"][p].startswith("open")]:
            if p not in (80, 81, 8080, 8099):
                continue
            for path in PATHS:
                o["http"]["%d %s" % (p, path)] = hit("GET", "http://%s:%d%s" % (h, p, path))
            o["http"]["%d POST batch" % p] = hit(
                "POST", "http://%s:%d/batch/actions" % (h, p),
                data=json.dumps({"api_secret": SECRET}).encode())
            o["http"]["%d POST c=monami" % p] = hit(
                "POST", "http://%s:%d/?c=monami" % (h, p), data=b"probe=1")
        out[h] = o
    print("=====PULL-START=====")
    print(json.dumps(out, indent=1)[:120000])
    print("=====PULL-END=====")


if __name__ == "__main__":
    main()
