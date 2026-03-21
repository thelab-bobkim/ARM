-- ARM Platform - PostgreSQL 초기화 SQL
-- 실행 순서: 테이블 생성 → 기본 데이터 삽입

-- ─────────────────────────────
-- 1. 카드 정보 테이블
-- ─────────────────────────────
CREATE TABLE IF NOT EXISTS cards (
    id SERIAL PRIMARY KEY,
    card_company VARCHAR(20) NOT NULL,
    card_number_masked VARCHAR(20) NOT NULL,
    card_holder_name VARCHAR(50),
    corp_id VARCHAR(50),
    emp_no VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cards_emp_no ON cards(emp_no);
CREATE INDEX IF NOT EXISTS idx_cards_company ON cards(card_company);

-- ─────────────────────────────
-- 2. 거래 내역 테이블
-- ─────────────────────────────
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    card_id INTEGER REFERENCES cards(id),
    trans_date DATE NOT NULL,
    trans_time VARCHAR(8),
    merchant VARCHAR(200),
    mcc_code VARCHAR(10),
    amount INTEGER NOT NULL,
    vat INTEGER DEFAULT 0,
    installment INTEGER DEFAULT 0,
    approval_no VARCHAR(50) UNIQUE,
    expense_code VARCHAR(50),
    expense_name VARCHAR(100),
    expense_code_source VARCHAR(20),
    daou_approval_id VARCHAR(100),
    daou_approval_status VARCHAR(20) DEFAULT 'PENDING',
    gps_score INTEGER,
    gps_grade VARCHAR(10),
    receipt_image_path VARCHAR(500),
    raw_data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(trans_date);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(daou_approval_status);
CREATE INDEX IF NOT EXISTS idx_transactions_approval ON transactions(daou_approval_id);

-- ─────────────────────────────
-- 3. 가맹점-경비코드 매핑 테이블
-- ─────────────────────────────
CREATE TABLE IF NOT EXISTS merchant_mappings (
    id SERIAL PRIMARY KEY,
    merchant_pattern VARCHAR(200) NOT NULL UNIQUE,
    mcc_code VARCHAR(10),
    expense_code VARCHAR(50) NOT NULL,
    expense_name VARCHAR(100) NOT NULL,
    source VARCHAR(20) DEFAULT 'MANUAL',
    confidence FLOAT DEFAULT 1.0,
    use_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────
-- 4. 경비 코드 마스터
-- ─────────────────────────────
CREATE TABLE IF NOT EXISTS expense_codes (
    code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    account_number VARCHAR(20),
    daou_form_code VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE
);

-- ─────────────────────────────
-- 5. 결재 로그 테이블
-- ─────────────────────────────
CREATE TABLE IF NOT EXISTS approval_logs (
    id SERIAL PRIMARY KEY,
    transaction_id INTEGER REFERENCES transactions(id),
    daou_doc_id VARCHAR(100),
    emp_no VARCHAR(20),
    amount INTEGER,
    status VARCHAR(20) DEFAULT 'PENDING',
    callback_data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_approval_logs_doc ON approval_logs(daou_doc_id);
CREATE INDEX IF NOT EXISTS idx_approval_logs_emp ON approval_logs(emp_no);

-- ─────────────────────────────
-- 기본 경비 코드 데이터 삽입
-- ─────────────────────────────
INSERT INTO expense_codes (code, name, description, account_number, daou_form_code) VALUES
    ('MEAL_EXP',       '식대',           '업무 관련 식비, 커피 등',          '5101', 'CORP_CARD_EXPENSE'),
    ('TRANS_LOCAL',    '대중교통비',     '버스, 지하철 등',                  '5201', 'CORP_CARD_EXPENSE'),
    ('TRANS_TRAIN',    '기차/KTX',       'KTX, ITX, SRT 등 철도 교통비',     '5202', 'CORP_CARD_EXPENSE'),
    ('TRANS_AIR',      '항공비',         '국내외 항공권',                    '5203', 'CORP_CARD_EXPENSE'),
    ('TRANS_TAXI',     '택시비',         '업무용 택시, 카카오T 등',          '5204', 'CORP_CARD_EXPENSE'),
    ('TRANS_FUEL',     '주유비',         '법인차량 주유, 주차비 포함',       '5205', 'CORP_CARD_EXPENSE'),
    ('TRANS_PARKING',  '주차비',         '업무 관련 주차 요금',              '5206', 'CORP_CARD_EXPENSE'),
    ('LODGING_EXP',    '숙박비',         '출장 숙박, 호텔 등',               '5301', 'CORP_CARD_EXPENSE'),
    ('OFFICE_SUPPLY',  '사무용품',       '문구류, 사무용품 구매',            '5401', 'CORP_CARD_EXPENSE'),
    ('EQUIP_PURCHASE', '장비/기기구매',  'IT 장비, 전자기기 등',             '5402', 'CORP_CARD_EXPENSE'),
    ('SW_SERVICE',     '소프트웨어/서비스', '클라우드, 구독 서비스 등',      '5403', 'CORP_CARD_EXPENSE'),
    ('COMM_EXP',       '통신비',         '업무용 통신, 인터넷 비용',         '5501', 'CORP_CARD_EXPENSE'),
    ('MEDICAL_EXP',    '의료비',         '업무 관련 의료, 건강검진 등',      '5601', 'CORP_CARD_EXPENSE'),
    ('EDU_EXP',        '교육비',         '업무 연수, 도서, 세미나 등',       '5701', 'CORP_CARD_EXPENSE'),
    ('WELFARE_EXP',    '복지/문화비',    '임직원 복지, 문화활동 등',         '5801', 'CORP_CARD_EXPENSE'),
    ('OTHER_EXP',      '기타경비',       '위 분류에 해당되지 않는 기타 경비', '5901', 'CORP_CARD_EXPENSE')
ON CONFLICT (code) DO NOTHING;

-- ─────────────────────────────
-- 기본 가맹점 매핑 데이터
-- ─────────────────────────────
INSERT INTO merchant_mappings (merchant_pattern, mcc_code, expense_code, expense_name, source) VALUES
    ('스타벅스',         '5812', 'MEAL_EXP',       '식대',         'MCC_PRESET'),
    ('커피빈',           '5812', 'MEAL_EXP',       '식대',         'MCC_PRESET'),
    ('이디야',           '5812', 'MEAL_EXP',       '식대',         'MCC_PRESET'),
    ('GS칼텍스',         '5541', 'TRANS_FUEL',     '주유비',       'MCC_PRESET'),
    ('SK에너지',         '5541', 'TRANS_FUEL',     '주유비',       'MCC_PRESET'),
    ('현대오일뱅크',     '5541', 'TRANS_FUEL',     '주유비',       'MCC_PRESET'),
    ('KTX',              '4112', 'TRANS_TRAIN',    '기차/KTX',     'MCC_PRESET'),
    ('SRT',              '4112', 'TRANS_TRAIN',    '기차/KTX',     'MCC_PRESET'),
    ('대한항공',         '4511', 'TRANS_AIR',      '항공비',       'MCC_PRESET'),
    ('아시아나',         '4511', 'TRANS_AIR',      '항공비',       'MCC_PRESET'),
    ('제주항공',         '4511', 'TRANS_AIR',      '항공비',       'MCC_PRESET'),
    ('카카오택시',       '4121', 'TRANS_TAXI',     '택시비',       'MCC_PRESET'),
    ('교보문고',         '5943', 'OFFICE_SUPPLY',  '사무용품/도서', 'MCC_PRESET'),
    ('YES24',            '5943', 'OFFICE_SUPPLY',  '사무용품/도서', 'MCC_PRESET'),
    ('쿠팡',             '5999', 'OFFICE_SUPPLY',  '사무용품',     'MCC_PRESET')
ON CONFLICT (merchant_pattern) DO NOTHING;
