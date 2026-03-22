"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import { Agent } from "@/lib/api/types";
import { AgentCard } from "@/components/ui/agent-card";
import { GlassCard } from "@/components/ui/glass-card";

export interface ScenarioListProps {
  category: "sales" | "presentation";
  title: string;
  description: string;
  actionText: string;
  gridCols?: 2 | 3;
}

export function ScenarioList({
  category,
  title,
  description,
  actionText,
  gridCols = 2,
}: ScenarioListProps) {
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadAgents = async () => {
      try {
        const data = await api.agents.getList(category);
        setAgents(data);
      } catch (err) {
        console.error(`Failed to load ${category} agents:`, err);
        setError(`暂无${title}场景`);
      } finally {
        setIsLoading(false);
      }
    };
    loadAgents();
  }, [category, title]);

  const handleAgentClick = (agentId: string) => {
    router.push(`/agents/${agentId}`);
  };

  const gridClassName =
    gridCols === 3
      ? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"
      : "grid grid-cols-1 md:grid-cols-2 gap-6";

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 pb-20">
      <div className="flex flex-col gap-6">
        <Button
          variant="ghost"
          className="w-fit pl-0 text-slate-500 hover:text-slate-900 hover:bg-transparent gap-2"
          onClick={() => router.back()}
        >
          <ArrowLeft className="w-4 h-4" />
          返回训练大厅
        </Button>

        <div className="flex justify-between items-end">
          <div>
            <h1 className="text-3xl font-black text-slate-900 tracking-tight">
              {title}
            </h1>
            <p className="text-slate-500 mt-2 text-lg font-medium">
              {description}
            </p>
          </div>
        </div>
      </div>

      <div className={gridClassName}>
        {isLoading ? (
          Array.from({ length: gridCols === 3 ? 3 : 4 }).map((_, i) => (
            <div
              key={i}
              className="h-64 rounded-3xl bg-white/50 animate-pulse border border-white/60"
            />
          ))
        ) : error || agents.length === 0 ? (
          <GlassCard className="col-span-full p-12 text-center">
            <p className="text-slate-500">
              {error || `暂无${title}场景，请联系管理员添加`}
            </p>
          </GlassCard>
        ) : (
          agents.map((agent) => (
            <AgentCard
              key={agent.id}
              id={agent.id}
              name={agent.name}
              description={agent.description}
              role={agent.role}
              difficulty={agent.difficulty}
              iconKey={agent.ui_metadata?.icon_key}
              themeColor={agent.ui_metadata?.theme_color}
              tags={agent.ui_metadata?.tags}
              category={category}
              actionText={actionText}
              onClick={() => handleAgentClick(agent.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}
