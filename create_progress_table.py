#!/usr/bin/env python3
"""
创建collection_progress表的脚本
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models import _init_engine_and_session, Base, CollectionProgress

def create_progress_table():
    """创建collection_progress表"""
    print("🔧 创建collection_progress表...")
    
    try:
        # 初始化数据库引擎
        _init_engine_and_session()
        
        # 创建表
        from app.models import _engine
        CollectionProgress.__table__.create(_engine, checkfirst=True)
        
        print("✅ collection_progress表创建成功！")
        
        # 验证表是否存在
        from sqlalchemy import inspect
        inspector = inspect(_engine)
        tables = inspector.get_table_names()
        
        if 'collection_progress' in tables:
            print("✅ 验证：collection_progress表已存在")
            
            # 显示表结构
            columns = inspector.get_columns('collection_progress')
            print("📋 表结构:")
            for col in columns:
                print(f"   - {col['name']}: {col['type']}")
        else:
            print("❌ 验证失败：collection_progress表不存在")
            
    except Exception as e:
        print(f"❌ 创建表失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    create_progress_table()