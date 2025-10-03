# Telegram群组采集系统 - 管理员指南

## 🚀 系统部署

### 快速部署到VPS
```bash
# 1. 确保有SSH密钥文件
# 2. 修改deploy-vps.sh中的VPS信息
# 3. 执行部署脚本
./deploy-vps.sh
```

### 手动部署步骤
```bash
# 1. 克隆项目
git clone https://github.com/PengC8899/tg_userharvest_fastapi.git
cd tg_userharvest_fastapi

# 2. 配置环境变量
cp .env.example .env
# 编辑.env文件，设置数据库连接等

# 3. 启动服务
docker-compose -f docker-compose.prod.yml up -d --build
```

## 🔧 系统配置

### 环境变量配置
```bash
# 数据库配置
DATABASE_URL=postgresql://username:password@localhost:5432/tg_userharvest

# Telegram API配置
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# 安全配置
SECRET_KEY=your_secret_key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123

# 服务器配置
HOST=0.0.0.0
PORT=8000
```

### 防火墙配置
```bash
# 开放必要端口
sudo ufw allow 8000/tcp  # 应用端口
sudo ufw allow 3000/tcp  # 监控端口
sudo ufw allow 22/tcp    # SSH端口
sudo ufw enable
```

## 📊 系统监控

### 访问监控面板
- **地址**: http://your-server:3000
- **用户名**: admin
- **密码**: admin

### 监控指标
- CPU使用率
- 内存使用率
- 磁盘空间
- 网络流量
- 应用响应时间
- 数据库连接数

### 日志查看
```bash
# 查看应用日志
docker-compose logs -f app

# 查看数据库日志
docker-compose logs -f postgres

# 查看Nginx日志
docker-compose logs -f nginx
```

## 👥 用户管理

### 添加新用户
目前系统使用单一管理员账号，所有员工共享使用。如需要多用户系统，需要开发用户管理功能。

### 数据隔离
- 每个Telegram账号的数据完全隔离
- 通过`account_id`区分不同用户的数据
- 用户只能看到自己账号的采集结果

## 🔒 安全管理

### 数据安全
- 所有敏感数据加密存储
- Session文件本地存储，不上传到Git
- 私钥文件已添加到.gitignore

### 访问控制
- 建议使用HTTPS（配置SSL证书）
- 定期更改管理员密码
- 监控异常登录行为

### 备份策略
```bash
# 执行备份
./scripts/backup.sh daily    # 每日备份
./scripts/backup.sh weekly   # 每周备份
./scripts/backup.sh monthly  # 每月备份
```

## 📈 性能优化

### 数据库优化
- 定期清理过期数据
- 优化数据库索引
- 监控查询性能

### 应用优化
- 调整并发采集数量
- 优化内存使用
- 配置适当的超时时间

### 服务器优化
```bash
# 调整系统参数
echo 'net.core.somaxconn = 65535' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_max_syn_backlog = 65535' >> /etc/sysctl.conf
sysctl -p
```

## 🛠️ 故障排除

### 常见问题

#### 1. 应用无法启动
```bash
# 检查端口占用
netstat -tlnp | grep 8000

# 检查Docker状态
docker ps -a
docker-compose logs app
```

#### 2. 数据库连接失败
```bash
# 检查数据库状态
docker-compose logs postgres

# 测试数据库连接
docker-compose exec postgres psql -U postgres -d tg_userharvest
```

#### 3. Telegram API错误
- 检查API_ID和API_HASH是否正确
- 确认网络可以访问Telegram服务器
- 检查账号是否被限制

#### 4. 采集速度慢
- 降低并发数量
- 检查网络延迟
- 优化数据库查询

### 诊断工具
```bash
# 运行系统诊断
python scripts/diagnose.py

# 检查系统资源
htop
df -h
free -h
```

## 📋 维护任务

### 日常维护
- [ ] 检查系统运行状态
- [ ] 查看错误日志
- [ ] 监控磁盘空间
- [ ] 检查备份状态

### 周期维护
- [ ] 更新系统补丁
- [ ] 清理临时文件
- [ ] 优化数据库
- [ ] 检查安全设置

### 月度维护
- [ ] 分析系统性能
- [ ] 更新依赖包
- [ ] 审查访问日志
- [ ] 测试备份恢复

## 🔄 系统更新

### 更新流程
```bash
# 1. 备份当前系统
./scripts/backup.sh

# 2. 拉取最新代码
git pull origin main

# 3. 重新构建镜像
docker-compose -f docker-compose.prod.yml build

# 4. 重启服务
docker-compose -f docker-compose.prod.yml up -d
```

### 回滚流程
```bash
# 1. 停止服务
docker-compose down

# 2. 恢复代码版本
git checkout previous_commit_hash

# 3. 重新启动
docker-compose -f docker-compose.prod.yml up -d
```

## 📞 紧急联系

### 系统故障处理
1. 立即检查系统状态
2. 查看错误日志
3. 尝试重启服务
4. 如无法解决，联系技术支持

### 联系信息
- **主要负责人**: [姓名] - [电话] - [邮箱]
- **备用联系人**: [姓名] - [电话] - [邮箱]
- **技术支持**: [技术团队联系方式]

---

**最后更新**: 2024年10月4日
**版本**: v1.0