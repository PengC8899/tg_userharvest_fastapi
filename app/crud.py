from __future__ import annotations

from typing import Iterable, Sequence
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, and_, func
from .models import Account, Group, SelectedGroup, User, Speak


# Accounts
def list_accounts(db: Session) -> list[Account]:
    return list(db.execute(select(Account).order_by(Account.id)).scalars())


def get_account(db: Session, account_id: int) -> Account | None:
    """根据ID获取账户"""
    return db.get(Account, account_id)


def create_account(db: Session, name: str, session_string: str, phone: str | None = None, is_enabled: bool = True) -> Account:
    acc = Account(name=name, session_string=session_string, phone=phone, is_enabled=is_enabled)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


def update_account(db: Session, account_id: int, **fields) -> Account | None:
    acc = db.get(Account, account_id)
    if not acc:
        return None
    for k, v in fields.items():
        if hasattr(acc, k):
            setattr(acc, k, v)
    db.commit()
    db.refresh(acc)
    return acc


def delete_account(db: Session, account_id: int) -> bool:
    acc = db.get(Account, account_id)
    if not acc:
        return False
    db.delete(acc)
    db.commit()
    return True


# Groups
def upsert_group(db: Session, account_id: int, chat_id: int, title: str) -> Group:
    q = select(Group).where(Group.account_id == account_id, Group.chat_id == chat_id)
    existing = db.execute(q).scalars().first()
    if existing:
        existing.title = title
        db.commit()
        db.refresh(existing)
        return existing
    g = Group(account_id=account_id, chat_id=chat_id, title=title)
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def list_groups_for_account(db: Session, account_id: int) -> list[Group]:
    return list(db.execute(select(Group).where(Group.account_id == account_id).order_by(Group.title)).scalars())


def set_selected_groups(db: Session, account_id: int, chat_ids: Iterable[int]) -> dict:
    # clear existing and insert new unique set
    db.execute(delete(SelectedGroup).where(SelectedGroup.account_id == account_id))
    db.commit()
    unique_ids = set(int(cid) for cid in chat_ids)
    for cid in unique_ids:
        db.add(SelectedGroup(account_id=account_id, chat_id=cid))
    db.commit()
    return {"count": len(unique_ids)}


def list_selected_groups(db: Session, account_id: int) -> list[SelectedGroup]:
    return list(db.execute(select(SelectedGroup).where(SelectedGroup.account_id == account_id)).scalars())


# Users & Speaks
def upsert_user(db: Session, tg_user_id: int, username: str | None, first_name: str | None, last_name: str | None, is_bot: bool) -> User:
    q = select(User).where(User.tg_user_id == tg_user_id)
    u = db.execute(q).scalars().first()
    if u:
        # Only update username if provided and non-empty (latest non-empty)
        if username:
            u.username = username
        # 不再更新昵称字段，只保存@username
        # u.first_name = first_name
        # u.last_name = last_name
        u.is_bot = is_bot
        db.commit()
        db.refresh(u)
        return u
    u = User(
        tg_user_id=tg_user_id,
        username=username,
        first_name=first_name,  # 新用户创建时可以为None
        last_name=last_name,    # 新用户创建时可以为None
        is_bot=is_bot,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def insert_speak(db: Session, account_id: int, chat_id: int, tg_user_id: int, message_id: int, message_date) -> bool:
    try:
        s = Speak(
            account_id=account_id,
            chat_id=chat_id,
            tg_user_id=tg_user_id,
            message_id=message_id,
            message_date=message_date,
        )
        db.add(s)
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False


def get_usernames_in_window(
    db: Session,
    start_utc,
    end_utc,
    account_id: int | None = None,
    chat_id: int | None = None,
) -> list[str]:
    # join speaks -> users and filter window
    from sqlalchemy import and_, join
    j = join(Speak, User, Speak.tg_user_id == User.tg_user_id)
    conds = [Speak.message_date >= start_utc, Speak.message_date < end_utc]
    if account_id is not None:
        conds.append(Speak.account_id == account_id)
    if chat_id is not None:
        conds.append(Speak.chat_id == chat_id)
    q = select(User.username).select_from(j).where(and_(*conds))
    rows = db.execute(q).scalars().all()
    usernames = sorted({r for r in rows if r})
    return usernames


def cleanup_database(db: Session) -> dict:
    """
    整理数据库：
    1. 删除没有username的用户记录
    2. 删除重复的用户记录（保留最新的）
    3. 确保所有username都以@开头
    4. 删除孤立的speak记录（对应的用户不存在）
    """
    from sqlalchemy import and_, func, text
    
    result = {
        "deleted_users_without_username": 0,
        "deleted_duplicate_users": 0,
        "updated_username_format": 0,
        "deleted_orphaned_speaks": 0,
        "remaining_users": 0,
        "remaining_speaks": 0
    }
    
    try:
        # 1. 删除没有username或username为空的用户
        users_without_username = db.execute(
            select(User).where(
                (User.username.is_(None)) | (User.username == '') | (User.username == '@')
            )
        ).scalars().all()
        
        for user in users_without_username:
            # 先删除相关的speak记录
            db.execute(delete(Speak).where(Speak.tg_user_id == user.tg_user_id))
            # 再删除用户记录
            db.delete(user)
            result["deleted_users_without_username"] += 1
        
        # 2. 处理重复的tg_user_id（保留最新的记录）
        # 查找重复的tg_user_id
        duplicate_query = db.execute(
            select(User.tg_user_id, func.count(User.id).label('count'))
            .group_by(User.tg_user_id)
            .having(func.count(User.id) > 1)
        ).all()
        
        for tg_user_id, count in duplicate_query:
            # 获取该tg_user_id的所有记录，按created_at降序排列
            users = db.execute(
                select(User)
                .where(User.tg_user_id == tg_user_id)
                .order_by(User.created_at.desc())
            ).scalars().all()
            
            # 保留第一个（最新的），删除其余的
            for user in users[1:]:
                db.delete(user)
                result["deleted_duplicate_users"] += 1
        
        # 3. 确保所有username都以@开头
        users_need_format = db.execute(
            select(User).where(
                and_(
                    User.username.is_not(None),
                    User.username != '',
                    ~User.username.startswith('@')
                )
            )
        ).scalars().all()
        
        for user in users_need_format:
            user.username = '@' + user.username
            result["updated_username_format"] += 1
        
        # 4. 删除孤立的speak记录（对应的用户不存在）
        orphaned_speaks = db.execute(
            text("""
                DELETE FROM speaks 
                WHERE tg_user_id NOT IN (SELECT tg_user_id FROM users)
            """)
        )
        result["deleted_orphaned_speaks"] = orphaned_speaks.rowcount
        
        # 提交所有更改
        db.commit()
        
        # 统计剩余记录数
        result["remaining_users"] = db.execute(select(func.count(User.id))).scalar()
        result["remaining_speaks"] = db.execute(select(func.count(Speak.id))).scalar()
        
        return result
        
    except Exception as e:
        db.rollback()
        raise e


def get_cleaned_usernames(db: Session) -> list[str]:
    """
    获取整理后的所有@username列表（去重、排序）
    """
    usernames = db.execute(
        select(User.username)
        .where(
            and_(
                User.username.is_not(None),
                User.username != '',
                User.username != '@'
            )
        )
        .distinct()
        .order_by(User.username)
    ).scalars().all()
    
    return list(usernames)