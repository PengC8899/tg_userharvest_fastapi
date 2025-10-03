#!/bin/bash

# VPS部署脚本
# 用于将项目部署到AWS Lightsail VPS

set -e

# 配置变量
VPS_HOST="18.136.159.243"
VPS_USER="ubuntu"
SSH_KEY="LightsailDefaultKey-ap-southeast-1.pem"
REMOTE_DIR="/home/ubuntu/tg_userharvest_fastapi"

echo "🚀 开始部署到VPS: $VPS_HOST"

# 1. 创建远程目录
echo "📁 创建远程目录..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$VPS_USER@$VPS_HOST" "mkdir -p $REMOTE_DIR"

# 2. 传输项目文件
echo "📤 传输项目文件..."
rsync -avz --progress \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='data/' \
    --exclude='sessions/' \
    --exclude='LightsailDefaultKey-ap-southeast-1.pem' \
    -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
    ./ "$VPS_USER@$VPS_HOST:$REMOTE_DIR/"

# 3. 在VPS上执行部署命令
echo "🔧 在VPS上执行部署..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$VPS_USER@$VPS_HOST" << 'EOF'
cd /home/ubuntu/tg_userharvest_fastapi

# 更新系统
sudo apt update

# 安装Docker
if ! command -v docker &> /dev/null; then
    echo "📦 安装Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker ubuntu
    rm get-docker.sh
fi

# 安装Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "📦 安装Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# 创建必要的目录
mkdir -p data sessions ssl

# 设置权限
chmod +x deploy.sh ssl-setup.sh start-monitoring.sh

# 启动服务
echo "🚀 启动Docker服务..."
sudo systemctl start docker
sudo systemctl enable docker

# 构建和启动应用
echo "🏗️ 构建和启动应用..."
docker-compose -f docker-compose.prod.yml up -d --build

echo "✅ 部署完成！"
echo "🌐 应用访问地址: http://18.136.159.243:8000"
echo "📊 监控面板: http://18.136.159.243:3000 (admin/admin)"
EOF

echo "🎉 VPS部署完成！"
echo "🌐 应用地址: http://$VPS_HOST:8000"
echo "📊 监控地址: http://$VPS_HOST:3000"