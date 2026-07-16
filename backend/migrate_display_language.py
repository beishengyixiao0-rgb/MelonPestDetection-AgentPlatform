from sqlalchemy import text
from app.database.session import SessionLocal

db = SessionLocal()
try:
    db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS display_language VARCHAR(8) DEFAULT 'zh' NOT NULL;"))
    db.commit()
    print("display_language 字段添加成功")
except Exception as e:
    db.rollback()
    print(f"添加失败: {str(e)}")
finally:
    db.close()
