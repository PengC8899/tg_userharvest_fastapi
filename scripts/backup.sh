#!/bin/bash

# TG UserHarvest 数据备份脚本
# 用法: ./backup.sh [backup_type]
# backup_type: daily, weekly, monthly (默认: daily)

set -e

# 配置
BACKUP_DIR="/opt/tg_userharvest_backups"
PROJECT_DIR="/opt/tg_userharvest_fastapi"
BACKUP_TYPE="${1:-daily}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="tg_userharvest_${BACKUP_TYPE}_${TIMESTAMP}"

# 保留策略
DAILY_RETENTION=7    # 保留7天的日备份
WEEKLY_RETENTION=4   # 保留4周的周备份
MONTHLY_RETENTION=12 # 保留12个月的月备份

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

# 检查必要的工具
check_dependencies() {
    log "检查依赖工具..."
    
    if ! command -v docker &> /dev/null; then
        error "Docker 未安装或不在PATH中"
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose 未安装或不在PATH中"
    fi
    
    if ! command -v pg_dump &> /dev/null; then
        warn "pg_dump 未找到，将使用Docker容器进行数据库备份"
    fi
}

# 创建备份目录
create_backup_dir() {
    log "创建备份目录: ${BACKUP_DIR}/${BACKUP_NAME}"
    mkdir -p "${BACKUP_DIR}/${BACKUP_NAME}"
}

# 备份数据库
backup_database() {
    log "备份PostgreSQL数据库..."
    
    cd "${PROJECT_DIR}"
    
    # 从环境变量文件读取数据库配置
    if [ -f ".env.prod" ]; then
        source .env.prod
    else
        error ".env.prod 文件不存在"
    fi
    
    # 使用Docker容器备份数据库
    docker-compose exec -T db pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" > "${BACKUP_DIR}/${BACKUP_NAME}/database.sql"
    
    if [ $? -eq 0 ]; then
        log "数据库备份完成"
    else
        error "数据库备份失败"
    fi
}

# 备份应用数据
backup_app_data() {
    log "备份应用数据..."
    
    # 备份用户上传的文件和会话数据
    if [ -d "${PROJECT_DIR}/data" ]; then
        cp -r "${PROJECT_DIR}/data" "${BACKUP_DIR}/${BACKUP_NAME}/"
        log "应用数据备份完成"
    else
        warn "应用数据目录不存在，跳过"
    fi
}

# 备份配置文件
backup_configs() {
    log "备份配置文件..."
    
    # 备份环境变量文件（不包含敏感信息）
    if [ -f "${PROJECT_DIR}/.env.prod" ]; then
        # 创建配置备份，但移除敏感信息
        grep -v -E "(PASSWORD|SECRET|KEY)" "${PROJECT_DIR}/.env.prod" > "${BACKUP_DIR}/${BACKUP_NAME}/env_config.txt"
    fi
    
    # 备份Nginx配置
    if [ -d "${PROJECT_DIR}/nginx" ]; then
        cp -r "${PROJECT_DIR}/nginx" "${BACKUP_DIR}/${BACKUP_NAME}/"
    fi
    
    # 备份监控配置
    if [ -d "${PROJECT_DIR}/monitoring" ]; then
        cp -r "${PROJECT_DIR}/monitoring" "${BACKUP_DIR}/${BACKUP_NAME}/"
    fi
    
    log "配置文件备份完成"
}

# 备份SSL证书
backup_ssl() {
    log "备份SSL证书..."
    
    if [ -d "${PROJECT_DIR}/ssl" ]; then
        cp -r "${PROJECT_DIR}/ssl" "${BACKUP_DIR}/${BACKUP_NAME}/"
        log "SSL证书备份完成"
    else
        warn "SSL证书目录不存在，跳过"
    fi
}

# 压缩备份
compress_backup() {
    log "压缩备份文件..."
    
    cd "${BACKUP_DIR}"
    tar -czf "${BACKUP_NAME}.tar.gz" "${BACKUP_NAME}"
    
    if [ $? -eq 0 ]; then
        rm -rf "${BACKUP_NAME}"
        log "备份压缩完成: ${BACKUP_NAME}.tar.gz"
    else
        error "备份压缩失败"
    fi
}

# 清理旧备份
cleanup_old_backups() {
    log "清理旧备份..."
    
    cd "${BACKUP_DIR}"
    
    case "${BACKUP_TYPE}" in
        "daily")
            find . -name "tg_userharvest_daily_*.tar.gz" -mtime +${DAILY_RETENTION} -delete
            ;;
        "weekly")
            find . -name "tg_userharvest_weekly_*.tar.gz" -mtime +$((WEEKLY_RETENTION * 7)) -delete
            ;;
        "monthly")
            find . -name "tg_userharvest_monthly_*.tar.gz" -mtime +$((MONTHLY_RETENTION * 30)) -delete
            ;;
    esac
    
    log "旧备份清理完成"
}

# 生成备份报告
generate_report() {
    log "生成备份报告..."
    
    BACKUP_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" | cut -f1)
    
    cat > "${BACKUP_DIR}/${BACKUP_NAME}_report.txt" << EOF
TG UserHarvest 备份报告
======================

备份时间: $(date)
备份类型: ${BACKUP_TYPE}
备份文件: ${BACKUP_NAME}.tar.gz
备份大小: ${BACKUP_SIZE}

备份内容:
- PostgreSQL 数据库
- 应用数据文件
- 配置文件
- SSL证书

备份位置: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz

备份状态: 成功
EOF

    log "备份报告生成完成"
}

# 主函数
main() {
    log "开始 ${BACKUP_TYPE} 备份..."
    
    check_dependencies
    create_backup_dir
    backup_database
    backup_app_data
    backup_configs
    backup_ssl
    compress_backup
    cleanup_old_backups
    generate_report
    
    log "备份完成！备份文件: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
}

# 执行主函数
main "$@"