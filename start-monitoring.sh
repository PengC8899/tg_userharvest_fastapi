#!/bin/bash

# 启动监控服务脚本
# Usage: ./start-monitoring.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_info "启动监控服务..."

# 检查是否存在监控配置
if [[ ! -f "monitoring/prometheus.yml" ]]; then
    log_error "监控配置文件不存在: monitoring/prometheus.yml"
    exit 1
fi

# 创建必要的目录
mkdir -p monitoring/grafana/provisioning

# 启动完整服务栈（包含监控）
log_info "使用完整配置启动所有服务..."
docker-compose -f docker-compose.full.yml --env-file .env.prod up -d

# 等待服务启动
log_info "等待服务启动..."
sleep 15

# 检查服务状态
log_info "检查服务状态..."
docker-compose -f docker-compose.full.yml ps

# 显示访问地址
log_info "服务启动完成！"
log_info "访问地址："
log_info "  主应用: http://localhost:8000"
log_info "  Grafana: http://localhost:3000 (admin/admin)"
log_info "  Prometheus: http://localhost:9090"
log_info "  Node Exporter: http://localhost:9100"
log_info "  cAdvisor: http://localhost:8080"

log_info "查看日志: docker-compose -f docker-compose.full.yml logs -f"