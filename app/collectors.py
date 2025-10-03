from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from telethon import types, errors
from telethon.tl.types import Channel, Chat, ChannelParticipantsAdmins
from sqlalchemy.orm import Session

from .tele_client import get_client_for_account
from .models import Account, SelectedGroup, CollectionProgress
from . import crud

# 全局进度跟踪（保留用于向后兼容）
collection_progress: Dict[str, Dict] = {}

def get_progress_key(account_id: int) -> str:
    """获取进度跟踪的键"""
    return f"account_{account_id}"

def update_progress(account_id: int, current_group: int, total_groups: int, group_name: str = "", status: str = "collecting"):
    """更新采集进度 - 同时更新内存和数据库"""
    key = get_progress_key(account_id)
    percentage = int((current_group / total_groups) * 100) if total_groups > 0 else 0
    
    # 更新内存状态（向后兼容）
    collection_progress[key] = {
        "account_id": account_id,
        "current_group": current_group,
        "total_groups": total_groups,
        "percentage": percentage,
        "group_name": group_name,
        "status": status,
        "updated_at": datetime.now().isoformat()
    }
    
    # 更新数据库状态
    update_progress_db(account_id, current_group, total_groups, group_name, status)

def update_progress_db(account_id: int, current_group: int, total_groups: int, group_name: str = "", status: str = "collecting"):
    """更新数据库中的采集进度"""
    from .models import _init_engine_and_session, SessionLocal
    
    try:
        # 确保数据库引擎已初始化
        _init_engine_and_session()
        db = SessionLocal()
        
        try:
            percentage = int((current_group / total_groups) * 100) if total_groups > 0 else 0
            
            # 查找或创建进度记录
            progress = db.query(CollectionProgress).filter(CollectionProgress.account_id == account_id).first()
            
            if progress:
                # 更新现有记录
                progress.current_group = current_group
                progress.total_groups = total_groups
                progress.percentage = percentage
                progress.group_name = group_name
                progress.status = status
                progress.updated_at = datetime.now(timezone.utc)
            else:
                # 创建新记录
                progress = CollectionProgress(
                    account_id=account_id,
                    current_group=current_group,
                    total_groups=total_groups,
                    percentage=percentage,
                    group_name=group_name,
                    status=status
                )
                db.add(progress)
            
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"❌ 更新数据库进度失败: {e}")

def get_progress(account_id: int) -> Dict:
    """获取采集进度 - 优先从数据库获取"""
    from .models import _init_engine_and_session, SessionLocal
    
    try:
        # 确保数据库引擎已初始化
        _init_engine_and_session()
        db = SessionLocal()
        
        try:
            progress = db.query(CollectionProgress).filter(CollectionProgress.account_id == account_id).first()
            
            if progress:
                return {
                    "account_id": progress.account_id,
                    "current_group": progress.current_group,
                    "total_groups": progress.total_groups,
                    "percentage": progress.percentage,
                    "group_name": progress.group_name,
                    "status": progress.status,
                    "updated_at": progress.updated_at.isoformat()
                }
        finally:
            db.close()
    except Exception as e:
        print(f"❌ 从数据库获取进度失败: {e}")
    
    # 如果数据库获取失败，返回默认状态
    return {
        "account_id": account_id,
        "current_group": 0,
        "total_groups": 0,
        "percentage": 0,
        "group_name": "准备中...",
        "status": "preparing",
        "updated_at": datetime.now().isoformat()
    }

def clear_progress(account_id: int):
    """清除采集进度 - 同时清除内存和数据库"""
    # 清除内存状态
    key = get_progress_key(account_id)
    if key in collection_progress:
        del collection_progress[key]
    
    # 清除数据库状态
    clear_progress_db(account_id)

def clear_progress_db(account_id: int):
    """清除数据库中的采集进度"""
    from .models import _init_engine_and_session, SessionLocal
    
    try:
        # 确保数据库引擎已初始化
        _init_engine_and_session()
        db = SessionLocal()
        
        try:
            progress = db.query(CollectionProgress).filter(CollectionProgress.account_id == account_id).first()
            if progress:
                db.delete(progress)
                db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"❌ 清除数据库进度失败: {e}")


async def refresh_groups_for_account(account_id: int, db: Session) -> dict:
    acc = db.get(Account, account_id)
    if not acc:
        return {"error": "account not found"}
    client = await get_client_for_account(acc)
    inserted = 0
    titles: List[str] = []
    async for d in client.iter_dialogs():
        # 仅保留真正的群/大群对话，避免误收录浏览过的公开频道
        if not getattr(d, "is_group", False):
            continue
        ent = d.entity
        # 排除已离开的群
        if hasattr(ent, "left") and getattr(ent, "left"):
            continue
        chat_id = getattr(ent, "id", None)
        title = getattr(ent, "title", "")
        if chat_id is None:
            continue
        crud.upsert_group(db, account_id=acc.id, chat_id=int(chat_id), title=title or str(chat_id))
        inserted += 1
        titles.append(title)
        await asyncio.sleep(0.05)
    return {"count": inserted, "titles": titles}


async def list_admin_user_ids(client, chat_id: int) -> set[int]:
    try:
        # 对于正数ID，尝试使用负数格式访问Channel类型群组
        entity = None
        if chat_id > 0:
            try:
                # 先尝试直接访问
                entity = await client.get_entity(chat_id)
            except Exception:
                # 如果失败，尝试使用Channel的负数ID格式
                try:
                    negative_id = -1000000000000 - chat_id
                    entity = await client.get_entity(negative_id)
                except Exception:
                    pass
        else:
            # 负数ID直接访问
            entity = await client.get_entity(chat_id)
            
        if not entity:
            return set()
    except Exception:
        return set()
    admin_ids: set[int] = set()
    try:
        if isinstance(entity, Channel):
            admins = await client.get_participants(entity, filter=ChannelParticipantsAdmins())
            for a in admins:
                admin_ids.add(int(a.id))
        # For Chat, Telethon doesn't provide admin list easily; skip.
    except errors.FloodWaitError as e:
        await asyncio.sleep(e.seconds + 1)
    except Exception:
        pass
    return admin_ids


async def collect_for_account(account_id: int, days: int, db: Session) -> dict:
    print(f"🚀 开始采集账号 {account_id}，天数: {days}")
    acc = db.get(Account, account_id)
    if not acc:
        print(f"❌ 账号 {account_id} 不存在")
        return {"error": "account not found"}
    
    print(f"📱 账号信息: {acc.name} ({acc.phone})")
    
    # 初始化进度
    selected = crud.list_selected_groups(db, account_id)
    total_groups = len(selected)
    print(f"📊 找到 {total_groups} 个选中的群组")
    update_progress(account_id, 0, total_groups, "准备中...", "preparing")
    
    print(f"🔗 获取Telegram客户端...")
    client = await get_client_for_account(acc)
    start_utc = datetime.now(timezone.utc) - timedelta(days=days)
    print(f"📅 采集时间范围: {start_utc} 到现在")
    stats: Dict[str, int] = {"new_users": 0, "new_speaks": 0}
    per_group: Dict[int, int] = {}

    for i, s in enumerate(selected):
        chat_id = int(s.chat_id)
        group_name = f"群组 {chat_id}"
        
        print(f"🔄 处理群组 {i+1}/{total_groups}: {chat_id}")
        
        # 更新进度
        update_progress(account_id, i, total_groups, group_name, "collecting")
        
        try:
            print(f"🔍 尝试获取群组实体: {chat_id}")
            # 对于正数ID，尝试使用负数格式访问Channel类型群组
            entity = None
            if chat_id > 0:
                try:
                    # 先尝试直接访问
                    print(f"  📞 直接访问 {chat_id}")
                    entity = await client.get_entity(chat_id)
                    print(f"  ✅ 直接访问成功")
                except Exception as e:
                    print(f"  ❌ 直接访问失败: {e}")
                    # 如果失败，尝试使用Channel的负数ID格式
                    try:
                        negative_id = -1000000000000 - chat_id
                        print(f"  📞 尝试负数ID: {negative_id}")
                        entity = await client.get_entity(negative_id)
                        print(f"  ✅ 负数ID访问成功")
                    except Exception as e2:
                        print(f"  ❌ 负数ID访问也失败: {e2}")
                        pass
            else:
                # 负数ID直接访问
                print(f"  📞 负数ID直接访问: {chat_id}")
                entity = await client.get_entity(chat_id)
                print(f"  ✅ 负数ID访问成功")
            
            if not entity:
                print(f"  ⚠️ 无法获取群组实体，跳过")
                # 减少群组访问失败时的等待时间
                await asyncio.sleep(0.02)
                continue
                
            # 尝试获取群组标题
            if hasattr(entity, 'title') and entity.title:
                group_name = entity.title
                print(f"  📝 群组标题: {group_name}")
                update_progress(account_id, i, total_groups, group_name, "collecting")
        except Exception as e:
            print(f"  ❌ 获取群组信息失败: {e}")
            # 减少群组标题获取失败时的等待时间
            await asyncio.sleep(0.02)
            continue
        
        print(f"  👥 获取管理员列表...")
        admin_ids = await list_admin_user_ids(client, chat_id)
        print(f"  👥 找到 {len(admin_ids)} 个管理员")
        per_group[chat_id] = 0

        try:
            print(f"  📨 开始遍历消息...")
            message_count = 0
            async for msg in client.iter_messages(entity, offset_date=start_utc, reverse=True):
                message_count += 1
                if message_count % 100 == 0:
                    print(f"    📊 已处理 {message_count} 条消息")
                
                if not msg:
                    continue
                # ensure date in window
                if msg.date is None:
                    continue
                msg_date = msg.date.astimezone(timezone.utc)
                if msg_date < start_utc:
                    continue
                try:
                    sender = await msg.get_sender()
                except Exception:
                    continue
                if not isinstance(sender, types.User):
                    continue
                if bool(getattr(sender, "bot", False)):
                    continue
                if int(sender.id) in admin_ids:
                    continue
                username = sender.username
                # 允许没有用户名的用户，不再跳过
                # upsert user & insert speak
                u = crud.upsert_user(
                    db,
                    tg_user_id=int(sender.id),
                    username=username,  # 可以为None
                    first_name=getattr(sender, "first_name", None),
                    last_name=getattr(sender, "last_name", None),
                    is_bot=bool(getattr(sender, "bot", False)),
                )
                inserted = crud.insert_speak(
                    db,
                    account_id=account_id,
                    chat_id=chat_id,
                    tg_user_id=int(sender.id),
                    message_id=int(getattr(msg, "id", 0)),
                    message_date=msg_date,
                )
                if inserted:
                    stats["new_speaks"] += 1
                    per_group[chat_id] += 1
                stats["new_users"] += 1  # count seen user occurrences (approx)
                # 减少消息处理间隔，提升采集速度
                await asyncio.sleep(0.01)
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds + 1)
        except Exception:
            # swallow per group errors to continue others
            await asyncio.sleep(0.05)

    # 完成进度
    update_progress(account_id, total_groups, total_groups, "采集完成", "completed")
    
    stats["per_group"] = per_group
    return stats


async def collect_multi(accounts: List[int], days: int, db: Session, max_concurrency: int) -> dict:
    sem = asyncio.Semaphore(max_concurrency)
    results: Dict[int, dict] = {}

    async def run_one(acc_id: int):
        async with sem:
            try:
                res = await collect_for_account(acc_id, days, db)
                results[acc_id] = res
            except Exception as e:
                results[acc_id] = {"error": str(e)}
            finally:
                # 清理进度信息
                clear_progress(acc_id)

    await asyncio.gather(*(run_one(a) for a in accounts))
    return {"results": results}