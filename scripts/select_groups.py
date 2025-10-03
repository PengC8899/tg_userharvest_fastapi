#!/usr/bin/env python3
"""
选择要监听的群组的脚本
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import _init_engine_and_session, get_db, Account, Group, SelectedGroup


def select_all_groups(account_id: int):
    """为指定账号选择所有群组进行监听"""
    print(f"🔄 正在为账号ID {account_id} 选择所有群组...")
    
    # 初始化数据库
    _init_engine_and_session()
    db = next(get_db())
    
    try:
        # 获取账号信息
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            print(f"❌ 找不到账号ID {account_id}")
            return False
            
        print(f"📱 账号: {account.name} ({account.phone})")
        
        # 获取该账号的所有群组
        groups = db.query(Group).filter(Group.account_id == account_id).all()
        print(f"📊 找到 {len(groups)} 个群组")
        
        if not groups:
            print("❌ 该账号没有群组")
            return False
        
        # 清除之前的选择
        db.query(SelectedGroup).filter(SelectedGroup.account_id == account_id).delete()
        
        # 添加所有群组到选中列表
        selected_count = 0
        for group in groups:
            selected_group = SelectedGroup(
                account_id=account_id,
                chat_id=group.chat_id
            )
            db.add(selected_group)
            selected_count += 1
            print(f"✅ 已选择: {group.title}")
        
        db.commit()
        print(f"\n🎉 成功选择了 {selected_count} 个群组进行监听！")
        return True
        
    except Exception as e:
        print(f"❌ 选择群组失败: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def show_selected_groups(account_id: int):
    """显示已选择的群组"""
    _init_engine_and_session()
    db = next(get_db())
    
    try:
        # 获取选中的群组
        selected_groups = db.query(SelectedGroup, Group).join(
            Group, SelectedGroup.chat_id == Group.chat_id
        ).filter(SelectedGroup.account_id == account_id).all()
        
        print(f"\n📋 账号ID {account_id} 已选择的群组:")
        print("=" * 60)
        
        if not selected_groups:
            print("❌ 没有选择任何群组")
        else:
            for i, (selected, group) in enumerate(selected_groups, 1):
                print(f"{i:2d}. {group.title}")
                print(f"    群组ID: {group.chat_id}")
        
        print("=" * 60)
        print(f"总计: {len(selected_groups)} 个群组")
        
    except Exception as e:
        print(f"❌ 获取群组列表失败: {e}")
    finally:
        db.close()


def main():
    print("🚀 群组选择工具")
    print("=" * 50)
    
    # 监听2号的账号ID是2
    account_id = 2
    
    print("1. 显示当前选择的群组...")
    show_selected_groups(account_id)
    
    print("\n2. 选择所有群组进行监听...")
    success = select_all_groups(account_id)
    
    if success:
        print("\n3. 显示更新后的选择...")
        show_selected_groups(account_id)
        
        print("\n🎯 下一步操作:")
        print("1. 返回管理界面")
        print("2. 点击 '开始采集' 按钮")
        print("3. 等待一段时间让系统采集消息")
        print("4. 再次尝试下载数据")
    else:
        print("\n❌ 群组选择失败")


if __name__ == '__main__':
    main()