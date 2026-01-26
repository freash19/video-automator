import { Play, RotateCcw, Plus, FileSpreadsheet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";

export function QuickActions() {
  const navigate = useNavigate();

  const actions = [
    {
      icon: Play,
      label: "Продолжить запуск",
      description: "Продолжить с последнего места",
      variant: "glow" as const,
      onClick: () => navigate("/runner"),
    },
    {
      icon: Plus,
      label: "Начать новый пакет",
      description: "Запустить новую обработку",
      variant: "secondary" as const,
      onClick: () => navigate("/data-studio"),
    },
    {
      icon: FileSpreadsheet,
      label: "Импорт данных",
      description: "Загрузить CSV или вставить текст",
      variant: "outline" as const,
      onClick: () => navigate("/data-studio"),
    },
    {
      icon: RotateCcw,
      label: "Перезапуск ошибок",
      description: "Только эпизоды с ошибкой",
      variant: "outline" as const,
      onClick: () => navigate("/runner"),
    },
  ];

  return (
    <div className="rounded-xl border border-border p-6 shadow-card">
      <h3 className="text-lg font-semibold text-foreground mb-4">Быстрые действия</h3>
      <div className="grid grid-cols-2 gap-3">
        {actions.map((action) => {
          const Icon = action.icon;
          return (
            <Button
              key={action.label}
              variant={action.variant}
              className="h-auto flex-col items-start gap-2 p-4 text-left"
              onClick={action.onClick}
            >
              <div className="flex items-center gap-2">
                <Icon className="w-4 h-4" />
                <span className="font-medium">{action.label}</span>
              </div>
              <span className="text-xs text-muted-foreground font-normal">
                {action.description}
              </span>
            </Button>
          );
        })}
      </div>
    </div>
  );
}
