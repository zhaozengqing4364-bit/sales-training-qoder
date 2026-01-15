/**
 * use{HookName} - {简短描述}
 * 
 * 使用方法:
 * 1. 复制此文件到 frontend/src/hooks/
 * 2. 替换 {HookName} 等占位符
 * 3. 实现 Hook 逻辑
 */
import { useState, useEffect, useCallback } from 'react';
import { apiRequest } from '@/lib/api';

// ========== 类型定义 ==========

interface {HookName}Options {
  // 配置选项
  autoFetch?: boolean;
}

interface {HookName}Result<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

// ========== Hook 实现 ==========

export function use{HookName}<T>(
  endpoint: string,
  options: {HookName}Options = {}
): {HookName}Result<T> {
  const { autoFetch = true } = options;
  
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(autoFetch);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const { success, data: responseData, error: responseError } = 
        await apiRequest<T>(endpoint);
      
      if (success) {
        setData(responseData ?? null);
      } else {
        // 根据错误码处理
        switch (responseError) {
          case '[UNAUTHORIZED]':
            // 跳转登录
            break;
          case '[PLEASE_TRY_AGAIN]':
            setError('请稍后重试');
            break;
          default:
            setError(responseError ?? '加载失败');
        }
      }
    } catch (e) {
      setError('网络连接失败');
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  useEffect(() => {
    if (autoFetch) {
      fetchData();
    }
  }, [autoFetch, fetchData]);

  return { data, loading, error, refetch: fetchData };
}
