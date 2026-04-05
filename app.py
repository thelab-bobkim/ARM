from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

# Genspark Claw 전용 설정
# 월요일에 다우오피스에 등록할 IP: 4.155.211.143
D_URL = "https://doas.daouoffice.com"
API_PATH = "/api/alliance/bizplay/v1/user/me"
CLIENT_ID = "b1cdf7daf8fef8a3"
CLIENT_SECRET = "c3e2d3f1ebc9fcb8dbedbbcea7fab8e5"

@app.route('/')
@app.route('/arm-ver2/editor')
def editor():
    # 통합 카드 내역 예시 데이터 (법인+개인)
    expenses = [
        {"date": "2026-04-05", "vendor": "포천힐스CC", "amount": 350000, "category": "접대비", "type": "corp"},
        {"date": "2026-04-05", "vendor": "현대주유소", "amount": 85000, "category": "유류비", "type": "personal"},
        {"date": "2026-04-04", "vendor": "아웃백", "amount": 120000, "category": "식비", "type": "personal"}
    ]
    return render_template('editor.html', expenses=expenses)

@app.route('/api/daou/sync', methods=['POST'])
def sync_data():
    headers = {
        "X-Daou-Client-Id": CLIENT_ID,
        "X-Daou-Client-Secret": CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    try:
        res = requests.get(f"{D_URL}{API_PATH}", headers=headers, timeout=5)
        return jsonify({"status": res.status_code, "data": res.json() if res.status_code == 200 else "Wait for IP approval"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
