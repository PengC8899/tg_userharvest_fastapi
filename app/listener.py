from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Set
from telethon import events, types
from telethon.tl.types import User, Channel, Chat
from sqlalchemy.orm import Session

from .tele_client import get_client_for_account
from .models import Account, get_db, User as UserModel, Speak
from . import crud
from .config import get_settings

# 全局监听器状态管理
active_listeners: Dict[int, Dict] = {}  # account_id -> listener_info
listener_stats: Dict[int, Dict] = {}    # account_id -> stats

def get_listener_status(account_id: int) -> Dict:
    """获取监听器状态"""
    if account_id not in active_listeners:
        return {
            "status": "stopped",
            "account_id": account_id,
            "stats": {"new_users": 0, "total_messages": 0},
            "start_time": None
        }
    
    return {
        "status": "listening",
        "account_id": account_id,
        "stats": listener_stats.get(account_id, {"new_users": 0, "total_messages": 0}),
        "start_time": active_listeners[account_id].get("start_time")
    }

async def start_listener_for_account(account_id: int, db: Session) -> dict:
    """为指定账号启动实时监听器"""
    print(f"🎧 启动账号 {account_id} 的实时监听器")
    
    # 检查账号是否存在
    acc = db.get(Account, account_id)
    if not acc:
        print(f"❌ 账号 {account_id} 不存在")
        return {"error": "account not found"}
    
    # 检查是否已经在监听
    if account_id in active_listeners:
        print(f"⚠️ 账号 {account_id} 已经在监听中")
        return {"error": "listener already active"}
    
    print(f"📱 账号信息: {acc.name} ({acc.phone})")
    
    # 获取选中的群组
    selected_groups = crud.list_selected_groups(db, account_id)
    if not selected_groups:
        print(f"❌ 账号 {account_id} 没有选中的群组")
        return {"error": "no selected groups"}
    
    chat_ids = [int(s.chat_id) for s in selected_groups]
    print(f"📊 将监听 {len(chat_ids)} 个群组: {chat_ids}")
    
    try:
        # 获取Telegram客户端
        client = await get_client_for_account(acc)
        
        # 初始化统计信息
        listener_stats[account_id] = {
            "new_users": 0,
            "total_messages": 0,
            "processed_users": set()  # 用于去重
        }
        
        # 创建消息处理器
        async def handle_new_message(event):
            """处理新消息事件"""
            try:
                # 获取消息发送者
                sender = await event.get_sender()
                if not sender or not isinstance(sender, types.User):
                    return
                
                # 跳过机器人
                if bool(getattr(sender, "bot", False)):
                    return
                
                # 只处理有username的用户
                if not sender.username:
                    return
                
                # 更新消息统计
                listener_stats[account_id]["total_messages"] += 1
                
                # 检查用户是否已处理过（去重）
                user_id = int(sender.id)
                if user_id in listener_stats[account_id]["processed_users"]:
                    return
                
                # 标记用户已处理
                listener_stats[account_id]["processed_users"].add(user_id)
                
                # 确保username以@开头
                username = sender.username
                if not username.startswith('@'):
                    username = '@' + username
                
                # 保存用户信息到数据库（只保存@username）
                with next(get_db()) as db_session:
                    u = crud.upsert_user(
                        db_session,
                        tg_user_id=user_id,
                        username=username,
                        first_name=None,  # 不保存昵称
                        last_name=None,   # 不保存昵称
                        is_bot=False,     # 已经过滤了机器人
                    )
                    
                    # 保存发言记录
                    speak_record = Speak(
                        account_id=account_id,
                        chat_id=chat_id,
                        tg_user_id=user_id,
                        message_id=event.message.id,
                        message_date=event.message.date
                    )
                    db_session.add(speak_record)
                    
                    db_session.commit()
                
                # 更新统计
                listener_stats[account_id]["new_users"] += 1
                
                print(f"👤 新用户: {username} - 总用户数: {listener_stats[account_id]['new_users']}")
                
            except Exception as e:
                print(f"❌ 处理消息时出错: {e}")
        
        # 注册事件处理器 - 监听指定群组的新消息
        for chat_id in chat_ids:
            try:
                # 尝试不同的ID格式
                entity_id = chat_id
                if chat_id > 0:
                    # 对于正数ID，尝试Channel格式
                    entity_id = -1000000000000 - chat_id
                
                client.add_event_handler(
                    handle_new_message,
                    events.NewMessage(chats=entity_id)
                )
                print(f"✅ 已注册监听器: 群组 {chat_id} (实体ID: {entity_id})")
            except Exception as e:
                print(f"⚠️ 注册群组 {chat_id} 监听器失败: {e}")
        
        # 记录监听器信息
        active_listeners[account_id] = {
            "client": client,
            "chat_ids": chat_ids,
            "start_time": datetime.now(timezone.utc).isoformat()
        }
        
        print(f"🎉 账号 {account_id} 的实时监听器启动成功！")
        return {
            "message": "实时监听器启动成功",
            "account_id": account_id,
            "listening_groups": len(chat_ids)
        }
        
    except Exception as e:
        print(f"❌ 启动监听器失败: {e}")
        return {"error": f"failed to start listener: {str(e)}"}

async def stop_listener_for_account(account_id: int) -> dict:
    """停止指定账号的实时监听器"""
    print(f"🛑 停止账号 {account_id} 的实时监听器")
    
    if account_id not in active_listeners:
        print(f"⚠️ 账号 {account_id} 没有活跃的监听器")
        return {"error": "no active listener"}
    
    try:
        # 获取监听器信息
        listener_info = active_listeners[account_id]
        client = listener_info["client"]
        
        # 移除所有事件处理器
        client.remove_event_handler(handle_new_message)
        
        # 清理监听器状态
        del active_listeners[account_id]
        
        # 保留统计信息但标记为已停止
        if account_id in listener_stats:
            # 移除processed_users集合以节省内存
            if "processed_users" in listener_stats[account_id]:
                del listener_stats[account_id]["processed_users"]
        
        print(f"✅ 账号 {account_id} 的监听器已停止")
        return {
            "message": "实时监听器已停止",
            "account_id": account_id,
            "final_stats": listener_stats.get(account_id, {})
        }
        
    except Exception as e:
        print(f"❌ 停止监听器失败: {e}")
        return {"error": f"failed to stop listener: {str(e)}"}

def get_all_listeners_status() -> Dict:
    """获取所有监听器的状态"""
    return {
        "active_listeners": list(active_listeners.keys()),
        "total_active": len(active_listeners),
        "listeners": {
            account_id: get_listener_status(account_id) 
            for account_id in set(list(active_listeners.keys()) + list(listener_stats.keys()))
        }
    }

async def stop_all_listeners() -> Dict:
    """停止所有活跃的监听器"""
    print("🛑 停止所有活跃的监听器")
    
    results = {}
    for account_id in list(active_listeners.keys()):
        result = await stop_listener_for_account(account_id)
        results[account_id] = result
    
    return {
        "message": "所有监听器已停止",
        "results": results
    }