"""
Chạy script này trong thư mục gốc project:
  python3 fix_titles.py
"""
import os, re, sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'app.db')

if not os.path.exists(DB_PATH):
    print(f"❌ Không tìm thấy DB tại: {DB_PATH}")
    exit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT id, title FROM conversations")
rows = cur.fetchall()

fixed = 0
for cid, title in rows:
    if not title or '=== HƯỚNG DẪN' not in title:
        continue
    # Xóa toàn bộ IMAGE_GUIDE, lấy phần text thuần trước đó (nếu có)
    clean = re.sub(r'\s*===\s*HƯỚNG DẪN PHÂN TÍCH ẢNH\s*===[\s\S]*', '', title).strip()
    new_title = clean if clean else '📷 Phân tích ảnh giao diện'
    cur.execute("UPDATE conversations SET title = ? WHERE id = ?", (new_title, cid))
    print(f"  ✅ id={cid}: '{title[:40]}...' → '{new_title}'")
    fixed += 1

conn.commit()
conn.close()
print(f"\nHoàn tất: đã fix {fixed} conversation(s).")
