USE memo_app;
CREATE TABLE IF NOT EXISTS users
(
    username VARCHAR(50) PRIMARY KEY,
    password_hash VARCHAR(255) NOT NULL
);