"""Fetch a wikitext-2 test slice once and cache it to reviews/eval_wikitext.txt.

The accuracy gate fetches wikitext via the datasets-server HTTP API, which is
flaky (rate limits) — this pins the eval text to a file so re-runs are
reproducible and work offline. The gate harness (accuracy_eval.py) prefers the
cache when present.
"""
import json
import os
import urllib.request

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "reviews", "eval_wikitext.txt")

API = ("https://datasets-server.huggingface.co/rows?dataset=Salesforce%2Fwikitext"
       "&config=wikitext-2-raw-v1&split=test&offset=0&length=25")


def main():
    with urllib.request.urlopen(API, timeout=30) as resp:
        data = json.load(resp)
    lines = [r["row"]["text"].strip() for r in data["rows"] if len(r["row"]["text"].strip()) > 80]
    if not lines:
        raise RuntimeError("no long wikitext lines returned")
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"saved {len(lines)} lines to {CACHE}")


if __name__ == "__main__":
    main()
