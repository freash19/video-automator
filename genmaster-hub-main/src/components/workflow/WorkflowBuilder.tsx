import { useEffect, useState } from "react";
import {
  MousePointerClick,
  Type,
  Navigation,
  Clock,
  Download,
  GripVertical,
  Plus,
  Trash2,
  ChevronDown,
  ChevronUp,
  Code2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

export interface Locator {
  name: string;
  selector: string;
}

interface WorkflowStep {
  id: string;
  type: string;
  params: Record<string, unknown>;
  enabled?: boolean;
}

const stepIcons = {
  click: MousePointerClick,
  fill: Type,
  navigate: Navigation,
  wait: Clock,
  download: Download,
};

const stepColors = {
  click: "text-primary bg-primary/10",
  fill: "text-success bg-success/10",
  navigate: "text-warning bg-warning/10",
  wait: "text-muted-foreground bg-muted",
  download: "text-purple-400 bg-purple-400/10",
};

interface Props {
  steps: WorkflowStep[];
  onStepsChange: (steps: WorkflowStep[]) => void;
  onSave?: () => void;
  locators: Locator[];
}

const STEP_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "navigate", label: "Navigate" },
  { value: "wait_for", label: "Wait For Selector" },
  { value: "wait", label: "Wait (Sleep)" },
  { value: "click", label: "Click" },
  { value: "fill", label: "Fill" },
  { value: "press", label: "Press Key" },
  { value: "select_episode_parts", label: "Select Episode Parts" },
  { value: "fill_scene", label: "Fill All Scenes" },
  { value: "delete_empty_scenes", label: "Delete Empty Scenes" },
  { value: "save", label: "Save" },
  { value: "reload", label: "Reload" },
  { value: "reload_and_validate", label: "Reload And Validate" },
  { value: "handle_broll", label: "Handle B-Roll" },
  { value: "generate", label: "Generate" },
  { value: "final_submit", label: "Final Submit" },
  { value: "confirm", label: "Confirm" },
];

const WAIT_UNTIL_OPTIONS = ["domcontentloaded", "load", "networkidle"] as const;
const WAIT_STATE_OPTIONS = ["attached", "detached", "visible", "hidden"] as const;

function oneOf<T extends readonly string[]>(vals: T, v: string, fallback: T[number]): T[number] {
  return (vals as readonly string[]).includes(v) ? (v as T[number]) : fallback;
}

function asString(v: unknown): string {
  if (v === null || v === undefined) return "";
  return String(v);
}

function asNumberString(v: unknown): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return s === "NaN" ? "" : s;
}

export function WorkflowBuilder({ steps, onStepsChange, onSave, locators }: Props) {
  const [localSteps, setLocalSteps] = useState<WorkflowStep[]>(steps);
  const [jsonStepIndex, setJsonStepIndex] = useState<number | null>(null);
  const [jsonDraft, setJsonDraft] = useState<string>("");
  const [jsonError, setJsonError] = useState<string>("");

  useEffect(() => {
    setLocalSteps(steps);
  }, [steps]);

  const moveStep = (index: number, direction: "up" | "down") => {
    const newSteps = [...localSteps];
    const newIndex = direction === "up" ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= localSteps.length) return;
    [newSteps[index], newSteps[newIndex]] = [newSteps[newIndex], newSteps[index]];
    setLocalSteps(newSteps);
    onStepsChange(newSteps);
  };

  const toggleStep = (id: string) => {
    const s = localSteps.map((step) => (step.id === id ? { ...step, enabled: !step.enabled } : step));
    setLocalSteps(s);
    onStepsChange(s);
  };

  const deleteStep = (id: string) => {
    const s = localSteps.filter((step) => step.id !== id);
    setLocalSteps(s);
    onStepsChange(s);
  };

  const addStep = () => {
    const newStep: WorkflowStep = {
      id: crypto.randomUUID(),
      type: "click",
      params: {},
      enabled: true,
    };
    const s = [...localSteps, newStep];
    setLocalSteps(s);
    onStepsChange(s);
  };

  const updateStep = (index: number, patch: Partial<WorkflowStep>) => {
    const s = [...localSteps];
    s[index] = { ...s[index], ...patch };
    setLocalSteps(s);
    onStepsChange(s);
  };

  const openStepJson = (index: number) => {
    const step = localSteps[index];
    if (!step) return;
    setJsonError("");
    setJsonStepIndex(index);
    setJsonDraft(JSON.stringify(step, null, 2));
  };

  const applyStepJson = () => {
    if (jsonStepIndex === null) return;
    try {
      const parsed = JSON.parse(jsonDraft || "{}");
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        setJsonError("JSON должен быть объектом шага");
        return;
      }
      const obj = parsed as Record<string, unknown>;
      const curr = localSteps[jsonStepIndex];
      const next: WorkflowStep = {
        id: String(obj.id || curr?.id || crypto.randomUUID()),
        type: String(obj.type || curr?.type || "click"),
        params:
          obj.params && typeof obj.params === "object" && !Array.isArray(obj.params)
            ? (obj.params as Record<string, unknown>)
            : {},
        enabled: typeof obj.enabled === "boolean" ? obj.enabled : curr?.enabled ?? true,
      };
      updateStep(jsonStepIndex, next);
      setJsonStepIndex(null);
    } catch (e) {
      setJsonError(String((e as Error)?.message || e || "Не удалось распарсить JSON"));
    }
  };

  const updateParams = (index: number, patch: Record<string, unknown>) => {
    const curr = localSteps[index];
    const nextParams = { ...(curr?.params || {}), ...patch };
    updateStep(index, { params: nextParams });
  };

  const setParam = (index: number, key: string, value: unknown) => {
    updateParams(index, { [key]: value });
  };

  const clearParam = (index: number, key: string) => {
    const curr = localSteps[index];
    if (!curr) return;
    const next = { ...(curr.params || {}) };
    delete next[key];
    updateStep(index, { params: next });
  };

  const renderParamsEditor = (step: WorkflowStep, index: number) => {
    const t = String(step.type || "").trim();
    const params = step.params || {};
    const selectorValue = asString(params["selector"]);
    const locatorSelected = locators.find((l) => l.selector === selectorValue) || locators.find((l) => l.name === selectorValue);

    if (t === "navigate" || t === "navigate_to_template") {
      const url = asString(params["url"]);
      const waitUntil = asString(params["wait_until"] || "domcontentloaded");
      const timeoutMs = asNumberString(params["timeout_ms"]);
      return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <div className="md:col-span-2">
            <Input
              placeholder="URL (leave empty to use template_url)"
              value={url}
              onChange={(e) => {
                const v = e.target.value;
                if (!v.trim()) clearParam(index, "url");
                else setParam(index, "url", v);
              }}
            />
          </div>
          <Select
            value={oneOf(WAIT_UNTIL_OPTIONS, waitUntil, "domcontentloaded")}
            onValueChange={(v) => setParam(index, "wait_until", v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="wait_until" />
            </SelectTrigger>
            <SelectContent>
              {WAIT_UNTIL_OPTIONS.map((v) => (
                <SelectItem key={v} value={v}>
                  {v}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            placeholder="timeout_ms (e.g. 120000)"
            value={timeoutMs}
            onChange={(e) => {
              const v = e.target.value.trim();
              if (!v) clearParam(index, "timeout_ms");
              else setParam(index, "timeout_ms", Number(v));
            }}
          />
        </div>
      );
    }

    if (t === "wait_for" || t === "wait_for_selector") {
      const timeoutMs = asNumberString(params["timeout_ms"]);
      const state = asString(params["state"] || "visible");
      return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <div className="md:col-span-2">
            <Select
              value={locatorSelected?.name || ""}
              onValueChange={(v) => {
                const loc = locators.find((l) => l.name === v);
                if (loc) setParam(index, "selector", loc.selector);
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Selector from library" />
              </SelectTrigger>
              <SelectContent>
                {locators.map((l) => (
                  <SelectItem key={l.name} value={l.name}>
                    {l.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Select
            value={oneOf(WAIT_STATE_OPTIONS, state, "visible")}
            onValueChange={(v) => setParam(index, "state", v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="state" />
            </SelectTrigger>
            <SelectContent>
              {WAIT_STATE_OPTIONS.map((v) => (
                <SelectItem key={v} value={v}>
                  {v}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            placeholder="timeout_ms (e.g. 30000)"
            value={timeoutMs}
            onChange={(e) => {
              const v = e.target.value.trim();
              if (!v) clearParam(index, "timeout_ms");
              else setParam(index, "timeout_ms", Number(v));
            }}
          />
        </div>
      );
    }

    if (t === "wait" || t === "sleep") {
      const sec = asNumberString(params["sec"]);
      return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <Input
            placeholder="sec (e.g. 1.5)"
            value={sec}
            onChange={(e) => {
              const v = e.target.value.trim();
              if (!v) clearParam(index, "sec");
              else setParam(index, "sec", Number(v));
            }}
          />
        </div>
      );
    }

    if (t === "click") {
      const which = asString(params["which"]);
      const timeoutMs = asNumberString(params["timeout_ms"]);
      const whichMode = which === "last" ? "last" : which && /^\d+$/.test(which) ? "nth" : "first";
      const nth = whichMode === "nth" ? which : "";
      return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <div className="md:col-span-2">
            <Select
              value={locatorSelected?.name || ""}
              onValueChange={(v) => {
                const loc = locators.find((l) => l.name === v);
                if (loc) setParam(index, "selector", loc.selector);
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Selector from library" />
              </SelectTrigger>
              <SelectContent>
                {locators.map((l) => (
                  <SelectItem key={l.name} value={l.name}>
                    {l.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Select
            value={whichMode}
            onValueChange={(v) => {
              if (v === "first") clearParam(index, "which");
              else if (v === "last") setParam(index, "which", "last");
              else setParam(index, "which", "0");
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="which" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="first">first</SelectItem>
              <SelectItem value="last">last</SelectItem>
              <SelectItem value="nth">nth</SelectItem>
            </SelectContent>
          </Select>
          {whichMode === "nth" ? (
            <Input
              placeholder="nth index (0-based)"
              value={nth}
              onChange={(e) => {
                const v = e.target.value.trim();
                if (!v) setParam(index, "which", "0");
                else setParam(index, "which", v.replace(/[^\d]/g, "") || "0");
              }}
            />
          ) : (
            <Input
              placeholder="timeout_ms (optional)"
              value={timeoutMs}
              onChange={(e) => {
                const v = e.target.value.trim();
                if (!v) clearParam(index, "timeout_ms");
                else setParam(index, "timeout_ms", Number(v));
              }}
            />
          )}
          {whichMode === "nth" && (
            <Input
              placeholder="timeout_ms (optional)"
              value={timeoutMs}
              onChange={(e) => {
                const v = e.target.value.trim();
                if (!v) clearParam(index, "timeout_ms");
                else setParam(index, "timeout_ms", Number(v));
              }}
            />
          )}
        </div>
      );
    }

    if (t === "fill") {
      const text = asString(params["text"]);
      return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <div className="md:col-span-1">
            <Select
              value={locatorSelected?.name || ""}
              onValueChange={(v) => {
                const loc = locators.find((l) => l.name === v);
                if (loc) setParam(index, "selector", loc.selector);
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Selector from library" />
              </SelectTrigger>
              <SelectContent>
                {locators.map((l) => (
                  <SelectItem key={l.name} value={l.name}>
                    {l.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <textarea
            className="md:col-span-2 px-2 py-2 rounded bg-muted/30 text-sm"
            rows={2}
            placeholder="Text (supports \\n). You can use {{episode_id}}, {{part_idx}}, {{template_url}}"
            value={text}
            onChange={(e) => setParam(index, "text", e.target.value)}
          />
        </div>
      );
    }

    if (t === "press") {
      const key = asString(params["key"]);
      return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <div className="md:col-span-2">
            <Select
              value={locatorSelected?.name || ""}
              onValueChange={(v) => {
                const loc = locators.find((l) => l.name === v);
                if (loc) setParam(index, "selector", loc.selector);
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Selector from library" />
              </SelectTrigger>
              <SelectContent>
                {locators.map((l) => (
                  <SelectItem key={l.name} value={l.name}>
                    {l.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Input placeholder="key (e.g. Enter)" value={key} onChange={(e) => setParam(index, "key", e.target.value)} />
        </div>
      );
    }

    if (t === "fill_scene") {
      const inlineBroll = params["handle_broll"];
      return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <Select
            value={inlineBroll === false ? "false" : inlineBroll === true ? "true" : "auto"}
            onValueChange={(v) => {
              if (v === "auto") clearParam(index, "handle_broll");
              else setParam(index, "handle_broll", v === "true");
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="handle_broll" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="auto">auto</SelectItem>
              <SelectItem value="true">true</SelectItem>
              <SelectItem value="false">false</SelectItem>
            </SelectContent>
          </Select>
        </div>
      );
    }

    if (t === "delete_empty_scenes") {
      const maxScenes = asNumberString(params["max_scenes"]);
      return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <Input
            placeholder="max_scenes (optional)"
            value={maxScenes}
            onChange={(e) => {
              const v = e.target.value.trim();
              if (!v) clearParam(index, "max_scenes");
              else setParam(index, "max_scenes", Number(v));
            }}
          />
        </div>
      );
    }

    return (
      <textarea
        className="w-full px-2 py-2 rounded bg-muted/30 text-xs font-mono"
        rows={3}
        value={JSON.stringify(step.params)}
        onChange={(e) => {
          try {
            const obj = JSON.parse(e.target.value || "{}");
            updateStep(index, { params: obj });
          } catch {
            return;
          }
        }}
      />
    );
  };

  return (
    <div className="rounded-xl border border-border shadow-card h-full flex flex-col">
      <Dialog
        open={jsonStepIndex !== null}
        onOpenChange={(open) => {
          if (!open) setJsonStepIndex(null);
        }}
      >
        <DialogContent className="max-w-4xl w-[95vw]" onOpenAutoFocus={(e) => e.preventDefault()}>
          <DialogHeader>
            <DialogTitle>JSON шага</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <textarea
              className="w-full px-3 py-2 rounded bg-muted/30 text-xs font-mono min-h-[360px]"
              value={jsonDraft}
              onChange={(e) => setJsonDraft(e.target.value)}
            />
            {jsonError ? <div className="text-xs text-destructive">{jsonError}</div> : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setJsonStepIndex(null)}>
              Отмена
            </Button>
            <Button onClick={applyStepJson}>Применить</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-foreground">Workflow Builder</h3>
          <div className="flex items-center gap-2">
          <Button size="sm" onClick={addStep}>
            <Plus className="w-4 h-4 mr-1" />
            Add Step
          </Button>
          {onSave && (
            <Button size="sm" variant="secondary" onClick={onSave}>
              Save
            </Button>
          )}
          </div>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Define the automation steps in order
        </p>
      </div>

      {/* Steps List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2 scrollbar-thin">
        {localSteps.map((step, index) => {
          const Icon = stepIcons[(step.type as keyof typeof stepIcons) || "click"] || MousePointerClick;
          const colorClass =
            stepColors[(step.type as keyof typeof stepColors) || "click"] || "text-muted-foreground bg-muted/30";
          return (
            <div
              key={step.id}
              className={cn(
                "group p-4 rounded-lg border transition-all duration-200",
                step.enabled
                  ? "border-border bg-card hover:border-muted-foreground/50"
                  : "border-border/50 bg-muted/30 opacity-60"
              )}
            >
              <div className="flex items-center gap-3">
                {/* Drag Handle */}
                <div className="cursor-grab text-muted-foreground hover:text-foreground">
                  <GripVertical className="w-4 h-4" />
                </div>

                {/* Step Number */}
                <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center text-xs font-mono text-muted-foreground">
                  {index + 1}
                </div>

                {/* Icon */}
                <div className={cn("p-2 rounded-lg", colorClass)}>
                  <Icon className="w-4 h-4" />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground">{step.type}</span>
                    <Badge variant="secondary" className="text-[10px]">
                      {step.id}
                    </Badge>
                  </div>
                  <div className="text-xs text-muted-foreground truncate mt-0.5">
                    {Object.entries(step.params).map(([k, v]) => `${k}: ${v}`).join(" • ")}
                  </div>
                  <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-2">
                    <Select
                      value={step.type || ""}
                      onValueChange={(v) => {
                        updateStep(index, { type: v, params: {} });
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Step type" />
                      </SelectTrigger>
                      <SelectContent>
                        {STEP_TYPE_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <div className="md:col-span-2">{renderParamsEditor(step, index)}</div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => moveStep(index, "up")}
                    disabled={index === 0}
                  >
                    <ChevronUp className="w-3 h-3" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => moveStep(index, "down")}
                    disabled={index === steps.length - 1}
                  >
                    <ChevronDown className="w-3 h-3" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => openStepJson(index)}
                    aria-label="Редактировать JSON шага"
                  >
                    <Code2 className="w-3 h-3" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className={cn("h-7 w-7", !step.enabled && "text-success")}
                    onClick={() => toggleStep(step.id)}
                  >
                    {step.enabled ? (
                      <span className="text-[10px] font-medium">ON</span>
                    ) : (
                      <span className="text-[10px] font-medium">OFF</span>
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-destructive hover:text-destructive"
                    onClick={() => deleteStep(step.id)}
                  >
                    <Trash2 className="w-3 h-3" />
                  </Button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-border bg-muted/20">
        <p className="text-xs text-muted-foreground text-center">
          {steps.filter((s) => s.enabled).length} of {steps.length} steps enabled
        </p>
      </div>
    </div>
  );
}
