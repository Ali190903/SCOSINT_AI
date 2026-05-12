"""API endpoint test — phone scan."""
import httpx
import json

r = httpx.post("http://127.0.0.1:8000/api/v1/scan",
               json={"value": "+994501234567", "type": "phone"},
               timeout=30)
d = r.json()
print(f"Status: {d['status']}")
print(f"Findings: {len(d['findings'])}")
for f in d["findings"]:
    print(f"  {f['finding_type']:15s} {f['value']}")
