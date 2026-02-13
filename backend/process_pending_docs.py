#!/usr/bin/env python3
"""
手动处理待处理的文档
直接调用 processor 处理 pending 状态的文档
"""
import asyncio
import sys
import os

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

os.environ["DOCUMENT_STORAGE_PATH"] = "./data/documents"
os.environ["CHROMADB_PERSIST_DIR"] = "./data/chromadb"

# 设置数据库为 SQLite（避免 PostgreSQL 驱动问题）
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/app.db"

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from common.knowledge.processor import DocumentProcessor
from common.knowledge.models import DocumentStatus
from common.knowledge.vector_store import get_knowledge_vector_store

async def process_pending_documents():
    """处理所有 pending 和 failed 的文档"""
    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/app.db")
    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 查询所有 pending 或 failed 的文档
        result = await session.execute(
            text('''
                SELECT d.id, d.title, d.file_type, d.file_url, d.status,
                       d.knowledge_base_id, kb.vector_collection
                FROM knowledge_documents d
                JOIN knowledge_bases kb ON d.knowledge_base_id = kb.id
                WHERE d.status IN ('pending', 'failed')
            ''')
        )
        docs = result.fetchall()

        if not docs:
            print("✅ 没有待处理的文档")
            return

        print(f"发现 {len(docs)} 个待处理文档:\n")

        processor = DocumentProcessor()
        vector_store = get_knowledge_vector_store()

        for doc in docs:
            print(f"处理文档: {doc.title}")
            print(f"  ID: {doc.id}")
            print(f"  文件路径: {doc.file_url}")
            print(f"  当前状态: {doc.status}")

            # 更新状态为 processing
            await session.execute(
                text("UPDATE knowledge_documents SET status = 'processing' WHERE id = :id"),
                {"id": doc.id}
            )
            await session.commit()

            try:
                # 如果是重新处理，先删除旧向量
                if doc.status == 'failed':
                    await vector_store.delete_document_chunks(doc.vector_collection, doc.id)
                    print(f"  已删除旧向量")

                # 处理文档
                result = await processor.process_document(
                    doc_id=doc.id,
                    file_path=doc.file_url,
                    file_type=doc.file_type,
                    document_title=doc.title,
                    knowledge_base_id=doc.knowledge_base_id,
                    vector_collection=doc.vector_collection,
                )

                # 更新最终状态
                await session.execute(
                    text('''
                        UPDATE knowledge_documents
                        SET status = :status,
                            chunk_count = :chunk_count,
                            error_message = :error_message
                        WHERE id = :id
                    '''),
                    {
                        "id": doc.id,
                        "status": result["status"],
                        "chunk_count": result["chunk_count"],
                        "error_message": result.get("error_message")
                    }
                )
                await session.commit()

                if result["status"] == DocumentStatus.READY.value:
                    print(f"  ✅ 处理成功！切片数: {result['chunk_count']}")
                else:
                    print(f"  ❌ 处理失败: {result.get('error_message')}")

            except Exception as e:
                await session.execute(
                    text('''
                        UPDATE knowledge_documents
                        SET status = 'failed', error_message = :error
                        WHERE id = :id
                    '''),
                    {"id": doc.id, "error": str(e)}
                )
                await session.commit()
                print(f"  ❌ 处理异常: {e}")

            print()

    await engine.dispose()
    print("处理完成！")

if __name__ == '__main__':
    asyncio.run(process_pending_documents())
