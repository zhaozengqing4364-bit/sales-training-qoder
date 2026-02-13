#!/usr/bin/env python3
"""
重新处理失败的文档

用法:
    python reprocess_failed_docs.py [document_id]

    不提供 document_id 时，会列出所有失败的文档
"""
import asyncio
import sys
import os

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from common.knowledge.processor import get_document_processor, DocumentProcessor
from common.knowledge.models import DocumentStatus
from common.knowledge.service import KnowledgeService
from common.knowledge.vector_store import get_knowledge_vector_store

# 从环境变量获取数据库 URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/app.db")

async def list_failed_documents():
    """列出所有失败的文档"""
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(
            text('''
                SELECT d.id, d.title, d.file_type, d.error_message,
                       d.knowledge_base_id, kb.name as kb_name
                FROM knowledge_documents d
                JOIN knowledge_bases kb ON d.knowledge_base_id = kb.id
                WHERE d.status = 'failed'
            ''')
        )
        rows = result.fetchall()

        if not rows:
            print('✅ 没有找到状态为 failed 的文档')
            return []

        print(f'发现 {len(rows)} 个失败的文档:\n')
        for row in rows:
            print(f'文档ID: {row.id}')
            print(f'标题: {row.title}')
            print(f'知识库: {row.kb_name}')
            print(f'错误: {row.error_message[:100] if row.error_message else "未知错误"}')
            print('-' * 50)

        return [row.id for row in rows]

    await engine.dispose()

async def reprocess_document(doc_id: str):
    """重新处理单个文档"""
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        service = KnowledgeService(session)

        # 获取文档信息
        result = await session.execute(
            text('''
                SELECT d.*, kb.vector_collection
                FROM knowledge_documents d
                JOIN knowledge_bases kb ON d.knowledge_base_id = kb.id
                WHERE d.id = :doc_id
            '''),
            {"doc_id": doc_id}
        )
        row = result.fetchone()

        if not row:
            print(f'❌ 文档 {doc_id} 不存在')
            return False

        if row.status != 'failed':
            print(f'⚠️ 文档 {doc_id} 状态为 {row.status}，不是失败状态')
            return False

        print(f'开始重新处理文档: {row.title}')
        print(f'文件路径: {row.file_url}')

        # 更新状态为 processing
        await service.update_document_status(
            doc_id=doc_id,
            status=DocumentStatus.PROCESSING.value
        )
        await session.commit()

        try:
            # 删除旧向量
            vector_store = get_knowledge_vector_store()
            await vector_store.delete_document_chunks(row.vector_collection, doc_id)

            # 重新处理
            processor = DocumentProcessor()
            result = await processor.process_document(
                doc_id=doc_id,
                file_path=row.file_url,
                file_type=row.file_type,
                document_title=row.title,
                knowledge_base_id=row.knowledge_base_id,
                vector_collection=row.vector_collection,
            )

            # 更新最终状态
            await service.update_document_status(
                doc_id=doc_id,
                status=result["status"],
                chunk_count=result["chunk_count"],
                error_message=result.get("error_message")
            )
            await session.commit()

            if result["status"] == DocumentStatus.READY.value:
                print(f'✅ 文档处理成功！切片数: {result["chunk_count"]}')
                return True
            else:
                print(f'❌ 文档处理失败: {result.get("error_message")}')
                return False

        except Exception as e:
            await service.update_document_status(
                doc_id=doc_id,
                status=DocumentStatus.FAILED.value,
                error_message=str(e)
            )
            await session.commit()
            print(f'❌ 处理异常: {e}')
            return False

    await engine.dispose()

async def main():
    if len(sys.argv) < 2:
        # 列出所有失败文档
        await list_failed_documents()
        print('\n用法: python reprocess_failed_docs.py <document_id>')
        print('      python reprocess_failed_docs.py all  # 重新处理所有失败文档')
    elif sys.argv[1] == 'all':
        doc_ids = await list_failed_documents()
        if doc_ids:
            print(f'\n开始重新处理 {len(doc_ids)} 个文档...\n')
            success_count = 0
            for doc_id in doc_ids:
                if await reprocess_document(doc_id):
                    success_count += 1
                print()
            print(f'处理完成: {success_count}/{len(doc_ids)} 成功')
    else:
        # 处理指定文档
        doc_id = sys.argv[1]
        await reprocess_document(doc_id)

if __name__ == '__main__':
    asyncio.run(main())
