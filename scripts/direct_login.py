#!/usr/bin/env python3
import asyncio
import sys
from telethon import TelegramClient
from telethon.sessions import StringSession


async def generate_session(phone, api_id, api_hash, account_name):
    """为指定账号生成会话"""
    print(f"\n{'='*60}")
    print(f"🔄 开始处理 {account_name}")
    print(f"手机号: {phone}")
    print(f"API ID: {api_id}")
    print(f"{'='*60}")
    
    try:
        # 创建客户端
        client = TelegramClient(StringSession(), int(api_id), api_hash)
        
        # 连接
        await client.connect()
        print("✅ 已连接到 Telegram 服务器")
        
        # 检查是否已授权
        if not await client.is_user_authorized():
            print(f"📱 正在发送验证码到 {phone}...")
            
            # 发送验证码
            await client.send_code_request(phone)
            print("✅ 验证码已发送！请查收短信或 Telegram 应用")
            
            # 等待用户输入验证码
            code = input(f'请输入 {phone} 收到的验证码: ').strip()
            
            try:
                # 登录
                await client.sign_in(phone=phone, code=code)
                print("✅ 登录成功！")
            except Exception as e:
                if 'SESSION_PASSWORD_NEEDED' in str(e) or 'password' in str(e).lower():
                    from getpass import getpass
                    password = getpass(f'请输入 {phone} 的两步验证密码: ')
                    await client.sign_in(password=password)
                    print("✅ 两步验证成功！")
                else:
                    print(f"❌ 登录失败: {e}")
                    await client.disconnect()
                    return None
        else:
            print("✅ 账号已授权")
        
        # 获取会话字符串
        session_string = client.session.save()
        await client.disconnect()
        
        print(f"\n🎉 {account_name} 会话生成成功！")
        print("会话字符串:")
        print("-" * 60)
        print(session_string)
        print("-" * 60)
        
        return session_string
        
    except Exception as e:
        print(f"❌ {account_name} 处理失败: {e}")
        try:
            await client.disconnect()
        except:
            pass
        return None


async def main():
    print("🚀 开始为两个监听账号生成会话...")
    
    # 账号信息
    accounts = [
        {
            "name": "监听1号",
            "phone": "+97517924046",
            "api_id": "20600006",
            "api_hash": "f723a2ce7491e888fa82b05870365311"
        },
        {
            "name": "监听2号", 
            "phone": "+97517578684",
            "api_id": "27715945",
            "api_hash": "8261b886976e018e70255e2e0ed3eade"
        }
    ]
    
    sessions = []
    
    for account in accounts:
        session = await generate_session(
            account["phone"],
            account["api_id"], 
            account["api_hash"],
            account["name"]
        )
        
        if session:
            sessions.append({
                "name": account["name"],
                "phone": account["phone"],
                "session": session
            })
            print(f"✅ {account['name']} 完成")
        else:
            print(f"❌ {account['name']} 失败")
            
        # 等待一下再处理下一个
        if account != accounts[-1]:  # 不是最后一个
            print("\n⏳ 等待3秒后处理下一个账号...")
            await asyncio.sleep(3)
    
    # 总结
    print(f"\n{'='*60}")
    print("📊 处理结果总结:")
    print(f"{'='*60}")
    
    if sessions:
        print(f"✅ 成功生成 {len(sessions)} 个会话:")
        for i, session_info in enumerate(sessions, 1):
            print(f"{i}. {session_info['name']} ({session_info['phone']})")
            
        print(f"\n🎯 所有会话字符串:")
        print("=" * 60)
        for session_info in sessions:
            print(f"\n# {session_info['name']} ({session_info['phone']})")
            print(session_info['session'])
            print("-" * 40)
        print("=" * 60)
        print("\n📋 请复制上面的会话字符串到管理系统中！")
    else:
        print("❌ 没有成功生成任何会话")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n\n⚠️  操作已取消')
        sys.exit(1)
    except Exception as e:
        print(f'\n❌ 脚本执行错误: {e}')
        sys.exit(1)