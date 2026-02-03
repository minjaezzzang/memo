import pymysql
import hashlib as hl
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

DB = None
cur = None

def parse_database_url(url):
    """DATABASE_URL을 파싱해서 연결 정보 추출"""
    parsed = urlparse(url)
    return {
        'host': parsed.hostname,
        'user': parsed.username,
        'password': parsed.password,
        'database': parsed.path.lstrip('/'),
        'port': parsed.port or 3306
    }

def get_connection():
    global DB, cur
    if DB is None:
        # DATABASE_URL이 있으면 사용 (Railway), 없으면 개별 환경변수 사용 (로컬)
        db_url = os.getenv('DATABASE_URL')
        if db_url:
            db_config = parse_database_url(db_url)
        else:
            db_config = {
                'host': os.getenv('DB_HOST', 'localhost'),
                'user': os.getenv('DB_USER', 'root'),
                'password': os.getenv('DB_PASSWORD', ''),
                'database': os.getenv('DB_NAME', 'memo_app'),
                'port': int(os.getenv('DB_PORT', 3306))
            }
        
        # 디버그: 비밀번호는 마스킹해서 로그에 남김
        masked = db_config.copy()
        if 'password' in masked and masked['password']:
            masked['password'] = '****'
        print(f"[db] connecting with: {masked}")
        try:
            DB = pymysql.connect(**db_config)
            cur = DB.cursor()
        except Exception as e:
            print(f"[db] MySQL connect failed: {e}")
            raise
    return DB, cur

hash_password = lambda passwd: hl.sha256(passwd.encode()).hexdigest()

def add_user(username, password):
    password_hash = hash_password(password)
    DB, cur = get_connection()
    query = "INSERT INTO users (username, password_hash) VALUES (%s, %s)"
    cur.execute(query, (username, password_hash))
    DB.commit()

def verify_user(username, password):
    password_hash = hash_password(password)
    DB, cur = get_connection()
    query = "SELECT username, password_hash FROM users WHERE username = %s"
    cur.execute(query, (username,))
    result = cur.fetchone()
    if result and result[1] == password_hash:
        return True
    return False

def add_memo(title, content, username):
    DB, cur = get_connection()
    query = "INSERT INTO memos (title, content, username) VALUES (%s, %s, %s)"
    cur.execute(query, (title, content, username))
    DB.commit()

def get_memos(username):
    DB, cur = get_connection()
    query = "SELECT id, title, content FROM memos WHERE username = %s ORDER BY created_at DESC"
    cur.execute(query, (username,))
    return cur.fetchall()

def delete_memo(memo_id):
    DB, cur = get_connection()
    query = "DELETE FROM memos WHERE id = %s"
    cur.execute(query, (memo_id,))
    DB.commit()

def delete_user(username):
    DB, cur = get_connection()
    query1 = "DELETE FROM memos WHERE username = %s"
    query2 = "DELETE FROM users WHERE username = %s"
    cur.execute(query1, (username,))
    cur.execute(query2, (username,))
    DB.commit()

def close_db():
    global DB, cur
    if cur:
        cur.close()
    if DB:
        DB.close()
