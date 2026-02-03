USE memo_app;
CREATE TABLE IF NOT EXISTS memos
(
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    username VARCHAR(50),
    FOREIGN KEY (username) REFERENCES users(username)
);