#!/usr/bin/env python3
import requests
import json
import time

def check_progress():
    """检查采集进度"""
    url = "http://127.0.0.1:8189/api/progress/1"
    
    print("🔍 监控账号1的采集进度...")
    
    for i in range(30):  # 最多检查30次，每次间隔10秒
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                result = response.json()
                data = result.get('data', {})
                
                status = data.get('status', 'unknown')
                current = data.get('current_group', 0)
                total = data.get('total_groups', 0)
                percentage = data.get('percentage', 0)
                group_name = data.get('group_name', '')
                
                print(f"[{i+1:2d}/30] 状态: {status} | 进度: {current}/{total} ({percentage}%) | 当前群组: {group_name[:50]}...")
                
                if status == 'completed':
                    print("✅ 采集完成！")
                    return True
                elif status == 'error':
                    print("❌ 采集出错！")
                    return False
                    
            else:
                print(f"❌ 获取进度失败: {response.status_code}")
                
        except Exception as e:
            print(f"❌ 检查进度时出错: {e}")
            
        time.sleep(10)  # 等待10秒
    
    print("⏰ 监控超时，采集可能仍在进行中")
    return False

if __name__ == '__main__':
    check_progress()
