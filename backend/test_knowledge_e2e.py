"""
知识库端到端测试脚本

测试流程：
1. 创建知识库
2. 上传文档
3. 等待文档处理完成
4. 测试向量检索
5. 清理测试数据
"""
import asyncio
import os
import sys

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# 导入所有模型以确保关系正确注册（顺序很重要！）
# 1. 先导入 Base
from common.db.models import Base  # noqa: F401
# 2. 导入 Agent 平台模型（被 PracticeSession 引用）
from agent.models import Agent, Persona  # noqa: F401
# 3. 导入对话模型（被 PracticeSession 引用）
from common.conversation.models import ConversationMessage  # noqa: F401
# 4. 导入知识库模型
from common.knowledge.models import KnowledgeBase, KnowledgeDocument  # noqa: F401

# 确保所有模型都注册到 Base.metadata
# 这是解决 SQLAlchemy relationship 找不到模型的关键
import common.db.models  # noqa: F401

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.knowledge.service import KnowledgeService
from common.knowledge.schemas import CreateKnowledgeBaseRequest
from common.knowledge.processor import get_document_processor
from common.knowledge.vector_store import get_knowledge_vector_store
from common.ai.embedding_service import get_embedding_service
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


async def test_knowledge_e2e():
    """测试知识库端到端流程"""
    
    # 1. 检查 Embedding 服务配置
    print("\n=== 1. 检查 Embedding 服务 ===")
    embedding_service = get_embedding_service()
    print(f"Embedding 服务已配置: {embedding_service.is_configured}")
    
    if not embedding_service.is_configured:
        print("❌ Embedding 服务未配置，请检查 OPENAI_API_KEY 环境变量")
        return False
    
    # 测试 embedding
    test_text = "这是一个测试文本"
    embed_result = await embedding_service.embed(test_text)
    if embed_result.is_success:
        print(f"✅ Embedding 测试成功，向量维度: {len(embed_result.value)}")
    else:
        print(f"❌ Embedding 测试失败: {embed_result.error}")
        return False
    
    # 2. 创建数据库连接
    print("\n=== 2. 连接数据库 ===")
    from common.db.session import get_database_url
    db_url = get_database_url()
    print(f"数据库 URL: {db_url[:50]}...")
    
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        service = KnowledgeService(session)
        
        # 3. 创建测试知识库
        print("\n=== 3. 创建测试知识库 ===")
        create_request = CreateKnowledgeBaseRequest(
            name="测试知识库",
            description="用于端到端测试",
            category="product"  # 有效值: product, competitor, faq, policy
        )
        
        result = await service.create(create_request)
        if not result.is_success:
            print(f"❌ 创建知识库失败: {result.fallback}")
            return False
        
        kb = result.value
        print(f"✅ 知识库创建成功: {kb.id}")
        print(f"   名称: {kb.name}")
        print(f"   向量集合: {kb.vector_collection}")
        
        await session.commit()
        
        # 4. 创建测试文档
        print("\n=== 4. 创建测试文档 ===")
        test_content = """
# 销售技巧指南

## 开场白技巧
1. 微笑问候，建立亲和力
2. 快速了解客户需求
3. 展示专业知识

## 产品介绍
- 突出产品优势
- 针对客户痛点
- 提供解决方案

## 异议处理
当客户说"太贵了"时：
- 强调价值而非价格
- 提供分期付款选项
- 对比竞品优势

## 成交技巧
- 识别购买信号
- 适时提出成交
- 处理最后异议
"""
        
        # 保存测试文档
        import uuid
        doc_id = str(uuid.uuid4())
        
        # 确保目录存在
        doc_dir = f"./data/documents/{kb.id}"
        os.makedirs(doc_dir, exist_ok=True)
        
        doc_path = f"{doc_dir}/{doc_id}.md"
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(test_content)
        
        print(f"✅ 测试文档已保存: {doc_path}")
        
        # 创建文档记录
        doc_result = await service.create_document_with_id(
            doc_id=doc_id,
            kb_id=kb.id,
            title="销售技巧指南",
            file_type="md",
            file_url=doc_path,
            file_size=len(test_content.encode("utf-8"))
        )
        
        if not doc_result.is_success:
            print(f"❌ 创建文档记录失败: {doc_result.fallback}")
            return False
        
        doc = doc_result.value
        print(f"✅ 文档记录创建成功: {doc.id}")
        await session.commit()
        
        # 5. 处理文档（分块 + 向量化）
        print("\n=== 5. 处理文档 ===")
        processor = get_document_processor()
        
        process_result = await processor.process_document(
            doc_id=doc.id,
            file_path=doc_path,
            file_type="md",
            document_title="销售技巧指南",
            knowledge_base_id=kb.id,
            vector_collection=kb.vector_collection
        )
        
        print(f"处理结果: {process_result}")
        
        if process_result["status"] != "ready":
            print(f"❌ 文档处理失败: {process_result.get('error_message')}")
            return False
        
        print(f"✅ 文档处理成功，分块数: {process_result['chunk_count']}")
        
        # 更新文档状态
        await service.update_document_status(
            doc_id=doc.id,
            status="ready",
            chunk_count=process_result["chunk_count"]
        )
        await session.commit()
        
        # 6. 测试向量检索
        print("\n=== 6. 测试向量检索 ===")
        
        test_queries = [
            "客户说太贵了怎么办",
            "如何开场",
            "成交技巧有哪些"
        ]
        
        for query in test_queries:
            print(f"\n查询: {query}")
            search_result = await service.search(
                kb_id=kb.id,
                query=query,
                top_k=2,
                similarity_threshold=0.5
            )
            
            if search_result.is_success:
                results = search_result.value
                print(f"  找到 {len(results)} 个结果:")
                for r in results:
                    score = r.get("score", 0)
                    content = r.get("content", "")[:100]
                    print(f"    - 相似度: {score:.3f}")
                    print(f"      内容: {content}...")
            else:
                print(f"  ❌ 检索失败: {search_result.error}")
        
        # 7. 清理测试数据
        print("\n=== 7. 清理测试数据 ===")
        
        # 删除向量
        vector_store = get_knowledge_vector_store()
        await vector_store.delete_collection(kb.vector_collection)
        print("✅ 向量集合已删除")
        
        # 删除文档文件
        if os.path.exists(doc_path):
            os.remove(doc_path)
            print("✅ 文档文件已删除")
        
        # 删除知识库记录
        await service.delete(kb.id)
        await session.commit()
        print("✅ 知识库记录已删除")
    
    await engine.dispose()
    
    print("\n=== 测试完成 ===")
    print("✅ 知识库端到端测试通过！")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_knowledge_e2e())
    sys.exit(0 if success else 1)
