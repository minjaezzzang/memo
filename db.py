import pymysql
import pymysql.err
import pymysql.err
import hashlib as hl
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

DB = None
cur = None
schema_initialized = False

class DBError(Exception):
    """데이터베이스 관련 커스텀 예외"""
    pass

class DBError(Exception):
    """데이터베이스 관련 커스텀 예외"""
    pass

def parse_database_url(url):
    """DATABASE_URL을 파싱해서 연결 정보 추출"""
    parsed = urlparse(url)
    return {
        'host': parsed.hostname,
        'user': "avnadmin",
        'password': parsed.password,
        'database': parsed.path.lstrip('/'),
        'port': parsed.port or 3306
    }

def looks_like_hostname(value):
    if value is None:
        return False
    text = str(value)
    return ('.' in text) or (':' in text)

def normalize_db_config(db_config):
    """환경변수 실수로 host/user가 뒤바뀐 경우 보정"""
    host = db_config.get('host')
    user = db_config.get('user')
    if host and user:
        host_is_host = looks_like_hostname(host)
        user_is_host = looks_like_hostname(user)
        if (not host_is_host) and user_is_host:
            print("[db] ! Detected swapped host/user; auto-correcting")
            db_config['host'], db_config['user'] = user, host
    return db_config

def build_db_config():
    """모든 환경변수 포맷 지원하는 DB 설정 빌드"""
    # 1. DATABASE_URL 형식 지원
    db_url = os.getenv('DATABASE_URL') or os.getenv('MYSQL_URL') or os.getenv('DB_URL')
    if db_url:
        if '://' not in db_url:
            print("[db] ! DATABASE_URL missing scheme; ignoring")
        else:
            return normalize_db_config(parse_database_url(db_url))

    # 2. MYSQL_* 환경변수 (표준)
    if os.getenv('MYSQL_HOST'):
        return normalize_db_config({
            'host': os.getenv('MYSQL_HOST'),
            'user': os.getenv('MYSQL_USER', 'root'),
            'password': os.getenv('MYSQL_PASSWORD', ''),
            'database': os.getenv('MYSQL_DB', 'defaultdb'),
            'port': int(os.getenv('MYSQL_PORT', 3306)),
        })

    # 3. AIVEN_MYSQL_* 환경변수
    if os.getenv('AIVEN_MYSQL_HOST'):
        return normalize_db_config({
            'host': os.getenv('AIVEN_MYSQL_HOST'),
            'user': os.getenv('AIVEN_MYSQL_USER'),
            'password': os.getenv('AIVEN_MYSQL_PASSWORD'),
            'database': os.getenv('AIVEN_MYSQL_DB'),
            'port': int(os.getenv('AIVEN_MYSQL_PORT', 3306)),
        })

    # 4. MYSQLHOST 형식 (Railway 등)
    if os.getenv('MYSQLHOST'):
        return normalize_db_config({
            'host': os.getenv('MYSQLHOST'),
            'user': os.getenv('MYSQLUSER'),
            'password': os.getenv('MYSQLPASSWORD'),
            'database': os.getenv('MYSQLDATABASE'),
            'port': int(os.getenv('MYSQLPORT', 3306)),
        })

    # 5. DB_* 환경변수 (레거시)
    return normalize_db_config({
        'host': os.getenv('DB_HOST', 'localhost'),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'memo_app'),
        'port': int(os.getenv('DB_PORT', 3306)),
    })

def reset_connection():
    """연결 초기화 (재연결 필요할 때)"""
    global DB, cur, schema_initialized
    try:
        if cur:
            cur.close()
        if DB:
            DB.close()
    except:
        pass
    DB = None
    cur = None
    schema_initialized = False

def ensure_schema():
    """필수 테이블/인덱스가 없으면 생성"""
    global DB, cur
    try:
        # users 테이블
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(64) NOT NULL UNIQUE,
                password_hash CHAR(64) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        # memos 테이블
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS memos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                username VARCHAR(64) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_memos_username (username)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        DB.commit()
        print("[db] ✓ Schema ensured")
    except Exception as e:
        print(f"[db] ✗ Schema ensure error: {e}")
        try:
            DB.rollback()
        except Exception:
            pass
        raise DBError(f"스키마 생성 실패: {str(e)}")

def get_connection():
    """데이터베이스 연결 획득"""
    global DB, cur, schema_initialized
    if DB is None:
        db_config = build_db_config()

        # 디버그: 비밀번호는 마스킹해서 로그에 남김
        masked = db_config.copy()
        if 'password' in masked and masked['password']:
            masked['password'] = '****'
        print(f"[db] connecting with: {masked}")
        
        try:
            # 연결 타임아웃 설정
            DB = pymysql.connect(
                host=db_config['host'],
                user=db_config['user'],
                password=db_config['password'],
                database=db_config['database'],
                port=db_config['port'],
                charset='utf8mb4',
                connect_timeout=30,
                read_timeout=30,
                write_timeout=30,
                autocommit=False
            )
            cur = DB.cursor()
            # 연결 확인
            cur.execute("SELECT 1")
            print("[db] ✓ Connection successful!")
            if not schema_initialized:
                ensure_schema()
                schema_initialized = True
        except pymysql.err.OperationalError as e:
            print(f"[db] ✗ Operational error: {e}")
            print(f"[db] Config: {masked}")
            reset_connection()
            raise DBError(f"데이터베이스 연결 실패: {str(e)}")
        except pymysql.err.ProgrammingError as e:
            print(f"[db] ✗ Programming error: {e}")
            reset_connection()
            raise DBError(f"SQL 오류: {str(e)}")
        except Exception as e:
            print(f"[db] ✗ Unexpected error: {type(e).__name__}: {e}")
            reset_connection()
            raise DBError(f"연결 오류: {str(e)}")
    return DB, cur

hash_password = lambda passwd: hl.sha256(passwd.encode()).hexdigest()

def add_user(username, password):
    """사용자 추가"""
    if not username or not password:
        raise DBError("사용자명과 비밀번호는 필수입니다")
    
    password_hash = hash_password(password)
    try:
        DB, cur = get_connection()
        query = "INSERT INTO users (username, password_hash) VALUES (%s, %s)"
        cur.execute(query, (username, password_hash))
        DB.commit()
        print(f"[db] ✓ User added: {username}")
    except pymysql.err.IntegrityError:
        print(f"[db] ! User already exists: {username}")
        raise DBError("이미 존재하는 사용자명입니다")
    except pymysql.err.OperationalError as e:
        print(f"[db] ✗ Operational error: {e}")
        reset_connection()
        raise DBError("데이터베이스 연결 오류")
    except Exception as e:
        print(f"[db] ✗ Add user error: {e}")
        raise DBError(f"사용자 추가 실패: {str(e)}")

def verify_user(username, password):
    """사용자 인증"""
    if not username or not password:
        return False
    
    password_hash = hash_password(password)
    try:
        DB, cur = get_connection()
        query = "SELECT username, password_hash FROM users WHERE username = %s"
        cur.execute(query, (username,))
        result = cur.fetchone()
        
        if result and result[1] == password_hash:
            print(f"[db] ✓ User verified: {username}")
            return True
        print(f"[db] ! Invalid credentials: {username}")
        return False
    except pymysql.err.OperationalError as e:
        print(f"[db] ✗ Operational error: {e}")
        reset_connection()
        return False
    except Exception as e:
        print(f"[db] ✗ Verify error: {e}")
        return False

def add_memo(title, content, username):
    """메모 추가"""
    if not title or not content or not username:
        raise DBError("제목, 내용, 사용자명은 필수입니다")
    
    try:
        DB, cur = get_connection()
        query = "INSERT INTO memos (title, content, username) VALUES (%s, %s, %s)"
        cur.execute(query, (title[:255], content, username))
        DB.commit()
        print(f"[db] ✓ Memo added for user: {username}")
    except pymysql.err.OperationalError as e:
        print(f"[db] ✗ Operational error: {e}")
        reset_connection()
        raise DBError("데이터베이스 연결 오류")
    except Exception as e:
        print(f"[db] ✗ Add memo error: {e}")
        raise DBError(f"메모 추가 실패: {str(e)}")

def get_memos(username):
    """메모 조회"""
    if not username:
        return []
    
    try:
        DB, cur = get_connection()
        query = "SELECT id, title, content FROM memos WHERE username = %s ORDER BY created_at DESC"
        cur.execute(query, (username,))
        results = cur.fetchall()
        print(f"[db] ✓ Got {len(results) if results else 0} memos for user: {username}")
        return results if results else []
    except pymysql.err.OperationalError as e:
        print(f"[db] ✗ Operational error: {e}")
        reset_connection()
        return []
    except Exception as e:
        print(f"[db] ✗ Get memos error: {e}")
        return []

def delete_memo(memo_id):
    """메모 삭제"""
    if not memo_id:
        raise DBError("메모 ID는 필수입니다")
    
    try:
        DB, cur = get_connection()
        query = "DELETE FROM memos WHERE id = %s"
        cur.execute(query, (memo_id,))
        DB.commit()
        print(f"[db] ✓ Memo deleted: {memo_id}")
    except pymysql.err.OperationalError as e:
        print(f"[db] ✗ Operational error: {e}")
        reset_connection()
        raise DBError("데이터베이스 연결 오류")
    except Exception as e:
        print(f"[db] ✗ Delete memo error: {e}")
        raise DBError(f"메모 삭제 실패: {str(e)}")

def delete_user(username):
    """사용자 삭제 (연관 메모 포함)"""
    if not username:
        raise DBError("사용자명은 필수입니다")
    
    try:
        DB, cur = get_connection()
        query1 = "DELETE FROM memos WHERE username = %s"
        query2 = "DELETE FROM users WHERE username = %s"
        
        cur.execute(query1, (username,))
        cur.execute(query2, (username,))
        DB.commit()
        print(f"[db] ✓ User deleted: {username}")
    except pymysql.err.OperationalError as e:
        print(f"[db] ✗ Operational error: {e}")
        reset_connection()
        raise DBError("데이터베이스 연결 오류")
    except Exception as e:
        print(f"[db] ✗ Delete user error: {e}")
        raise DBError(f"사용자 삭제 실패: {str(e)}")

def user_exists(username):
    """사용자 존재 여부 확인"""
    if not username:
        return False
    
    try:
        DB, cur = get_connection()
        query = "SELECT 1 FROM users WHERE username = %s LIMIT 1"
        cur.execute(query, (username,))
        return cur.fetchone() is not None
    except:
        return False

def close_db():
    """데이터베이스 연결 종료"""
    reset_connection()
