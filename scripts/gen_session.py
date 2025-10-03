#!/usr/bin/env python3
import os
import sys
import asyncio
from getpass import getpass

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession


async def main():
    load_dotenv()
    api_id = os.getenv('API_ID') or input('API_ID: ').strip()
    api_hash = os.getenv('API_HASH') or input('API_HASH: ').strip()

    if not api_id or not api_hash:
        print('API_ID 和 API_HASH 必填', file=sys.stderr)
        sys.exit(1)

    phone = input('电话号码 (含国家码，如 +855...): ').strip()
    if not phone:
        print('电话必填以接收验证码', file=sys.stderr)
        sys.exit(1)

    async with TelegramClient(StringSession(), int(api_id), api_hash) as client:
        await client.connect()
        if not await client.is_user_authorized():
            try:
                await client.send_code_request(phone)
            except Exception as e:
                print(f'发送验证码失败: {e}', file=sys.stderr)
                sys.exit(1)

            code = input('输入收到的验证码 (不含空格): ').strip()
            try:
                await client.sign_in(phone=phone, code=code)
            except Exception as e:
                # 可能需要二次验证密码
                if 'SESSION_PASSWORD_NEEDED' in str(e) or 'password' in str(e).lower():
                    pw = getpass('输入两步验证密码: ')
                    await client.sign_in(password=pw)
                else:
                    print(f'登录失败: {e}', file=sys.stderr)
                    sys.exit(1)

        s = client.session.save()
        print('\n===== 复制以下 StringSession 到管理台新增账号 =====\n')
        print(s)
        print('\n=================================================')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n已取消')