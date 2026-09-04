import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

data = json.loads(open("outputs/person_profiles.json", encoding="utf-8").read())

print(f"Total profiles: {len(data)}")
for i, p in enumerate(data[:15]):
    print(f"\n[{i+1}] {p['person_name']} (账号: {p['main_account']}, 文章数: {p['total_articles']}, 平台: {p['platforms']})")
    print(f"    主要攻击角度: {p['attack_angles']}")
    if p['sample_titles']:
        print(f"    典型标题: {p['sample_titles'][:2]}")
    if p['sample_reasons']:
        print(f"    侵权原因摘要: {p['sample_reasons'][0][:80]}...")
