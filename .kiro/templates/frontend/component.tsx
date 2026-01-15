/**
 * {ComponentName} - {简短描述}
 * 
 * 使用方法:
 * 1. 复制此文件到 frontend/src/design-system/primitives/ 或 features/{module}/
 * 2. 替换 {ComponentName} 等占位符
 * 3. 实现组件逻辑
 * 
 * 设计规范:
 * - 使用 Design Tokens，不直接写 Tailwind 类名
 * - 支持 variant 变体
 * - 使用 cn() 合并类名
 */
import { forwardRef, HTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

// ========== 类型定义 ==========

export interface {ComponentName}Props extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'primary' | 'secondary';
  size?: 'sm' | 'md' | 'lg';
}

// ========== 样式定义 ==========

const variantStyles = {
  default: cn(
    'bg-white',
    'border border-gray-100',
    'shadow-[0_8px_30px_rgb(0,0,0,0.04)]'
  ),
  primary: cn(
    'bg-slate-900 text-white',
    'shadow-lg shadow-slate-900/20'
  ),
  secondary: cn(
    'bg-white text-slate-700',
    'border border-slate-200',
    'hover:bg-slate-50'
  ),
};

const sizeStyles = {
  sm: 'p-4 text-sm',
  md: 'p-6 text-base',
  lg: 'p-8 text-lg',
};

// ========== 组件实现 ==========

export const {ComponentName} = forwardRef<HTMLDivElement, {ComponentName}Props>(
  ({ className, variant = 'default', size = 'md', children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          // 基础样式
          'rounded-2xl',
          'transition-all duration-200',
          
          // 变体样式
          variantStyles[variant],
          
          // 尺寸样式
          sizeStyles[size],
          
          // 自定义类名
          className
        )}
        {...props}
      >
        {children}
      </div>
    );
  }
);

{ComponentName}.displayName = '{ComponentName}';
