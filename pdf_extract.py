# import subprocess
# import sys
# subprocess.check_call([sys.executable, "-m", "pip", "install", "pymupdf"], stdout=subprocess.DEVNULL)

import fitz  # PyMuPDF
import json
import os

pdf_path = r"F:\TwinCAT\Documents\倍福CX控制器官方资料\Manual-TC1000-TwinCAT3-ADS.NET-V7.pdf"
out_dir = r"F:\TwinCAT\Documents\倍福CX控制器官方资料\tc1000_temp_parts"
os.makedirs(out_dir, exist_ok=True)

doc = fitz.open(pdf_path)
total = len(doc)
print(f"总页数: {total}")

# 分成 5 部分
chunk = total // 5 + 1
parts = []
for i in range(5):
    start = i * chunk
    end = min(start + chunk, total)
    if start >= total:
        break
    parts.append((start, end))

for idx, (start, end) in enumerate(parts):
    out_path = os.path.join(out_dir, f"part{idx+1}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# TC1000 TwinCAT3 ADS.NET V7 - 第 {idx+1} 部分\n")
        f.write(f"# 页码范围: {start+1} - {end}\n\n")
        for page_num in range(start, end):
            page = doc[page_num]
            text = page.get_text("text")
            f.write(f"\n## 第 {page_num+1} 页\n\n")
            f.write(text)
    print(f"已导出: {out_path} ({end-start} 页)")

print("全部完成!")
