#!/usr/bin/env python3
import os
import sys
import asyncio
from getpass import getpass

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession


async def login_account(phone, api_id, api_hash):
    """直接登录指定账号"""
    print(f"正在为 {phone} 生成会话...")
    print(f"使用 API ID: {api_id}")
    
    async with TelegramClient(StringSession(), int(api_id), api_hash) as client:
        try:
            await client.connect()
            print("已连接到 Telegram 服务器")
            
            if not await client.is_user_authorized():
                print(f"发送验证码到 {phone}...")
                await client.send_code_request(phone)
                print("✅ 验证码已发送！请查收短信或 Telegram 应用")
                
                code = input('请输入收到的验证码: ').strip()
                
                try:
                    await client.sign_in(phone=phone, code=code)
                    print("✅ 登录成功！")
                except Exception as e:
                    if 'SESSION_PASSWORD_NEEDED' in str(e) or 'password' in str(e).lower():
                        pw = getpass('需要两步验证密码: ')
                        await client.sign_in(password=pw)
                        print("✅ 两步验证成功！")
                    else:
                        print(f"❌ 登录失败: {e}")
                        return None
            else:
                print("✅ 账号已授权")

            session_string = client.session.save()
            print(f"\n🎉 会话生成成功！")
            print(f"账号: {phone}")
            print(f"会话字符串:")
            print("=" * 60)
            print(session_string)
            print("=" * 60)
            return session_string
            
        except Exception as e:
            print(f"❌ 错误: {e}")
            return None


async def main():
    # 监听1号
    phone1 = "+97517924046"
    api_id1 = "20600006"
    api_hash1 = "f723a2ce7491e888fa82b05870365311"
    
    # 监听2号
    phone2 = "+97517578684"
    api_id2 = "27715945"
    api_hash2 = "8261b886976e018e70255e2e0ed3eade"
    
    print("开始为两个账号生成会话...")
    print("=" * 60)
    
    # 登录第一个账号
    print("\n🔄 处理监听1号...")
    session1 = await login_account(phone1, api_id1, api_hash1)
    
    if session1:
        print(f"\n✅ 监听1号 ({phone1}) 会话生成完成")
        
        # 登录第二个账号
        print("\n🔄 处理监听2号...")
        session2 = await login_account(phone2, api_id2, api_hash2)
        
        if session2:
            print(f"\n✅ 监听2号 ({phone2}) 会话生成完成")
            print("\n🎉 所有账号会话生成完成！")
            print("\n请复制上面的会话字符串到管理系统中")
        else:
            print(f"\n❌ 监听2号生成失败")
    else:
        print(f"\n❌ 监听1号生成失败")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n已取消')
    except Exception as e:
        print(f"脚本错误: {e}")