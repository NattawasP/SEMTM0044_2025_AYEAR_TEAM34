"""
รันไฟล์นี้ 'ครั้งเดียว' เพื่อแปลง CSV เป็น Parquet
จะช่วยให้แอปโหลด/query เร็วขึ้นมากในการรันครั้งต่อๆ ไป
(ไม่กระทบข้อมูลเดิม สร้างไฟล์ .parquet เพิ่มขึ้นมาข้างๆ ไฟล์ .csv เดิม)
"""
import duckdb
import os

# แก้ path ตรงนี้ให้ตรงกับโฟลเดอร์ข้อมูลของคุณ
path = r"C:\Users\Pattanun\OneDrive\Desktop\SEMTM0044_2025_AYEAR_TEAM34\notebooks\03_Mew"

csv_files = [
    "fact_mutations.csv",
    "fact_fusions.csv",
    "dim_cell_lines.csv",
    "dim_genes.csv",
    "hpa.csv",
    "depmap.csv",
    "geo.csv",
    "proteomics.csv",
]

con = duckdb.connect()

for fname in csv_files:
    csv_path = os.path.join(path, fname)
    parquet_path = csv_path.replace(".csv", ".parquet")

    if not os.path.exists(csv_path):
        print(f"ข้าม (ไม่เจอไฟล์): {fname}")
        continue

    print(f"กำลังแปลง {fname} -> {os.path.basename(parquet_path)} ...")
    con.sql(f"""
        COPY (SELECT * FROM '{csv_path}')
        TO '{parquet_path}' (FORMAT PARQUET)
    """)

print("\nเสร็จแล้ว! ไฟล์ .parquet ถูกสร้างในโฟลเดอร์เดียวกับ .csv เดิม")
