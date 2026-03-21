#!/usr/bin/env bash
# ARM Platform - AWS Lightsail 최초 서버 설정 스크립트
# 실행: chmod +x scripts/server_setup.sh && sudo ./scripts/server_setup.sh

set -e

echo "🚀 ARM Platform 서버 설정 시작"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. 시스템 업데이트
echo "📦 시스템 업데이트..."
apt-get update -qq && apt-get upgrade -y -qq

# 2. Docker 설치
echo "🐳 Docker 설치..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker ubuntu
    systemctl enable docker
    systemctl start docker
fi

# 3. Docker Compose 설치
echo "🐳 Docker Compose 설치..."
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# 4. Git 설치 및 저장소 클론
echo "📁 저장소 클론..."
apt-get install -y -qq git
if [ ! -d "/home/ubuntu/ARM" ]; then
    git clone https://github.com/thelab-bobkim/ARM /home/ubuntu/ARM
    chown -R ubuntu:ubuntu /home/ubuntu/ARM
fi

# 5. Certbot (Let's Encrypt) 설치
echo "🔒 Certbot 설치..."
apt-get install -y -qq certbot

# 6. 방화벽 설정
echo "🔥 방화벽 설정..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 서버 설정 완료!"
echo ""
echo "다음 단계:"
echo "  1. /home/ubuntu/.env.prod 파일 생성 (cp .env.example .env.prod)"
echo "  2. API 키 입력"
echo "  3. docker-compose -f docker-compose.prod.yml up -d"
echo ""
echo "도메인이 있다면:"
echo "  certbot certonly --webroot -w /var/www/certbot -d yourdomain.com"
