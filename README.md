tg_userharvest_fastapi

概述
- 使用 FastAPI + Telethon 构建的 Telegram 多账号采集管理台。
- 支持从“我加入的群”中按近 N 天（today/yesterday/3d/7d）采集有发言且带 @username 的普通用户（排除管理员/群主/Bot），去重入库并提供 TXT 导出。
- 多账号池：通过 StringSession 管理多个账号；按账号维度刷新群、勾选目标、并发采集。

快速开始（本地）
1) 创建并激活虚拟环境
```
python -m venv .venv
source .venv/bin/activate
```
2) 安装依赖
```
pip install -r requirements.txt
```
3) 配置环境
```
cp .env.sample .env
# 编辑 .env，填入 API_ID、API_HASH、TZ 等
```
4) 生成 Telethon StringSession
```
python scripts/gen_session.py
# 成功后复制输出的 SESSION_STRING
```
5) 启动服务
```
uvicorn app.main:app --host 0.0.0.0 --port 8000
# 打开 http://localhost:8000
```
6) 在管理台新增账号（粘贴 StringSession）→ 刷新群 → 勾选目标群 → 开始采集 → 导出 TXT（按时间范围）。

Docker 运行
```
docker compose up -d --build
# 打开 http://localhost:8000
```

注意事项
- 采集包含限流风险（FloodWait），系统已做节流与退避，但建议控制并发（MAX_CONCURRENCY）。
- 会话失效或需要二步验证时，通过“测试会话”接口可查看提示并更新会话。
- 导出 TXT 为去重后的 username（非空），按升序排列；可按账号/群过滤。

目录结构
```
tg_userharvest_fastapi/
├── README.md
├── .env.sample
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── scripts/
│   └── gen_session.py
└── app/
    ├── main.py
    ├── config.py
    ├── tele_client.py
    ├── collectors.py
    ├── models.py
    ├── crud.py
    ├── schemas.py
    ├── utils.py
    ├── templates/
    │   └── index.html
    └── static/
        └── style.css
```