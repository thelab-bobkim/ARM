import sqlite3
import csv
import io
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
DB_FILE = 'ledger.db'

# 다우오피스 설정 (이미지 e57303 기반)
D_URL = "https://doas.daouoffice.com"
C_ID = "b1cdf7daf8fef8a3"
C_SEC = "c3e2d3f1ebc9fcb8dbedbbcea7fab8e5"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
@app.route('/arm-ver2/editor')
def editor():
    conn = get_db_connection()
    expenses_raw = conn.execute('SELECT * FROM expenses ORDER BY date DESC').fetchall()
    expenses = [dict(row) for row in expenses_raw]
    total_amount = sum(item['amount'] for item in expenses)
    conn.close()
    return render_template('editor.html', expenses=expenses, server_ip="4.155.211.143", total_amount=total_amount)

# [핵심] 다우오피스 일괄 상신 API
@app.route('/api/daou/submit', methods=['POST'])
def submit_to_daou():
    conn = get_db_connection()
    # 상신 대기 중인 모든 내역 조회
    items = conn.execute('SELECT * FROM expenses WHERE status = "미상신"').fetchall()
    
    if not items:
        return jsonify({"status": "error", "message": "상신할 내역이 없습니다."})

    # 다우오피스 결재 양식 생성 (시뮬레이션)
    approval_data = {
        "title": "카드 지출 결의서 (AI 자동 생성)",
        "content": "시스템에 의해 자동으로 분류된 카드 내역입니다.",
        "items": [dict(row) for row in items]
    }
    
    # 실제 API 호출은 월요일 IP 승인 후 활성화
    # response = requests.post(f"{D_URL}/api/v1/approval", json=approval_data, headers={"X-Client-ID": C_ID})
    
    # 상신 성공 시 상태 변경
    conn.execute('UPDATE expenses SET status = "상신완료" WHERE status = "미상신"')
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success", "message": f"{len(items)}건의 내역이 다우오피스로 전송 대기 상태로 전환되었습니다."})

@app.route('/api/upload/csv', methods=['POST'])
def upload_csv():
    file = request.files['file']
    stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
    csv_input = csv.DictReader(stream)
    conn = get_db_connection()
    for row in csv_input:
        conn.execute('INSERT INTO expenses (date, vendor, amount, category, type, card) VALUES (?, ?, ?, ?, ?, ?)',
                     (row['date'], row['vendor'], int(row['amount']), '미분류', row['type'], row['card']))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "CSV 로드가 완료되었습니다."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
