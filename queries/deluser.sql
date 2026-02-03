USE memo_app;
DELETE FROM memos WHERE username = %s;
DELETE FROM users WHERE username = %s;