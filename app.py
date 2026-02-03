from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import db
import os
import json
import requests
import hashlib
from dotenv import load_dotenv
from urllib.parse import urlencode, parse_qs
from urllib.request import urlopen

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Google OAuth 설정
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:14444/auth/google/callback')
GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v1/userinfo'
SCOPES = ['openid', 'email', 'profile']

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if db.verify_user(username, password):
            session['username'] = username
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    else:
        username = request.form['username']
        password = request.form['password']
        db.add_user(username, password)
        return redirect(url_for('login', registered='1'))
@app.route('/logout')
def logout():
    if 'username' in session:
        session.pop('username')
    else:
        return redirect(url_for('login'), 403)
    return redirect(url_for('home'))

@app.route('/auth/google')
def auth_google():
    """Google OAuth 로그인 시작"""
    if not GOOGLE_CLIENT_ID or GOOGLE_CLIENT_ID == 'YOUR_GOOGLE_CLIENT_ID':
        return render_template('login.html', error='Google OAuth가 설정되지 않았습니다.')
    
    # OAuth 상태 토큰 생성 (CSRF 방지)
    import secrets
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    
    # Google 인증 URL 생성
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'state': state,
        'access_type': 'offline',
        'prompt': 'consent'  # 항상 동의 화면 표시
    }
    
    authorization_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    print(f"[OAuth] Redirecting to: {authorization_url}")
    print(f"[OAuth] Client ID: {GOOGLE_CLIENT_ID}")
    print(f"[OAuth] Redirect URI: {GOOGLE_REDIRECT_URI}")
    
    return redirect(authorization_url)

@app.route('/auth/google/callback')
def auth_google_callback():
    """Google OAuth 콜백 처리"""
    # CSRF 토큰 검증
    state = request.args.get('state')
    session_state = session.get('oauth_state')
    
    if not state or state != session_state:
        return render_template('login.html', error='인증 상태가 일치하지 않습니다.')
    
    # 인증 코드 확인
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return render_template('login.html', error=f'Google 인증 실패: {error}')
    
    if not code:
        return render_template('login.html', error='인증 코드가 없습니다.')
    
    try:
        # 토큰 요청
        token_params = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': GOOGLE_REDIRECT_URI
        }
        
        token_response = requests.post(GOOGLE_TOKEN_URL, data=token_params)
        
        if token_response.status_code != 200:
            return render_template('login.html', error='토큰 획득 실패')
        
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        
        if not access_token:
            return render_template('login.html', error='액세스 토큰 없음')
        
        # 사용자 정보 요청
        headers = {'Authorization': f'Bearer {access_token}'}
        userinfo_response = requests.get(GOOGLE_USERINFO_URL, headers=headers)
        
        if userinfo_response.status_code != 200:
            return render_template('login.html', error='사용자 정보 조회 실패')
        
        user_info = userinfo_response.json()
        
        google_id = user_info.get('id')
        email = user_info.get('email')
        name = user_info.get('name')
        picture = user_info.get('picture')
        
        if not google_id or not email:
            return render_template('login.html', error='필수 사용자 정보 없음')
        
        # 데이터베이스에 사용자 생성 또는 로그인
        username = f"google_{google_id}"
        password_hash = hashlib.sha256(google_id.encode()).hexdigest()
        
        try:
            # 사용자가 존재하는지 확인
            if db.verify_user(username, google_id):
                pass  # 이미 존재
            else:
                # 새 사용자 생성
                db.add_user(username, google_id)
        except Exception as e:
            # 사용자가 이미 존재할 수 있음
            print(f"User creation/verification: {e}")
        
        # 세션 설정
        session['username'] = username
        session['email'] = email
        session['name'] = name
        session['picture'] = picture
        session['oauth_provider'] = 'google'
        
        # 상태 토큰 제거
        session.pop('oauth_state', None)
        
        return redirect(url_for('home'))
        
    except Exception as e:
        print(f"OAuth callback error: {e}")
        return render_template('login.html', error=f'인증 중 오류 발생: {str(e)}')

@app.post('/memo')
def add_memo():
    if 'username' not in session:
        return redirect(url_for('login'), 403)
    title = request.form['title']
    content = request.form['content']
    username = session['username']
    db.add_memo(title, content, username)
    return redirect(url_for('home'))

@app.get('/api/memos')
def api_get_memos():
    if 'username' not in session:
        return jsonify([])
    username = session['username']
    memos = db.get_memos(username)
    return jsonify([{
        'id': memo[0],
        'title': memo[1],
        'content': memo[2]
    } for memo in memos])

@app.route('/memos')
def view_memos():
    if 'username' not in session:
        return redirect(url_for('login'), 403)
    username = session['username']
    memos = db.get_memos(username)
    return render_template('memos.html', memos=memos)
@app.post('/memo/delete/<int:memo_id>')
def delete_memo(memo_id):
    if 'username' not in session:
        return redirect(url_for('login'), 403)
    db.delete_memo(memo_id)
    return redirect(url_for('view_memos'))
@app.post('/delete_account')
def delete_account():
    if 'username' not in session:
        return redirect(url_for('login'), 403)
    username = session['username']
    db.delete_user(username)
    session.pop('username')
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=os.getenv('DEBUG', False), host='0.0.0.0', port=14444)