#!/bin/bash

# TG UserHarvest 定时任务设置脚本
# 用于设置自动备份和监控任务

set -e

# 配置
PROJECT_DIR="/opt/tg_userharvest_fastapi"
BACKUP_SCRIPT="${PROJECT_DIR}/scripts/backup.sh"
LOG_DIR="/var/log/tg_userharvest"

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

# 检查是否为root用户
check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "请以root用户身份运行此脚本"
    fi
}

# 创建日志目录
create_log_dir() {
    log "创建日志目录..."
    mkdir -p "$LOG_DIR"
    chmod 755 "$LOG_DIR"
}

# 设置备份定时任务
setup_backup_cron() {
    log "设置备份定时任务..."
    
    # 创建临时cron文件
    TEMP_CRON="/tmp/tg_userharvest_cron"
    
    # 获取当前cron任务
    crontab -l > "$TEMP_CRON" 2>/dev/null || true
    
    # 移除旧的TG UserHarvest相关任务
    sed -i '/# TG UserHarvest/d' "$TEMP_CRON" 2>/dev/null || true
    sed -i '/tg_userharvest/d' "$TEMP_CRON" 2>/dev/null || true
    
    # 添加新的定时任务
    cat >> "$TEMP_CRON" << EOF

# TG UserHarvest 自动备份任务
# 每天凌晨2点执行日备份
0 2 * * * $BACKUP_SCRIPT daily >> $LOG_DIR/backup.log 2>&1

# 每周日凌晨3点执行周备份
0 3 * * 0 $BACKUP_SCRIPT weekly >> $LOG_DIR/backup.log 2>&1

# 每月1号凌晨4点执行月备份
0 4 1 * * $BACKUP_SCRIPT monthly >> $LOG_DIR/backup.log 2>&1

# TG UserHarvest 日志清理任务
# 每天凌晨1点清理30天前的日志
0 1 * * * find $LOG_DIR -name "*.log" -mtime +30 -delete

# TG UserHarvest 系统监控任务
# 每5分钟检查服务状态
*/5 * * * * cd $PROJECT_DIR && docker-compose ps | grep -q "Up" || echo "\$(date): Services down" >> $LOG_DIR/monitor.log

# TG UserHarvest 磁盘空间检查
# 每小时检查磁盘空间
0 * * * * df -h / | awk 'NR==2{if(\$5+0 > 85) print strftime("%Y-%m-%d %H:%M:%S") ": Disk usage high: " \$5}' >> $LOG_DIR/disk.log

EOF
    
    # 安装新的cron任务
    crontab "$TEMP_CRON"
    rm "$TEMP_CRON"
    
    log "备份定时任务设置完成"
}

# 设置日志轮转
setup_logrotate() {
    log "设置日志轮转..."
    
    cat > /etc/logrotate.d/tg-userharvest << EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        # 重启rsyslog以重新打开日志文件
        systemctl reload rsyslog > /dev/null 2>&1 || true
    endscript
}

# Docker容器日志轮转
/var/lib/docker/containers/*/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    copytruncate
}
EOF
    
    log "日志轮转设置完成"
}

# 创建监控脚本
create_monitor_script() {
    log "创建系统监控脚本..."
    
    cat > "${PROJECT_DIR}/scripts/monitor.sh" << 'EOF'
#!/bin/bash

# TG UserHarvest 系统监控脚本

PROJECT_DIR="/opt/tg_userharvest_fastapi"
LOG_FILE="/var/log/tg_userharvest/monitor.log"

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# 检查Docker服务
check_docker() {
    if ! systemctl is-active --quiet docker; then
        log_message "ERROR: Docker service is not running"
        return 1
    fi
    return 0
}

# 检查应用容器
check_containers() {
    cd "$PROJECT_DIR"
    
    # 检查所有服务是否运行
    if ! docker-compose ps | grep -q "Up"; then
        log_message "ERROR: Some containers are not running"
        docker-compose ps >> "$LOG_FILE"
        return 1
    fi
    
    # 检查Web服务健康状态
    if ! curl -f -s http://localhost:8000/health > /dev/null; then
        log_message "ERROR: Web service health check failed"
        return 1
    fi
    
    return 0
}

# 检查磁盘空间
check_disk_space() {
    USAGE=$(df / | awk 'NR==2{print $5}' | sed 's/%//')
    if [ "$USAGE" -gt 85 ]; then
        log_message "WARNING: Disk usage is ${USAGE}%"
        return 1
    fi
    return 0
}

# 检查内存使用
check_memory() {
    USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    if [ "$USAGE" -gt 90 ]; then
        log_message "WARNING: Memory usage is ${USAGE}%"
        return 1
    fi
    return 0
}

# 主检查函数
main() {
    local errors=0
    
    check_docker || ((errors++))
    check_containers || ((errors++))
    check_disk_space || ((errors++))
    check_memory || ((errors++))
    
    if [ $errors -eq 0 ]; then
        log_message "INFO: All checks passed"
    else
        log_message "ERROR: $errors checks failed"
    fi
    
    return $errors
}

main "$@"
EOF
    
    chmod +x "${PROJECT_DIR}/scripts/monitor.sh"
    log "系统监控脚本创建完成"
}

# 创建健康检查脚本
create_health_check() {
    log "创建健康检查脚本..."
    
    cat > "${PROJECT_DIR}/scripts/health-check.sh" << 'EOF'
#!/bin/bash

# TG UserHarvest 健康检查脚本

PROJECT_DIR="/opt/tg_userharvest_fastapi"
LOG_FILE="/var/log/tg_userharvest/health.log"

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# 检查Web服务
check_web_service() {
    local response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
    if [ "$response" != "200" ]; then
        log_message "ERROR: Web service returned HTTP $response"
        return 1
    fi
    return 0
}

# 检查数据库连接
check_database() {
    cd "$PROJECT_DIR"
    if ! docker-compose exec -T db pg_isready -U postgres > /dev/null 2>&1; then
        log_message "ERROR: Database connection failed"
        return 1
    fi
    return 0
}

# 检查Nginx
check_nginx() {
    if ! curl -s -o /dev/null http://localhost:80; then
        log_message "ERROR: Nginx is not responding"
        return 1
    fi
    return 0
}

# 检查SSL证书
check_ssl_cert() {
    if [ -f "$PROJECT_DIR/ssl/cert.pem" ]; then
        local expiry=$(openssl x509 -enddate -noout -in "$PROJECT_DIR/ssl/cert.pem" | cut -d= -f2)
        local expiry_epoch=$(date -d "$expiry" +%s)
        local current_epoch=$(date +%s)
        local days_left=$(( (expiry_epoch - current_epoch) / 86400 ))
        
        if [ $days_left -lt 30 ]; then
            log_message "WARNING: SSL certificate expires in $days_left days"
            return 1
        fi
    fi
    return 0
}

# 主检查函数
main() {
    local errors=0
    
    check_web_service || ((errors++))
    check_database || ((errors++))
    check_nginx || ((errors++))
    check_ssl_cert || ((errors++))
    
    if [ $errors -eq 0 ]; then
        log_message "INFO: All health checks passed"
    else
        log_message "ERROR: $errors health checks failed"
    fi
    
    return $errors
}

main "$@"
EOF
    
    chmod +x "${PROJECT_DIR}/scripts/health-check.sh"
    log "健康检查脚本创建完成"
}

# 显示设置结果
show_summary() {
    log "定时任务设置完成！"
    echo
    echo "已设置的定时任务："
    echo "- 每天凌晨2点：日备份"
    echo "- 每周日凌晨3点：周备份"
    echo "- 每月1号凌晨4点：月备份"
    echo "- 每天凌晨1点：清理30天前的日志"
    echo "- 每5分钟：检查服务状态"
    echo "- 每小时：检查磁盘空间"
    echo
    echo "日志文件位置："
    echo "- 备份日志: $LOG_DIR/backup.log"
    echo "- 监控日志: $LOG_DIR/monitor.log"
    echo "- 健康检查日志: $LOG_DIR/health.log"
    echo "- 磁盘检查日志: $LOG_DIR/disk.log"
    echo
    echo "查看当前定时任务："
    echo "crontab -l"
    echo
    echo "手动执行脚本："
    echo "- 备份: $BACKUP_SCRIPT [daily|weekly|monthly]"
    echo "- 监控: ${PROJECT_DIR}/scripts/monitor.sh"
    echo "- 健康检查: ${PROJECT_DIR}/scripts/health-check.sh"
}

# 主函数
main() {
    log "开始设置TG UserHarvest定时任务..."
    
    check_root
    create_log_dir
    setup_backup_cron
    setup_logrotate
    create_monitor_script
    create_health_check
    show_summary
    
    log "定时任务设置完成！"
}

main "$@"