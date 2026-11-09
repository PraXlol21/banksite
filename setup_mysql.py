"""Create the moneybook database + app user in local MySQL and write C:\\money-site\\.env.
Uses root credentials from the blood bank project's config (local test install)."""
import importlib.util
import secrets

import pymysql

spec = importlib.util.spec_from_file_location("bbconfig", r"C:\ends wiith this dbms\app\config.py")
cfg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfg)

app_pw = secrets.token_urlsafe(18)
root = pymysql.connect(host=cfg.DB_HOST, port=cfg.DB_PORT, user=cfg.DB_USER, password=cfg.DB_PASSWORD)
with root.cursor() as c:
    c.execute("CREATE DATABASE IF NOT EXISTS moneybook CHARACTER SET utf8mb4")
    c.execute("CREATE USER IF NOT EXISTS 'moneybook'@'localhost' IDENTIFIED BY %s", (app_pw,))
    c.execute("ALTER USER 'moneybook'@'localhost' IDENTIFIED BY %s", (app_pw,))
    c.execute("CREATE USER IF NOT EXISTS 'moneybook'@'127.0.0.1' IDENTIFIED BY %s", (app_pw,))
    c.execute("ALTER USER 'moneybook'@'127.0.0.1' IDENTIFIED BY %s", (app_pw,))
    c.execute("GRANT ALL PRIVILEGES ON moneybook.* TO 'moneybook'@'localhost'")
    c.execute("GRANT ALL PRIVILEGES ON moneybook.* TO 'moneybook'@'127.0.0.1'")
root.commit()
root.close()

with open(r"C:\money-site\.env", "w", encoding="utf-8") as f:
    f.write(
        "# Local MySQL settings for MoneyBook (not committed to git)\n"
        "MYSQL_HOST=127.0.0.1\nMYSQL_PORT=3306\nMYSQL_USER=moneybook\n"
        f"MYSQL_PASSWORD={app_pw}\nMYSQL_DATABASE=moneybook\n"
    )
print("database + user ready, .env written")
