#!/bin/bash
# ARM Platform - HTTPS 자동 설정 스크립트
# 사용법: sudo bash setup_https.sh arm-dsti.duckdns.org

set -e

DOMAIN=$1
EMAIL="htkim@dsti.co.kr"
ARM_DIR="/home/ubuntu/ARM"

# ── 입력 검증 ──
if [ -z "$DOMAIN" ]; then
    echo "❌ 도메인을 입력하세요!"
    echo "사용법: sudo bash setup_https.sh [도메인]"
    echo "예시:   sudo bash setup_https.sh arm-dsti.duckdns.org"
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🔐 ARM Platform HTTPS 설정 시작"
echo "  도메인: $DOMAIN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── STEP 1: DNS 확인 ──
echo ""
echo "[ STEP 1 ] DNS 확인 중..."
RESOLVED_IP=$(dig +short $DOMAIN | head -1)
SERVER_IP=$(curl -4 -s ifconfig.me)

echo "  도메인 IP: $RESOLVED_IP"
echo "  서버 IP:   $SERVER_IP"

if [ "$RESOLVED_IP" != "$SERVER_IP" ]; then
    echo "⚠️  경고: DNS가 아직 전파되지 않았습니다."
    echo "   DuckDNS에서 IP를 $SERVER_IP 로 설정했는지 확인하세요."
    echo "   계속 진행하시겠습니까? (y/n)"
    read -r CONTINUE
    if [ "$CONTINUE" != "y" ]; then
        echo "종료합니다."
        exit 1
    fi
else
    echo "  ✅ DNS 확인 완료!"
fi

# ── STEP 2: certbot 설치 ──
echo ""
echo "[ STEP 2 ] Certbot 설치 중..."
apt-get update -qq
apt-get install -y -qq certbot
echo "  ✅ Certbot 설치 완료!"

# ── STEP 3: nginx 임시 중지 ──
echo ""
echo "[ STEP 3 ] Nginx 임시 중지 (인증서 발급을 위해)..."
cd $ARM_DIR
docker compose -f docker-compose.prod.yml stop nginx
echo "  ✅ Nginx 중지 완료"

# ── STEP 4: SSL 인증서 발급 ──
echo ""
echo "[ STEP 4 ] Let's Encrypt SSL 인증서 발급 중..."
certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email $EMAIL \
    -d $DOMAIN \
    --http-01-port 80

echo "  ✅ SSL 인증서 발급 완료!"
echo "  경로: /etc/letsencrypt/live/$DOMAIN/"

# ── STEP 5: nginx.conf 업데이트 ──
echo ""
echo "[ STEP 5 ] nginx.conf HTTPS 설정 적용 중..."
cp $ARM_DIR/nginx/nginx.conf.https.template $ARM_DIR/nginx/nginx.conf
sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" $ARM_DIR/nginx/nginx.conf
echo "  ✅ nginx.conf 업데이트 완료"

# ── STEP 6: .env 파일 도메인 업데이트 ──
echo ""
echo "[ STEP 6 ] 환경변수 업데이트..."
sed -i "s|SERVER_URL=.*|SERVER_URL=https://$DOMAIN|" $ARM_DIR/.env
sed -i "s|SERVER_URL=.*|SERVER_URL=https://$DOMAIN|" $ARM_DIR/.env.prod 2>/dev/null || true
echo "  ✅ SERVER_URL=https://$DOMAIN"

# ── STEP 7: certbot_webroot 디렉토리 생성 ──
mkdir -p /var/www/certbot

# ── STEP 8: Docker 서비스 재시작 ──
echo ""
echo "[ STEP 8 ] 서비스 재시작 중..."
cd $ARM_DIR
docker compose -f docker-compose.prod.yml up -d --force-recreate nginx
sleep 5

# ── STEP 9: 최종 확인 ──
echo ""
echo "[ STEP 9 ] 최종 확인..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -L https://$DOMAIN/health 2>/dev/null || echo "000")
MANIFEST_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://$DOMAIN/manifest.json 2>/dev/null || echo "000")
SW_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://$DOMAIN/sw.js 2>/dev/null || echo "000")

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ ARM Platform HTTPS 설정 완료!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🌐 접속 URL: https://$DOMAIN"
echo "  🔐 SSL 인증서: /etc/letsencrypt/live/$DOMAIN/"
echo "  📱 PWA 설치 가능: HTTPS 적용 완료"
echo ""
echo "  헬스체크: $HTTP_STATUS"
echo "  manifest.json: $MANIFEST_STATUS"
echo "  sw.js: $SW_STATUS"
echo ""

# ── STEP 10: 자동 갱신 cron 설정 ──
echo "[ STEP 10 ] SSL 자동 갱신 설정 (90일마다)..."
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --pre-hook 'cd $ARM_DIR && docker compose -f docker-compose.prod.yml stop nginx' --post-hook 'cd $ARM_DIR && docker compose -f docker-compose.prod.yml start nginx'") | crontab -
echo "  ✅ 자동 갱신 설정 완료 (매일 새벽 3시 확인)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  모바일에서 https://$DOMAIN 접속 후"
echo "  Chrome 메뉴 → '홈 화면에 추가'로 앱 설치!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
