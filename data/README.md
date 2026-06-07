# Data Folder

โครงสร้างและที่มาของข้อมูลทั้งหมดในโปรเจกต์ CellLineSelector

## โครงสร้าง

```
data/
├── raw/          ไฟล์ดั้งเดิมจากแหล่งดาวน์โหลด ห้ามแก้
│   ├── depmap_25Q2/
│   ├── ccle_proteomics_2020/
│   └── hpa/
├── interim/      ไฟล์ระหว่างการประมวลผล
└── processed/    ไฟล์สุดท้ายที่พร้อมใช้ใน pipeline
```

## ไฟล์ใน raw/

### depmap_25Q2/ — DepMap quarterly release 25Q2

ดาวน์โหลดจาก [depmap.org/portal/download/all](https://depmap.org/portal/download/all/)
(ต้องสมัครสมาชิกฟรีก่อน)

| ไฟล์ | ขนาด | ใช้ทำอะไร |
|---|---|---|
| `Model.csv` | 679 KB | metadata ของ 2,116 cell lines + DepMap ↔ CCLE bridge |

### ccle_proteomics_2020/ — Nusinow et al. 2020 CCLE Proteomics

ดาวน์โหลดจาก [Gygi Lab Harvard](https://gygi.hms.harvard.edu/publications/ccle.html)
(ไม่ต้องสมัครสมาชิก)

Citation: Nusinow et al., Cell 2020, doi:10.1016/j.cell.2019.12.023

| ไฟล์ | ขนาด | ใช้ทำอะไร |
|---|---|---|
| `protein_quant_current_normalized.csv` | 68 MB | matrix หลัก protein × cell line (12,755 × 378) |
| `Table_S1_Sample_Information.xlsx` | 28 KB | mapping ชื่อ cell line ↔ TenPx plex |

### hpa/ — Human Protein Atlas

ดาวน์โหลดจาก [proteinatlas.org/about/download](https://www.proteinatlas.org/about/download)

| ไฟล์ | ขนาด | ใช้ทำอะไร |
|---|---|---|
| `HPA.tsv` | 6.9 KB | ตัวอย่าง gene summary (1 ยีน) สำหรับเรียนรู้ schema |

## Pinned versions

| Source | Release | Date downloaded |
|---|---|---|
| DepMap | 25Q2 | 2026-06-06 |
| CCLE Proteomics | Nusinow 2020 | 2026-06-06 |
| HPA | v23 | 2026-06-06 |

## กฎสำคัญ

1. **ไม่ commit ลง git** — ดูใน `.gitignore`
2. **ห้ามแก้ไฟล์ใน raw/** — เป็น immutable source
3. **ทุกการประมวลผล save ใน processed/** — ผ่าน script ที่ reproducible
4. **pin version ของทุก dataset** — แก้ในตารางข้างบนเมื่ออัปเดต
