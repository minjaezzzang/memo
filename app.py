from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import db
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

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
        return redirect(url_for('login'))
@app.route('/logout')
def logout():
    if 'username' in session:
        session.pop('username')
    else:
        return redirect(url_for('login'), 403)
    return redirect(url_for('home'))
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