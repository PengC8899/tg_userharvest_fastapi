# TG UserHarvest 生产环境部署检查清单

## 🔒 安全配置检查

### ✅ 密钥和密码
- [x] 更改默认管理员密码（从 `9999` 改为强密码）
- [x] 生成强JWT密钥（32字符以上随机字符串）
- [x] 确保所有敏感信息不在代码中硬编码
- [x] 创建 `.gitignore` 文件防止敏感文件提交

### ✅ 环境变量
- [x] 创建 `.env.prod.template` 模板文件
- [x] 配置生产环境变量文件 `.env.prod`
- [x] 验证所有必需的环境变量已设置
- [x] 确保敏感信息不在版本控制中

## 🐳 Docker配置检查

### ✅ Dockerfile优化
- [x] 使用多阶段构建减小镜像大小
- [x] 创建非root用户运行应用
- [x] 添加健康检查配置
- [x] 安装必要的运行时依赖（curl等）

### ✅ Docker Compose
- [x] 配置生产环境的docker-compose.prod.yml
- [x] 设置适当的资源限制
- [x] 配置重启策略
- [x] 创建 `.dockerignore` 文件优化构建

## 🌐 Nginx和SSL配置

### ✅ Nginx配置
- [x] 配置HTTPS重定向
- [x] 设置安全头（HSTS, CSP等）
- [x] 配置速率限制防止攻击
- [x] 设置适当的超时和缓存策略

### ✅ SSL证书
- [x] 配置Let's Encrypt自动证书
- [x] 设置SSL安全配置
- [x] 配置证书自动续期

## 📊 监控和日志

### ✅ 监控系统
- [x] 配置Prometheus指标收集
- [x] 设置Grafana可视化面板
- [x] 配置Loki日志聚合
- [x] 设置告警规则和通知

### ✅ 日志管理
- [x] 配置日志轮转
- [x] 设置日志级别
- [x] 配置结构化日志输出

## 💾 备份和恢复

### ✅ 备份策略
- [x] 创建自动备份脚本
- [x] 配置定时备份任务
- [x] 设置备份保留策略
- [x] 测试备份完整性

### ✅ 恢复机制
- [x] 创建数据恢复脚本
- [x] 文档化恢复流程
- [x] 测试恢复过程

## 🚀 部署前最终检查

### 服务器准备
- [ ] 确保服务器满足最低要求（2GB RAM, 20GB存储）
- [ ] 安装Docker和Docker Compose
- [ ] 配置防火墙规则
- [ ] 设置域名DNS解析

### 环境配置
- [ ] 复制项目文件到服务器
- [ ] 配置生产环境变量
- [ ] 设置文件权限
- [ ] 配置SSL证书

### 服务启动
- [ ] 构建Docker镜像
- [ ] 启动所有服务
- [ ] 验证服务健康状态
- [ ] 测试应用功能

### 监控设置
- [ ] 启动监控服务
- [ ] 配置告警通知
- [ ] 设置定时任务
- [ ] 验证备份功能

## 📋 部署命令清单

### 1. 服务器初始化
```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. 项目部署
```bash
# 克隆项目
git clone <repository_url> /opt/tg_userharvest_fastapi
cd /opt/tg_userharvest_fastapi

# 运行部署脚本
sudo ./deploy.sh
```

### 3. 监控设置
```bash
# 启动监控服务
docker-compose -f docker-compose.monitoring.yml up -d

# 设置定时任务
sudo ./scripts/setup-cron.sh
```

### 4. 验证部署
```bash
# 检查服务状态
docker-compose ps

# 测试健康检查
curl http://localhost:8000/health
curl https://yourdomain.com/health

# 查看日志
docker-compose logs -f
```

## 🔧 故障排除

### 常见问题
1. **容器启动失败**
   - 检查环境变量配置
   - 查看容器日志：`docker-compose logs <service_name>`
   - 验证端口占用情况

2. **SSL证书问题**
   - 确认域名DNS解析正确
   - 检查防火墙80/443端口开放
   - 查看证书申请日志

3. **数据库连接失败**
   - 检查数据库容器状态
   - 验证数据库凭据
   - 确认网络连接

4. **性能问题**
   - 监控资源使用情况
   - 检查日志错误信息
   - 调整容器资源限制

## 📞 支持联系

如遇到部署问题，请：
1. 查看相关日志文件
2. 检查系统资源使用情况
3. 参考故障排除指南
4. 联系技术支持

---

**注意**: 请在生产环境部署前仔细检查所有项目，确保系统安全和稳定运行。