# Telegram User Harvest - 生产环境部署指南

本指南将帮助您将 Telegram 用户收集系统部署到 VPS 生产环境。

## 🚀 快速部署

### 1. 服务器要求

- **操作系统**: Ubuntu 20.04+ / CentOS 7+ / Debian 10+
- **内存**: 最少 2GB RAM
- **存储**: 最少 10GB 可用空间
- **网络**: 公网 IP 地址
- **域名**: 已解析到服务器 IP 的域名

### 2. 安装依赖

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y docker.io docker-compose git curl openssl

# CentOS/RHEL
sudo yum install -y docker docker-compose git curl openssl
sudo systemctl start docker
sudo systemctl enable docker

# 将用户添加到 docker 组
sudo usermod -aG docker $USER
# 重新登录或运行: newgrp docker
```

### 3. 克隆项目

```bash
git clone <your-repository-url>
cd tg_userharvest_fastapi
```

### 4. 配置环境变量

```bash
# 复制环境变量模板
cp .env.prod .env.prod.local

# 编辑配置文件
nano .env.prod.local
```

**必须配置的变量**:
```bash
# Telegram API (从 https://my.telegram.org 获取)
API_ID=your_api_id
API_HASH=your_api_hash

# 管理员账户
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password

# 域名配置
DOMAIN=your-domain.com
EMAIL=your-email@example.com

# JWT 密钥 (自动生成，或手动设置)
JWT_SECRET_KEY=your_super_secret_jwt_key
```

### 5. 设置 SSL 证书

```bash
# 自动设置 Let's Encrypt SSL 证书
./ssl-setup.sh your-domain.com your-email@example.com
```

### 6. 部署应用

```bash
# 运行部署脚本
./deploy.sh your-domain.com your-email@example.com
```

## 📋 手动部署步骤

如果自动部署脚本遇到问题，可以按以下步骤手动部署：

### 1. 构建 Docker 镜像

```bash
docker build -t tg-userharvest .
```

### 2. 启动服务

```bash
# 使用生产环境配置启动
docker-compose -f docker-compose.prod.yml --env-file .env.prod.local up -d
```

### 3. 检查服务状态

```bash
# 查看运行状态
docker-compose -f docker-compose.prod.yml ps

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f
```

## 🔧 配置说明

### Nginx 反向代理

- **配置文件**: `nginx/nginx.conf`
- **功能**: HTTPS 重定向、SSL 终止、反向代理、速率限制
- **端口**: 80 (HTTP) → 443 (HTTPS)

### SSL 证书

- **类型**: Let's Encrypt 免费证书
- **自动续期**: 每周日凌晨 3 点自动续期
- **手动续期**: `./renew-ssl.sh`

### 安全配置

- **JWT 认证**: 所有 API 端点需要认证
- **速率限制**: API 请求限制 10/秒，登录限制 5/分钟
- **HTTPS 强制**: 所有 HTTP 请求重定向到 HTTPS
- **安全头**: 包含 HSTS、XSS 保护等安全头

## 📊 监控和日志

### 启动监控服务

```bash
# 启动 Prometheus + Grafana 监控
cd monitoring
docker-compose -f docker-compose.monitoring.yml up -d
```

**访问地址**:
- Grafana: `http://your-domain.com:3000` (admin/admin)
- Prometheus: `http://your-domain.com:9090`

### 查看日志

```bash
# 应用日志
docker-compose -f docker-compose.prod.yml logs -f web

# Nginx 日志
docker-compose -f docker-compose.prod.yml logs -f nginx

# 系统日志
tail -f logs/nginx/access.log
tail -f logs/nginx/error.log
```

## 🔄 维护操作

### 更新应用

```bash
# 拉取最新代码
git pull

# 重新构建并重启
docker-compose -f docker-compose.prod.yml up -d --build
```

### 备份数据

```bash
# 备份数据库
cp data/data.sqlite3 backup/data-$(date +%Y%m%d).sqlite3

# 备份配置
tar -czf backup/config-$(date +%Y%m%d).tar.gz .env.prod.local nginx/
```

### 重启服务

```bash
# 重启所有服务
docker-compose -f docker-compose.prod.yml restart

# 重启单个服务
docker-compose -f docker-compose.prod.yml restart web
docker-compose -f docker-compose.prod.yml restart nginx
```

### 停止服务

```bash
# 停止所有服务
docker-compose -f docker-compose.prod.yml down

# 停止并删除数据卷
docker-compose -f docker-compose.prod.yml down -v
```

## 🛠️ 故障排除

### 常见问题

1. **SSL 证书获取失败**
   ```bash
   # 检查域名解析
   dig your-domain.com
   
   # 检查端口 80 是否被占用
   sudo netstat -tlnp | grep :80
   ```

2. **服务启动失败**
   ```bash
   # 查看详细错误日志
   docker-compose -f docker-compose.prod.yml logs web
   
   # 检查环境变量
   docker-compose -f docker-compose.prod.yml config
   ```

3. **无法访问应用**
   ```bash
   # 检查防火墙设置
   sudo ufw status
   sudo ufw allow 80
   sudo ufw allow 443
   
   # 检查服务状态
   curl -I http://localhost:8000/health
   ```

### 性能优化

1. **增加并发数**
   ```bash
   # 在 .env.prod.local 中调整
   MAX_CONCURRENCY=5
   ```

2. **数据库优化**
   ```bash
   # 定期清理数据库
   docker-compose -f docker-compose.prod.yml exec web python -c "
   from app.database import get_db
   from app import crud
   db = next(get_db())
   crud.cleanup_old_data(db)
   "
   ```

## 📞 支持

如果遇到问题，请检查：

1. **日志文件**: `logs/` 目录下的日志文件
2. **健康检查**: `https://your-domain.com/health`
3. **服务状态**: `docker-compose -f docker-compose.prod.yml ps`

## 🔒 安全建议

1. **定期更新**
   - 定期更新系统包: `sudo apt update && sudo apt upgrade`
   - 定期更新 Docker 镜像: `docker-compose pull`

2. **监控访问**
   - 定期检查访问日志
   - 设置异常访问告警

3. **备份策略**
   - 每日自动备份数据库
   - 定期备份配置文件

4. **防火墙配置**
   ```bash
   sudo ufw enable
   sudo ufw allow ssh
   sudo ufw allow 80
   sudo ufw allow 443
   ```