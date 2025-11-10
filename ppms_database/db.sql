CREATE USER 'ppms_user'@'localhost' IDENTIFIED BY '1234';
GRANT ALL PRIVILEGES ON ppms_db.* TO 'ppms_user'@'localhost';
FLUSH PRIVILEGES;

-- 2-3. 'ppms_db' 데이터베이스 사용
USE ppms_db;

-- 2-4. 'production_schedules' 테이블 생성
CREATE TABLE production_schedules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    prod_year INT NOT NULL,
    prod_month INT NOT NULL,
    prod_week INT NOT NULL,
    line VARCHAR(10) NOT NULL,
    company VARCHAR(100),
    model VARCHAR(100),
    lot VARCHAR(50),
    tb VARCHAR(50),
    start_date VARCHAR(50),
    end_date VARCHAR(50),
    manager VARCHAR(100),
    actual_prod INT DEFAULT 0,
    actual_start_date VARCHAR(50),
    actual_end_date VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
USE ppms_db;
SHOW TABLES;
DESC production_schedules;
SELECT * FROM production_schedules;