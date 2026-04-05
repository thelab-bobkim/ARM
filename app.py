from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

# [환경설정] Genspark Claw 공인 IP 및 다우오피스 정보
CLAW_IP = "4.155.211.143"
D_URL = "https://doas.daouoffice.com"
C_ID = "b1cdf7daf8fef8a3"
C_SEC = "c3e2d3f1ebc9fcb8dbedbbcea7fab8e5"

@app.route('/')
@app.route('/arm-ver2/editor')
def editor():
    # 통합 카드 내역 (법인+개인)
    expenses = [
        {"id": 1, "date": "2026-04-05", "vendor": "포천힐스CC", "amount": 350000, "category": "접대비", "type": "corp", "card": "신한(법인)"},
        {"id": 2, "date": "2026-04-05", "vendor": "현대주유소", "amount": 85000, "category": "유류비", "type": "personal", "card": "국민(개인)"},
        {"id": 3, "date": "2026-04-04", "vendor": "아웃백", "amount": 120000, "category": "식비", "type": "personal", "card": "삼성(개인)"}
    ]
    return render_template('editor.html', expenses=expenses, server_ip=CLAW_IP)

@app.route('/api/daou/sync', methods=['POST'])
def sync():
    headers = {"X-Daou-Client-Id": C_ID, "X-Daou-Client-Secret": C_SEC, "Content-Type": "application/json"}
    try:
        # 월요일 IP 승인 전까지는 403이 예상됨
        res = requests.get(f"{D_URL}/api/alliance/bizplay/v1/user/me", headers=headers, timeout=5)
        return jsonify({"status": res.status_code, "server": CLAW_IP})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    # Claw 환경에서 외부 접속을 허용하기 위해 0.0.0.0으로 바인딩
    app.run(host='0.0.0.0', port=5001, debug=True)
