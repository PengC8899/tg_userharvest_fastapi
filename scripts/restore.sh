#!/bin/bash

# TG UserHarvest 数据恢复脚本
# 用法: ./restore.sh <backup_file>

set -e

# 配置
PROJECT_DIR="/opt/tg_userharvest_fastapi"
BACKUP_FILE="$1"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# 显示使用说明
show_usage() {
    echo "用法: $0 <backup_file>"
    echo "示例: $0 /opt/tg_userharvest_backups/tg_userharvest_daily_20240101_120000.tar.gz"
    exit 1
}

# 检查参数
check_params() {
    if [ -z "$BACKUP_FILE" ]; then
        error "请指定备份文件"
        show_usage
    fi
    
    if [ ! -f "$BACKUP_FILE" ]; then
        error "备份文件不存在: $BACKUP_FILE"
    fi
}

# 检查依赖
check_dependencies() {
    log "检查依赖工具..."
    
    if ! command -v docker &> /dev/null; then
        error "Docker 未安装或不在PATH中"
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose 未安装或不在PATH中"
    fi
}

# 确认恢复操作
confirm_restore() {
    echo -e "${YELLOW}警告: 此操作将覆盖现有数据！${NC}"
    echo "备份文件: $BACKUP_FILE"
    echo "目标目录: $PROJECT_DIR"
    echo
    read -p "确定要继续恢复吗？(yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log "恢复操作已取消"
        exit 0
    fi
}

# 停止服务
stop_services() {
    log "停止应用服务..."
    
    cd "$PROJECT_DIR"
    
    if [ -f "docker-compose.yml" ]; then
        docker-compose down
        log "服务已停止"
    else
        warn "docker-compose.yml 不存在，跳过服务停止"
    fi
}

# 解压备份文件
extract_backup() {
    log "解压备份文件..."
    
    TEMP_DIR="/tmp/tg_userharvest_restore_$(date +%s)"
    mkdir -p "$TEMP_DIR"
    
    tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"
    
    # 查找解压后的目录
    BACKUP_DIR=$(find "$TEMP_DIR" -maxdepth 1 -type d -name "tg_userharvest_*" | head -1)
    
    if [ -z "$BACKUP_DIR" ]; then
        error "无法找到备份目录"
    fi
    
    log "备份文件已解压到: $BACKUP_DIR"
}

# 恢复数据库
restore_database() {
    log "恢复数据库..."
    
    if [ ! -f "$BACKUP_DIR/database.sql" ]; then
        warn "数据库备份文件不存在，跳过数据库恢复"
        return
    fi
    
    cd "$PROJECT_DIR"
    
    # 启动数据库服务
    docker-compose up -d db
    
    # 等待数据库启动
    log "等待数据库启动..."
    sleep 10
    
    # 从环境变量文件读取数据库配置
    if [ -f ".env.prod" ]; then
        source .env.prod
    else
        error ".env.prod 文件不存在"
    fi
    
    # 恢复数据库
    docker-compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$BACKUP_DIR/database.sql"
    
    if [ $? -eq 0 ]; then
        log "数据库恢复完成"
    else
        error "数据库恢复失败"
    fi
}

# 恢复应用数据
restore_app_data() {
    log "恢复应用数据..."
    
    if [ -d "$BACKUP_DIR/data" ]; then
        # 备份现有数据
        if [ -d "$PROJECT_DIR/data" ]; then
            mv "$PROJECT_DIR/data" "$PROJECT_DIR/data.backup.$(date +%s)"
        fi
        
        cp -r "$BACKUP_DIR/data" "$PROJECT_DIR/"
        log "应用数据恢复完成"
    else
        warn "备份中没有应用数据，跳过"
    fi
}

# 恢复配置文件
restore_configs() {
    log "恢复配置文件..."
    
    # 恢复Nginx配置
    if [ -d "$BACKUP_DIR/nginx" ]; then
        if [ -d "$PROJECT_DIR/nginx" ]; then
            mv "$PROJECT_DIR/nginx" "$PROJECT_DIR/nginx.backup.$(date +%s)"
        fi
        cp -r "$BACKUP_DIR/nginx" "$PROJECT_DIR/"
        log "Nginx配置恢复完成"
    fi
    
    # 恢复监控配置
    if [ -d "$BACKUP_DIR/monitoring" ]; then
        if [ -d "$PROJECT_DIR/monitoring" ]; then
            mv "$PROJECT_DIR/monitoring" "$PROJECT_DIR/monitoring.backup.$(date +%s)"
        fi
        cp -r "$BACKUP_DIR/monitoring" "$PROJECT_DIR/"
        log "监控配置恢复完成"
    fi
}

# 恢复SSL证书
restore_ssl() {
    log "恢复SSL证书..."
    
    if [ -d "$BACKUP_DIR/ssl" ]; then
        if [ -d "$PROJECT_DIR/ssl" ]; then
            mv "$PROJECT_DIR/ssl" "$PROJECT_DIR/ssl.backup.$(date +%s)"
        fi
        cp -r "$BACKUP_DIR/ssl" "$PROJECT_DIR/"
        log "SSL证书恢复完成"
    else
        warn "备份中没有SSL证书，跳过"
    fi
}

# 启动服务
start_services() {
    log "启动应用服务..."
    
    cd "$PROJECT_DIR"
    
    docker-compose up -d
    
    # 等待服务启动
    log "等待服务启动..."
    sleep 15
    
    # 检查服务状态
    if docker-compose ps | grep -q "Up"; then
        log "服务启动成功"
    else
        error "服务启动失败"
    fi
}

# 清理临时文件
cleanup() {
    log "清理临时文件..."
    
    if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
        log "临时文件清理完成"
    fi
}

# 验证恢复
verify_restore() {
    log "验证恢复结果..."
    
    cd "$PROJECT_DIR"
    
    # 检查数据库连接
    if docker-compose exec -T db pg_isready -U postgres > /dev/null 2>&1; then
        log "数据库连接正常"
    else
        warn "数据库连接异常"
    fi
    
    # 检查Web服务
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log "Web服务正常"
    else
        warn "Web服务异常"
    fi
    
    log "恢复验证完成"
}

# 生成恢复报告
generate_report() {
    log "生成恢复报告..."
    
    REPORT_FILE="$PROJECT_DIR/restore_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$REPORT_FILE" << EOF
TG UserHarvest 恢复报告
======================

恢复时间: $(date)
备份文件: $BACKUP_FILE
目标目录: $PROJECT_DIR

恢复内容:
- PostgreSQL 数据库
- 应用数据文件
- 配置文件
- SSL证书

恢复状态: 成功

注意事项:
- 原有数据已备份为 *.backup.* 文件
- 请检查应用功能是否正常
- 如有问题，可使用备份文件回滚

EOF

    log "恢复报告生成完成: $REPORT_FILE"
}

# 主函数
main() {
    log "开始数据恢复..."
    
    check_params
    check_dependencies
    confirm_restore
    stop_services
    extract_backup
    restore_database
    restore_app_data
    restore_configs
    restore_ssl
    start_services
    verify_restore
    cleanup
    generate_report
    
    log "数据恢复完成！"
    log "请检查应用功能是否正常"
}

# 设置清理陷阱
trap cleanup EXIT

# 执行主函数
main "$@"