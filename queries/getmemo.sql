USE memo_app;
SELECT id, title, content FROM memos WHERE username = %s ORDER BY created_at DESC;