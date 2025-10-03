#!/usr/bin/env python3
"""
Telegram 用户收集系统自诊断脚本
自动检测常见问题并提供修复建议
"""

import os
import sys
import sqlite3
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# 添加app目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

def print_header(title):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def print_section(title):
    """打印章节标题"""
    print(f"\n{'-'*40}")
    print(f" {title}")
    print(f"{'-'*40}")

def check_database():
    """检查数据库状态"""
    print_section("数据库检查")
    
    db_path = "/app/data/data.sqlite3" if os.path.exists("/app") else "./data/data.sqlite3"
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False
    
    print(f"✅ 数据库文件存在: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查表是否存在
        required_tables = ['accounts', 'groups', 'selected_groups', 'collection_progress']
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        missing_tables = []
        for table in required_tables:
            if table in existing_tables:
                print(f"✅ 表 {table} 存在")
            else:
                print(f"❌ 表 {table} 不存在")
                missing_tables.append(table)
        
        # 检查账户数据
        cursor.execute("SELECT COUNT(*) FROM accounts;")
        account_count = cursor.fetchone()[0]
        print(f"📊 账户数量: {account_count}")
        
        if account_count == 0:
            print("⚠️  没有配置账户，需要先添加账户")
        
        # 检查进度表数据
        cursor.execute("SELECT COUNT(*) FROM collection_progress;")
        progress_count = cursor.fetchone()[0]
        print(f"📊 进度记录数量: {progress_count}")
        
        conn.close()
        
        if missing_tables:
            print(f"\n🔧 修复建议: 运行数据库迁移创建缺失的表: {', '.join(missing_tables)}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 数据库连接错误: {e}")
        return False

def check_environment():
    """检查环境变量"""
    print_section("环境变量检查")
    
    required_vars = {
        'API_ID': '必需 - Telegram API ID',
        'API_HASH': '必需 - Telegram API Hash',
        'ADMIN_USERNAME': '必需 - 管理员用户名',
        'ADMIN_PASSWORD': '必需 - 管理员密码',
        'JWT_SECRET_KEY': '必需 - JWT密钥'
    }
    
    missing_vars = []
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            # 隐藏敏感信息
            if var in ['API_HASH', 'ADMIN_PASSWORD', 'JWT_SECRET_KEY']:
                display_value = f"{value[:4]}***{value[-4:]}" if len(value) > 8 else "***"
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
        else:
            print(f"❌ {var}: 未设置 - {desc}")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n🔧 修复建议: 在.env文件中设置缺失的环境变量: {', '.join(missing_vars)}")
        return False
    
    return True

def check_accounts():
    """检查账户状态"""
    print_section("账户状态检查")
    
    db_path = "/app/data/data.sqlite3" if os.path.exists("/app") else "./data/data.sqlite3"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name, phone, is_enabled FROM accounts;")
        accounts = cursor.fetchall()
        
        if not accounts:
            print("❌ 没有配置任何账户")
            print("🔧 修复建议: 使用脚本添加账户或通过Web界面添加")
            return False
        
        enabled_accounts = []
        for acc in accounts:
            acc_id, name, phone, is_enabled = acc
            status = "启用" if is_enabled else "禁用"
            print(f"📱 账户 {acc_id}: {name} ({phone}) - {status}")
            if is_enabled:
                enabled_accounts.append(acc_id)
        
        if not enabled_accounts:
            print("❌ 没有启用的账户")
            print("🔧 修复建议: 启用至少一个账户")
            return False
        
        # 检查选中的群组
        for acc_id in enabled_accounts:
            cursor.execute("SELECT COUNT(*) FROM selected_groups WHERE account_id = ?;", (acc_id,))
            group_count = cursor.fetchone()[0]
            print(f"📊 账户 {acc_id} 选中群组数量: {group_count}")
            
            if group_count == 0:
                print(f"⚠️  账户 {acc_id} 没有选中任何群组")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 检查账户时出错: {e}")
        return False

def check_progress_status():
    """检查进度状态"""
    print_section("进度状态检查")
    
    db_path = "/app/data/data.sqlite3" if os.path.exists("/app") else "./data/data.sqlite3"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT account_id, current_group, total_groups, percentage, 
                   group_name, status, updated_at 
            FROM collection_progress;
        """)
        progress_records = cursor.fetchall()
        
        if not progress_records:
            print("📊 没有进度记录")
            print("💡 这是正常的，进度记录会在开始收集时创建")
            return True
        
        for record in progress_records:
            acc_id, current, total, percentage, group_name, status, updated_at = record
            print(f"📊 账户 {acc_id}: {current}/{total} ({percentage}%) - {status}")
            print(f"   当前群组: {group_name}")
            print(f"   更新时间: {updated_at}")
            
            # 检查是否卡住
            if updated_at:
                try:
                    last_update = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    hours_since_update = (now - last_update).total_seconds() / 3600
                    
                    if hours_since_update > 2 and status in ['collecting', 'preparing']:
                        print(f"⚠️  账户 {acc_id} 可能卡住了 (超过2小时未更新)")
                        print("🔧 修复建议: 重启收集任务或重置进度")
                except:
                    pass
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 检查进度时出错: {e}")
        return False

def reset_progress(account_id=None):
    """重置进度"""
    print_section("重置进度")
    
    db_path = "/app/data/data.sqlite3" if os.path.exists("/app") else "./data/data.sqlite3"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        if account_id:
            cursor.execute("DELETE FROM collection_progress WHERE account_id = ?;", (account_id,))
            print(f"✅ 已重置账户 {account_id} 的进度")
        else:
            cursor.execute("DELETE FROM collection_progress;")
            print("✅ 已重置所有账户的进度")
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 重置进度时出错: {e}")
        return False

def create_progress_record(account_id):
    """为账户创建进度记录"""
    print_section(f"为账户 {account_id} 创建进度记录")
    
    db_path = "/app/data/data.sqlite3" if os.path.exists("/app") else "./data/data.sqlite3"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查账户是否存在
        cursor.execute("SELECT id FROM accounts WHERE id = ? AND is_enabled = 1;", (account_id,))
        if not cursor.fetchone():
            print(f"❌ 账户 {account_id} 不存在或未启用")
            return False
        
        # 检查是否已有进度记录
        cursor.execute("SELECT id FROM collection_progress WHERE account_id = ?;", (account_id,))
        if cursor.fetchone():
            print(f"⚠️  账户 {account_id} 已有进度记录")
            return True
        
        # 创建进度记录
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO collection_progress 
            (account_id, current_group, total_groups, percentage, group_name, status, created_at, updated_at)
            VALUES (?, 0, 0, 0, '准备中...', 'preparing', ?, ?);
        """, (account_id, now, now))
        
        conn.commit()
        conn.close()
        
        print(f"✅ 已为账户 {account_id} 创建进度记录")
        return True
        
    except Exception as e:
        print(f"❌ 创建进度记录时出错: {e}")
        return False

def main():
    """主函数"""
    print_header("Telegram 用户收集系统 - 自诊断")
    
    # 检查各个组件
    checks = [
        ("环境变量", check_environment),
        ("数据库", check_database),
        ("账户状态", check_accounts),
        ("进度状态", check_progress_status),
    ]
    
    all_passed = True
    for name, check_func in checks:
        try:
            if not check_func():
                all_passed = False
        except Exception as e:
            print(f"❌ {name}检查时出错: {e}")
            all_passed = False
    
    print_header("诊断结果")
    
    if all_passed:
        print("🎉 所有检查都通过了！系统应该可以正常运行。")
        print("\n💡 如果脚本仍然显示0%，可能的原因:")
        print("   1. 没有启动收集任务")
        print("   2. 账户没有选中任何群组")
        print("   3. 网络连接问题")
        print("   4. Telegram API限制")
    else:
        print("⚠️  发现了一些问题，请根据上面的修复建议进行处理。")
    
    # 提供交互式修复选项
    print("\n" + "="*60)
    print("可用的修复操作:")
    print("1. 重置所有进度")
    print("2. 重置指定账户进度")
    print("3. 为账户创建进度记录")
    print("4. 退出")
    
    try:
        choice = input("\n请选择操作 (1-4): ").strip()
        
        if choice == "1":
            if input("确认重置所有进度? (y/N): ").lower() == 'y':
                reset_progress()
        elif choice == "2":
            account_id = input("请输入账户ID: ").strip()
            if account_id.isdigit():
                if input(f"确认重置账户 {account_id} 的进度? (y/N): ").lower() == 'y':
                    reset_progress(int(account_id))
        elif choice == "3":
            account_id = input("请输入账户ID: ").strip()
            if account_id.isdigit():
                create_progress_record(int(account_id))
        elif choice == "4":
            print("退出诊断工具")
        else:
            print("无效选择")
    except KeyboardInterrupt:
        print("\n\n退出诊断工具")
    except Exception as e:
        print(f"操作时出错: {e}")

if __name__ == "__main__":
    main()