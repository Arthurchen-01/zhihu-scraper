import requests
import sys

sys.stdout.reconfigure(encoding="utf-8")

HOST = "38.76.206.7"
domains = [
    "reg.samuraiguan.cloud",
    "topup.samuraiguan.cloud",
    "probe.samuraiguan.cloud",
    "lt.samuraiguan.cloud",
    "ds.samuraiguan.cloud"
]

for d in domains:
    headers = {"Host": d}
    try:
        r = requests.get(f"http://{HOST}", headers=headers, auth=("admin", "39TF6xMH52yC"), timeout=5)
        print(f"Host: {d} -> HTTP {r.status_code} ({len(r.text)} bytes)")
    except Exception as e:
        print(f"Host: {d} -> Failed: {e}")
