import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Database,
  GitBranch,
  FileText,
  Settings,
  Play,
  ChevronLeft,
  ChevronRight,
  Zap,
  FolderOutput,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const navItems = [
  { path: "/", icon: LayoutDashboard, label: "Панель", description: "Обзор и статистика" },
  { path: "/data-studio", icon: Database, label: "Студия данных", description: "Шаг 1: Импорт данных" },
  { path: "/workflow", icon: GitBranch, label: "Воркфлоу", description: "Шаг 2: Конструктор" },
  { path: "/scripts", icon: FileText, label: "Сценарии", description: "Эпизоды и проекты" },
  { path: "/settings", icon: Settings, label: "Настройки", description: "Конфигурация" },
  { path: "/runner", icon: Play, label: "Запуск", description: "Выполнение автоматизации" },
  { path: "/results", icon: FolderOutput, label: "Результаты", description: "Выходные видео" },
];

export function AppSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  return (
    <aside
      className={cn(
        "relative flex flex-col h-screen border-r border-sidebar-border bg-sidebar transition-all duration-300",
        collapsed ? "w-[72px]" : "w-[260px]"
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 p-4 border-b border-sidebar-border">
        <div className="flex items-center justify-center w-10 h-10 rounded-xl gradient-primary shadow-glow">
          <Zap className="w-5 h-5 text-primary-foreground" />
        </div>
        {!collapsed && (
          <div className="flex flex-col animate-fade-in">
            <span className="text-sm font-semibold text-foreground">HeyGen</span>
            <span className="text-xs text-muted-foreground">Automation Pro</span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto scrollbar-thin">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          const Icon = item.icon;

          const linkContent = (
            <NavLink
              to={item.path}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 group",
                isActive
                  ? "bg-sidebar-accent text-sidebar-primary"
                  : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              )}
            >
              <div
                className={cn(
                  "flex items-center justify-center w-8 h-8 rounded-lg transition-all duration-200",
                  isActive
                    ? "bg-primary/20 text-primary"
                    : "bg-muted/50 text-muted-foreground group-hover:bg-accent group-hover:text-accent-foreground"
                )}
              >
                <Icon className="w-4 h-4" />
              </div>
              {!collapsed && (
                <div className="flex flex-col animate-fade-in">
                  <span className="text-sm font-medium">{item.label}</span>
                  <span className="text-[10px] text-muted-foreground">{item.description}</span>
                </div>
              )}
              {isActive && !collapsed && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              )}
            </NavLink>
          );

          if (collapsed) {
            return (
              <Tooltip key={item.path} delayDuration={0}>
                <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
                <TooltipContent side="right" className="flex flex-col gap-0.5">
                  <span className="font-medium">{item.label}</span>
                  <span className="text-xs text-muted-foreground">{item.description}</span>
                </TooltipContent>
              </Tooltip>
            );
          }

          return <div key={item.path}>{linkContent}</div>;
        })}
      </nav>

      {/* Collapse Toggle */}
      <div className="p-3 border-t border-sidebar-border">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setCollapsed(!collapsed)}
          className="w-full justify-center"
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <>
              <ChevronLeft className="w-4 h-4" />
              <span className="animate-fade-in">Свернуть</span>
            </>
          )}
        </Button>
      </div>
    </aside>
  );
}
