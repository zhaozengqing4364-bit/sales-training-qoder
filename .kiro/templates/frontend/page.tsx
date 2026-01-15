/**
 * {PageName}Page - {简短描述}
 * 
 * 使用方法:
 * 1. 复制此文件到 frontend/src/pages/
 * 2. 替换 {PageName} 等占位符
 * 3. 在 router.tsx 中注册路由
 * 
 * 设计规范:
 * - 使用 PageLayout 布局
 * - 使用 BentoGrid 网格
 * - 遵循 Modern Soft UI 风格
 */
import { PageLayout } from '@/design-system/layouts/PageLayout';
import { BentoGrid, BentoItem } from '@/design-system/layouts/BentoGrid';
import { Card } from '@/design-system/primitives/Card';
import { Button } from '@/design-system/primitives/Button';
import { Badge } from '@/design-system/primitives/Badge';

// ========== 页面组件 ==========

export default function {PageName}Page() {
  return (
    <PageLayout
      title="{页面标题}"
      description="{页面描述}"
    >
      {/* 页面头部 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">
            {页面标题}
          </h1>
          <p className="mt-1 text-slate-500">
            {页面描述}
          </p>
        </div>
        <Button variant="primary">
          主要操作
        </Button>
      </div>

      {/* 内容区域 - Bento Grid */}
      <BentoGrid cols={3} gap="md">
        <BentoItem colSpan={2}>
          <Card hoverable>
            <h3 className="text-lg font-semibold text-slate-900">
              主要内容
            </h3>
            <p className="mt-2 text-slate-500">
              内容描述...
            </p>
          </Card>
        </BentoItem>
        
        <BentoItem>
          <Card>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">状态</span>
              <Badge variant="success" dot>
                正常
              </Badge>
            </div>
          </Card>
        </BentoItem>
        
        <BentoItem>
          <Card hoverable>
            <h4 className="font-medium text-slate-900">卡片 1</h4>
          </Card>
        </BentoItem>
        
        <BentoItem>
          <Card hoverable>
            <h4 className="font-medium text-slate-900">卡片 2</h4>
          </Card>
        </BentoItem>
        
        <BentoItem>
          <Card hoverable>
            <h4 className="font-medium text-slate-900">卡片 3</h4>
          </Card>
        </BentoItem>
      </BentoGrid>
    </PageLayout>
  );
}
