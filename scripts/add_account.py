#!/usr/bin/env python3
"""
添加账号到数据库的脚本
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import Account, _init_engine_and_session, get_db
from app.config import get_settings


def add_account(name: str, phone: str, session_string: str):
    """添加账号到数据库"""
    print(f"🔄 正在添加账号: {name}")
    print(f"手机号: {phone}")
    print(f"会话字符串长度: {len(session_string)} 字符")
    
    # 初始化数据库
    _init_engine_and_session()
    
    # 获取数据库会话
    db = next(get_db())
    
    try:
        # 检查账号是否已存在
        existing = db.query(Account).filter(Account.name == name).first()
        if existing:
            print(f"⚠️  账号 {name} 已存在，正在更新...")
            existing.phone = phone
            existing.session_string = session_string
            existing.is_enabled = True
            db.commit()
            print(f"✅ 账号 {name} 更新成功！")
        else:
            # 创建新账号
            account = Account(
                name=name,
                phone=phone,
                session_string=session_string,
                is_enabled=True
            )
            db.add(account)
            db.commit()
            print(f"✅ 账号 {name} 添加成功！")
        
        # 显示账号信息
        account = db.query(Account).filter(Account.name == name).first()
        print(f"\n📋 账号信息:")
        print(f"ID: {account.id}")
        print(f"名称: {account.name}")
        print(f"手机号: {account.phone}")
        print(f"状态: {'启用' if account.is_enabled else '禁用'}")
        print(f"创建时间: {account.created_at}")
        print(f"更新时间: {account.updated_at}")
        
        return account.id
        
    except Exception as e:
        print(f"❌ 添加账号失败: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def main():
    print("🚀 开始添加监听2号账号到数据库...")
    
    # 监听2号信息
    account_name = "监听2号"
    phone = "+97517578684"
    session_string = "1BVtsOMQBu6Y2yp_20i8OTgoSl7K31FPQ8M2SDwa0jJiNizyuXhKMY034FTIjVYFS3bEJvKdqATwABdr_odz3KXAOU9gEcyu1lrWSwyrx32xTji7H4-Q8V7Kq_wKOtOw4wpvpBQz6vqOF3xiSwyoqaZHVi1PwPZarhuCc2NMwhnrtIzC7EhUkWEuEoYTJSe_7pL78-BSTsXU8MuF3cxzKIhrBenHhgRMfZ8MdjcIa10IWrWV6MR7TAvqD04BFXb8jcvMy0nnwDA_Xt_scilIbgM6cJnYNlUiuKyv-JhDJfHIO1dGYYNrYmpbNqN4lSBRMGuML04mD9ckjAkLFrTrRxGZjrs5Jbnc="
    
    account_id = add_account(account_name, phone, session_string)
    
    if account_id:
        print(f"\n🎉 监听2号账号添加完成！账号ID: {account_id}")
        print("\n📝 下一步:")
        print("1. 启动 FastAPI 服务器")
        print("2. 访问管理界面添加要监听的群组")
        print("3. 开始数据采集")
    else:
        print("\n❌ 账号添加失败")
        sys.exit(1)


if __name__ == '__main__':
    main()