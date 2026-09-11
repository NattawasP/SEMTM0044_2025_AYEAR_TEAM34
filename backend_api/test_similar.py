from app.services import similarity_service
import time

print("Building all matrices (first call)...")
t0 = time.time()
results = similarity_service.find_similar("ACH-000741", top_n=3)
elapsed = time.time() - t0
print(f"Done in {elapsed:.1f}s")

if results:
    for r in results:
        ach = r["ach_id"]
        sim = r["similarity"]
        print(f"  {ach}: {sim:.4f}")
else:
    print("  No results returned")
