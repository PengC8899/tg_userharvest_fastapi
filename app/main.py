from __future__ import annotations

import io
import asyncio
from typing import Optional, List, Dict
import re
from fastapi import FastAPI, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from sqlalchemy.orm import Session

from .config import get_settings
from .models import get_db, Account
from . import crud
from .tele_client import get_client_for_account, release_all_clients
from .collectors import refresh_groups_for_account, collect_multi, get_progress
from .listener import start_listener_for_account, stop_listener_for_account, get_listener_status, get_all_listeners_status, stop_all_listeners
from .utils import parse_range_to_utc_window
from .schemas import APIResponse, AccountCreate, AccountUpdate, GroupSelect, CollectRequest, SessionInitRequest, SessionVerifyRequest, LoginRequest, LoginResponse
from .auth import authenticate_user, create_access_token, get_current_user
from telethon import errors
from telethon import TelegramClient
from telethon.sessions import StringSession


app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# in-memory state for phone -> phone_code_hash
_session_states: Dict[str, dict] = {}


@app.on_event("shutdown")
async def on_shutdown():
    await stop_all_listeners()
    await release_all_clients()


@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    accounts = crud.list_accounts(db)
    settings = get_settings()
    return templates.TemplateResponse("index.html", {"request": request, "accounts": accounts, "settings": settings})


@app.get("/health")
def health_check():
    """健康检查端点"""
    return {"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"}


# Authentication
@app.post("/api/login", response_model=LoginResponse)
def api_login(payload: LoginRequest):
    """用户登录"""
    if not authenticate_user(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": payload.username})
    return LoginResponse(access_token=access_token)


# Accounts
@app.get("/api/accounts", response_model=APIResponse)
def api_list_accounts(db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    accs = crud.list_accounts(db)
    data = [{"id": a.id, "name": a.name, "phone": a.phone, "is_enabled": a.is_enabled} for a in accs]
    return APIResponse(ok=True, data={"accounts": data})


@app.post("/api/accounts", response_model=APIResponse)
def api_create_account(payload: AccountCreate, db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    acc = crud.create_account(db, name=payload.name, session_string=payload.session_string, phone=payload.phone, is_enabled=payload.is_enabled)
    return APIResponse(ok=True, data={"id": acc.id})


@app.put("/api/accounts/{account_id}", response_model=APIResponse)
def api_update_account(account_id: int, payload: AccountUpdate, db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    acc = crud.update_account(db, account_id, **{k: v for k, v in payload.dict().items() if v is not None})
    if not acc:
        return APIResponse(ok=False, error="account not found")
    return APIResponse(ok=True, data={"id": acc.id})


@app.delete("/api/accounts/{account_id}", response_model=APIResponse)
def api_delete_account(account_id: int, db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    ok = crud.delete_account(db, account_id)
    return APIResponse(ok=ok, data={"id": account_id} if ok else None, error=None if ok else "account not found")


@app.post("/api/accounts/{account_id}/test-session", response_model=APIResponse)
async def api_test_session(account_id: int, db: Session = Depends(get_db)):
    acc = db.get(Account, account_id)
    if not acc:
        return APIResponse(ok=False, error="account not found")
    try:
        client = await get_client_for_account(acc)
        authorized = await client.is_user_authorized()
        return APIResponse(ok=True, data={"authorized": bool(authorized)})
    except Exception as e:
        return APIResponse(ok=False, error=str(e))


# Session generation (send code, verify and return StringSession)
@app.post("/api/session/init", response_model=APIResponse)
async def api_session_init(payload: SessionInitRequest):
    import time
    settings = get_settings()
    phone = re.sub(r"[\s-]+", "", payload.phone.strip())
    
    # 验证API配置
    if not settings.api_id or not settings.api_hash:
        return APIResponse(ok=False, error="API_ID 或 API_HASH 未配置")
    
    try:
        print(f"🔄 正在为手机号 {phone} 初始化会话...")
        
        # 创建客户端并设置超时
        client = TelegramClient(StringSession(), settings.api_id, settings.api_hash)
        
        # 使用 asyncio.wait_for 添加超时控制
        async def init_session():
            await client.connect()
            print("📡 已连接到 Telegram")
            print("📱 正在发送验证码...")
            sent = await client.send_code_request(phone)
            return sent, client.session.save()
        
        # 设置15秒超时
        sent, session_string = await asyncio.wait_for(init_session(), timeout=15.0)
        
        # 保存完整的会话状态，包括时间戳
        timeout_value = getattr(sent, "timeout", None) or 300  # 如果没有timeout属性，默认5分钟
        _session_states[phone] = {
            "phone_code_hash": getattr(sent, "phone_code_hash", None),
            "session_string": session_string,
            "timestamp": time.time(),
            "timeout": timeout_value
        }
        print(f"✅ 验证码已发送到 {phone}，有效期约 {timeout_value} 秒")
        
        # 断开连接
        await client.disconnect()
        
        return APIResponse(ok=True, data={
            "sent": True, 
            "timeout": timeout_value,
            "message": f"验证码已发送，请在 {timeout_value} 秒内输入"
        })
        
    except asyncio.TimeoutError:
        print(f"❌ 会话初始化超时: {phone}")
        return APIResponse(ok=False, error="连接超时，请检查网络连接或稍后重试")
    except Exception as e:
        print(f"❌ 会话初始化失败: {e}")
        return APIResponse(ok=False, error=str(e))


@app.post("/api/session/verify", response_model=APIResponse)
async def api_session_verify(payload: SessionVerifyRequest):
    import time
    settings = get_settings()
    phone = re.sub(r"[\s-]+", "", payload.phone.strip())
    code = payload.code.strip()
    pw = (payload.password or "").strip()
    st = _session_states.get(phone)
    
    # 检查会话状态是否存在
    if not st:
        return APIResponse(ok=False, error="会话已过期，请重新发送验证码")
    
    # 检查验证码是否过期
    current_time = time.time()
    elapsed_time = current_time - st.get("timestamp", 0)
    timeout = st.get("timeout", 300)
    
    if elapsed_time > timeout:
        # 清理过期的会话状态
        _session_states.pop(phone, None)
        return APIResponse(ok=False, error=f"验证码已过期（已过 {int(elapsed_time)} 秒，超时时间 {timeout} 秒），请重新发送验证码")
    
    try:
        print(f"🔐 正在验证手机号 {phone} 的验证码...")
        print(f"⏰ 验证码剩余有效时间: {int(timeout - elapsed_time)} 秒")
        
        # 使用保存的会话字符串创建客户端
        session_string = st.get("session_string", "")
        client = TelegramClient(StringSession(session_string), settings.api_id, settings.api_hash)
        
        # 使用 asyncio.wait_for 添加超时控制
        async def verify_session():
            await client.connect()
            print("📡 已连接到 Telegram")
            
            phone_code_hash = st.get("phone_code_hash")
            if phone_code_hash:
                print("📱 使用已保存的验证码哈希进行登录...")
                try:
                    await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
                except errors.SessionPasswordNeededError:
                    if not pw:
                        raise Exception("需要两步验证密码")
                    print("🔒 需要两步验证密码，正在验证...")
                    await client.sign_in(password=pw)
            else:
                # 如果没有保存的哈希，重新发送验证码
                print("📱 重新发送验证码并登录...")
                sent = await client.send_code_request(phone)
                try:
                    await client.sign_in(phone=phone, code=code, phone_code_hash=getattr(sent, "phone_code_hash", None))
                except errors.SessionPasswordNeededError:
                    if not pw:
                        raise Exception("需要两步验证密码")
                    print("🔒 需要两步验证密码，正在验证...")
                    await client.sign_in(password=pw)
            
            # 保存会话字符串
            session_string = client.session.save()
            return session_string
        
        # 设置20秒超时
        session_string = await asyncio.wait_for(verify_session(), timeout=20.0)
        
        # 断开连接
        await client.disconnect()
        
        # 清理状态
        _session_states.pop(phone, None)
        print(f"✅ 会话验证成功: {phone}")
        
        return APIResponse(ok=True, data={"session_string": session_string})
        
    except asyncio.TimeoutError:
        print(f"❌ 会话验证超时: {phone}")
        return APIResponse(ok=False, error="验证超时，请检查网络连接或稍后重试")
    except errors.PhoneCodeExpiredError:
        # 清理过期的会话状态
        _session_states.pop(phone, None)
        return APIResponse(ok=False, error="验证码已过期，请重新发送验证码")
    except errors.PhoneCodeInvalidError:
        return APIResponse(ok=False, error="验证码错误，请检查后重新输入")
    except errors.PasswordHashInvalidError:
        return APIResponse(ok=False, error="两步验证密码错误，请检查后重新输入")
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 会话验证失败: {error_msg}")
        
        # 处理常见错误
        if "confirmation code has expired" in error_msg.lower():
            _session_states.pop(phone, None)
            return APIResponse(ok=False, error="验证码已过期，请重新发送验证码")
        elif "invalid code" in error_msg.lower():
            return APIResponse(ok=False, error="验证码错误，请检查后重新输入")
        elif "password" in error_msg.lower():
            return APIResponse(ok=False, error="两步验证密码错误，请检查后重新输入")
        else:
            return APIResponse(ok=False, error=f"验证失败: {error_msg}")


# Groups
@app.post("/api/accounts/{account_id}/refresh-groups", response_model=APIResponse)
async def api_refresh_groups(account_id: int, db: Session = Depends(get_db)):
    data = await refresh_groups_for_account(account_id, db)
    if "error" in data:
        return APIResponse(ok=False, error=data["error"])
    return APIResponse(ok=True, data=data)


@app.get("/api/accounts/{account_id}/groups", response_model=APIResponse)
def api_list_groups(account_id: int, db: Session = Depends(get_db)):
    gs = crud.list_groups_for_account(db, account_id)
    data = [{"chat_id": g.chat_id, "title": g.title} for g in gs]
    return APIResponse(ok=True, data={"groups": data})


@app.post("/api/accounts/{account_id}/select-groups", response_model=APIResponse)
def api_select_groups(account_id: int, payload: GroupSelect, db: Session = Depends(get_db)):
    res = crud.set_selected_groups(db, account_id, payload.chat_ids)
    return APIResponse(ok=True, data=res)


@app.get("/api/accounts/{account_id}/selected-groups", response_model=APIResponse)
def api_list_selected_groups(account_id: int, db: Session = Depends(get_db)):
    ss = crud.list_selected_groups(db, account_id)
    data = [{"chat_id": s.chat_id} for s in ss]
    return APIResponse(ok=True, data={"selected": data})


# Collect
@app.post("/api/collect", response_model=APIResponse)
async def api_collect(payload: CollectRequest, current_user: str = Depends(get_current_user)):
    try:
        print(f"🔍 收到采集请求: days={payload.days} accounts={payload.accounts}")
        settings = get_settings()
        
        # 确定要采集的账号ID
        account_ids = payload.accounts if payload.accounts and len(payload.accounts) > 0 else None
        
        print(f"📋 将要采集的账号ID: {account_ids}")
        print(f"📅 采集天数: {payload.days}")
        
        # 启动后台任务，立即返回
        asyncio.create_task(run_collection_task(account_ids, payload.days, settings.max_concurrency))
        
        return APIResponse(ok=True, data={"message": "采集任务已启动", "accounts": account_ids})
    except Exception as e:
        print(f"❌ 采集过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return APIResponse(ok=False, error=str(e))

async def run_collection_task(account_ids: Optional[List[int]], days: int, max_concurrency: int):
    """后台运行采集任务"""
    try:
        print(f"🚀 开始后台采集任务: 账号 {account_ids}, 天数 {days}")
        # 创建新的数据库会话用于后台任务
        import app.models
        from app.models import _init_engine_and_session
        from . import crud
        _init_engine_and_session()  # 确保数据库引擎已初始化
        db = app.models.SessionLocal()
        try:
            # 如果没有指定账号，获取所有启用的账号
            if account_ids is None:
                accs = [a for a in crud.list_accounts(db) if a.is_enabled]
                account_ids = [a.id for a in accs]
                print(f"📋 获取到的账号ID: {account_ids}")
            
            data = await collect_multi(account_ids, days, db, max_concurrency)
            print(f"✅ 后台采集完成: {data}")
        finally:
            db.close()
    except Exception as e:
        print(f"❌ 后台采集过程中出错: {e}")
        import traceback
        traceback.print_exc()


# Progress API
@app.get("/api/progress/{account_id}", response_model=APIResponse)
def api_get_progress(account_id: int):
    """获取指定账号的采集进度"""
    try:
        progress = get_progress(account_id)
        return APIResponse(ok=True, data=progress)
    except Exception as e:
        return APIResponse(ok=False, error=str(e))


# Statistics API
@app.get("/api/stats", response_model=APIResponse)
def api_get_stats(db: Session = Depends(get_db)):
    """获取采集统计信息"""
    try:
        from sqlalchemy import text
        
        # 总用户数
        total_users = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
        
        # 有用户名的用户数
        users_with_username = db.execute(text("SELECT COUNT(*) FROM users WHERE username IS NOT NULL AND username != ''")).scalar()
        
        # 总发言数
        total_speaks = db.execute(text("SELECT COUNT(*) FROM speaks")).scalar()
        
        # 最近采集的用户（最新10个）
        recent_users = db.execute(text("""
            SELECT username, first_name, last_name, created_at 
            FROM users 
            WHERE username IS NOT NULL 
            ORDER BY created_at DESC 
            LIMIT 10
        """)).fetchall()
        
        # 按账号统计
        account_stats = db.execute(text("""
            SELECT a.name, COUNT(DISTINCT s.tg_user_id) as user_count, COUNT(s.id) as speak_count
            FROM accounts a
            LEFT JOIN speaks s ON a.id = s.account_id
            GROUP BY a.id, a.name
            ORDER BY user_count DESC
        """)).fetchall()
        
        stats = {
            "total_users": total_users,
            "users_with_username": users_with_username,
            "total_speaks": total_speaks,
            "recent_users": [
                {
                    "username": row[0],
                    "first_name": row[1],
                    "last_name": row[2],
                    "created_at": row[3]
                } for row in recent_users
            ],
            "account_stats": [
                {
                    "account_name": f"@{row[0]}",
                    "user_count": row[1],
                    "speak_count": row[2]
                } for row in account_stats
            ]
        }
        
        return APIResponse(ok=True, data=stats)
    except Exception as e:
        return APIResponse(ok=False, error=str(e))


# Export TXT
@app.get("/api/export/txt")
def api_export_txt(range: str, account_id: Optional[int] = None, chat_id: Optional[int] = None, db: Session = Depends(get_db)):
    settings = get_settings()
    try:
        start_utc, end_utc = parse_range_to_utc_window(range, settings.tz)
    except Exception as e:
        return PlainTextResponse(str(e), status_code=400)
    usernames = crud.get_usernames_in_window(db, start_utc, end_utc, account_id=account_id, chat_id=chat_id)
    
    # 确保所有用户名都以@开头，并按单列格式输出
    formatted_usernames = []
    for username in usernames:
        if username:  # 过滤空用户名
            if not username.startswith('@'):
                formatted_usernames.append(f"@{username}")
            else:
                formatted_usernames.append(username)
    
    content = "\n".join(formatted_usernames) + ("\n" if formatted_usernames else "")
    from fastapi.responses import Response
    filename = f"usernames_{range}.txt"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return Response(content=content, media_type="text/plain", headers=headers)


# Export listener collected usernames
@app.get("/api/export/listener-usernames/{account_id}")
def api_export_listener_usernames(account_id: int, db: Session = Depends(get_db)):
    """下载指定账户监听器收集到的用户名"""
    from fastapi.responses import Response
    from datetime import datetime, timedelta
    
    # 获取最近24小时的数据（监听器通常是实时收集）
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=24)
    
    # 获取该账户在指定时间范围内收集的用户名
    usernames = crud.get_usernames_in_window(db, start_time, end_time, account_id=account_id)
    
    if not usernames:
        content = "# 暂无监听收集到的用户名\n"
    else:
        # 确保所有用户名都以@开头，并按单列格式输出
        formatted_usernames = []
        for username in usernames:
            if username:  # 过滤空用户名
                if not username.startswith('@'):
                    formatted_usernames.append(f"@{username}")
                else:
                    formatted_usernames.append(username)
        content = "\n".join(formatted_usernames) + "\n"
    
    # 生成文件名，包含账户ID和时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"listener_usernames_account_{account_id}_{timestamp}.txt"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    
    return Response(content=content, media_type="text/plain", headers=headers)


# Listener API endpoints
@app.post("/api/accounts/{account_id}/start-listener", response_model=APIResponse)
async def api_start_listener(account_id: int, db: Session = Depends(get_db)):
    """启动指定账户的实时监听"""
    try:
        account = crud.get_account(db, account_id)
        if not account:
            return APIResponse(ok=False, error="账户不存在")
        
        success = await start_listener_for_account(account_id, db)
        if success:
            return APIResponse(ok=True, data={"message": f"账户 {account_id} 的监听器已启动"})
        else:
            return APIResponse(ok=False, error="启动监听器失败")
    except Exception as e:
        return APIResponse(ok=False, error=str(e))


@app.post("/api/accounts/{account_id}/stop-listener", response_model=APIResponse)
async def api_stop_listener(account_id: int):
    """停止指定账户的实时监听"""
    try:
        success = await stop_listener_for_account(account_id)
        if success:
            return APIResponse(ok=True, data={"message": f"账户 {account_id} 的监听器已停止"})
        else:
            return APIResponse(ok=False, error="停止监听器失败或监听器未运行")
    except Exception as e:
        return APIResponse(ok=False, error=str(e))


@app.get("/api/accounts/{account_id}/listener-status", response_model=APIResponse)
def api_get_listener_status(account_id: int):
    """获取指定账户的监听器状态"""
    try:
        status = get_listener_status(account_id)
        return APIResponse(ok=True, data=status)
    except Exception as e:
        return APIResponse(ok=False, error=str(e))


@app.get("/api/listeners/status", response_model=APIResponse)
def api_get_all_listeners_status():
    """获取所有监听器的状态"""
    try:
        status = get_all_listeners_status()
        return APIResponse(ok=True, data=status)
    except Exception as e:
        return APIResponse(ok=False, error=str(e))


@app.post("/api/listeners/stop-all", response_model=APIResponse)
async def api_stop_all_listeners():
    """停止所有监听器"""
    try:
        await stop_all_listeners()
        return APIResponse(ok=True, data={"message": "所有监听器已停止"})
    except Exception as e:
        return APIResponse(ok=False, error=str(e))


# Database cleanup API endpoints
@app.post("/api/database/cleanup", response_model=APIResponse)
def api_cleanup_database(db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    """整理数据库：去重复、提取@username、删除无效数据"""
    try:
        result = crud.cleanup_database(db)
        return APIResponse(ok=True, data={
            "message": "数据库整理完成",
            "details": result
        })
    except Exception as e:
        return APIResponse(ok=False, error=f"数据库整理失败: {str(e)}")


@app.get("/api/export/cleaned-usernames")
def api_export_cleaned_usernames(db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    """下载整理后的@username列表"""
    from fastapi.responses import Response
    from datetime import datetime
    
    try:
        usernames = crud.get_cleaned_usernames(db)
        
        if not usernames:
            content = "# 暂无整理后的用户名数据\n"
        else:
            content = "\n".join(usernames) + "\n"
        
        # 生成文件名，包含时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cleaned_usernames_{timestamp}.txt"
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
        
        return Response(content=content, media_type="text/plain", headers=headers)
    except Exception as e:
        return PlainTextResponse(f"导出失败: {str(e)}", status_code=500)