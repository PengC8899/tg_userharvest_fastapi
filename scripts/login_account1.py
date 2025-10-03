#!/usr/bin/env python3
"""
专门为账号1（鹏程，+97517924046）生成会话字符串的脚本
"""
import os
import sys
import asyncio
import sqlite3
from getpass import getpass

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession


async def login_account1():
    """为账号1生成会话字符串"""
    # 加载环境变量
    load_dotenv()
    
    api_id = os.getenv('API_ID')
    api_hash = os.getenv('API_HASH')
    phone = '+97517924046'  # 监听1号手机
    
    if not api_id or not api_hash:
        print("❌ 请在 .env 文件中配置 API_ID 和 API_HASH")
        return None
    
    print(f"正在为账号1（{phone}）生成会话...")
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
            print(f"会话字符串长度: {len(session_string)}")
            
            # 更新数据库
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data.sqlite3')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE accounts SET session_string = ? WHERE id = 1",
                (session_string,)
            )
            conn.commit()
            conn.close()
            
            print("✅ 数据库已更新")
            return session_string
            
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return None


if __name__ == '__main__':
    try:
        result = asyncio.run(login_account1())
        if result:
            print("\n✅ 账号1会话生成完成！")
        else:
            print("\n❌ 会话生成失败")
    except KeyboardInterrupt:
        print('\n已取消')
    except Exception as e:
        print(f"脚本错误: {e}")