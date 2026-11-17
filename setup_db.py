"""
One-time setup: creates my auth + logging tables (username_*) and adds the API key 123.
Run:  python setup_db.py
"""
import pymysql
import yaml

with open("config.yml", "r") as f:
    config = yaml.safe_load(f)
db_config = config["mysql"]
U = config["username"]

conn = pymysql.connect(**db_config)
cur = conn.cursor()

cur.execute(f"""
CREATE TABLE IF NOT EXISTS `{U}_auth` (
    `uid`     INT AUTO_INCREMENT PRIMARY KEY,
    `token`   VARCHAR(100) NOT NULL UNIQUE,
    `email`   VARCHAR(100) NOT NULL,
    `created` DATETIME DEFAULT CURRENT_TIMESTAMP
)""")

cur.execute(f"""
CREATE TABLE IF NOT EXISTS `{U}_api_logs` (
    `lid`      INT AUTO_INCREMENT PRIMARY KEY,
    `dt`       DATETIME NOT NULL,
    `endpoint` VARCHAR(50) NOT NULL,
    `token`    VARCHAR(100),
    `params`   TEXT,
    `code`     TINYINT,
    `msg`      VARCHAR(255),
    `sqltime`  DOUBLE,
    `ip`       VARCHAR(45)
)""")

cur.execute(f"INSERT IGNORE INTO `{U}_auth` (`token`,`email`) VALUES (%s,%s)",
            ("123", "test@example.com"))
conn.commit()
print(f"Tables `{U}_auth` and `{U}_api_logs` ready; key 123 registered.")
