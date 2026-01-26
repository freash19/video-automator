import { useCallback, useEffect, useState } from "react";
import { Locator, LocatorLibrary } from "@/components/workflow/LocatorLibrary";
import { WorkflowBuilder } from "@/components/workflow/WorkflowBuilder";
import { WizardNavigation } from "@/components/common/WizardNavigation";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { API_BASE_URL } from "@/lib/utils";
import { toast } from "sonner";

type WorkflowStep = {
  id: string;
  type: string;
  params: Record<string, unknown>;
  enabled?: boolean;
};

type WorkflowSettings = Record<string, unknown>;

export default function Workflow() {
  const API = API_BASE_URL;
  const [files, setFiles] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [newWfFile, setNewWfFile] = useState<string>("");
  const [wfName, setWfName] = useState<string>("");
  const [steps, setSteps] = useState<WorkflowStep[]>([]);
  const [settings, setSettings] = useState<WorkflowSettings>({});
  const [locators, setLocators] = useState<Locator[]>([]);
  const [automaJson, setAutomaJson] = useState<string>("");
  const [wfJsonOpen, setWfJsonOpen] = useState<boolean>(false);
  const [wfJsonDraft, setWfJsonDraft] = useState<string>("");
  const [wfJsonError, setWfJsonError] = useState<string>("");
  const [inspectorUrl, setInspectorUrl] = useState<string>("https://app.heygen.com/projects");
  const [inspectorTarget, setInspectorTarget] = useState<string>("");

  useEffect(() => {
    const loadFiles = async () => {
      try {
        const res = await fetch(`${API}/workflows`).then((r) => r.json());
        setFiles(res.files || []);
      } catch {
        setFiles([]);
      }
    };
    loadFiles();
  }, [API]);

  const refreshLocators = useCallback(async () => {
    try {
      const res = await fetch(`${API}/locators`).then((r) => r.json());
      const m = (res || {}).locators || {};
      const arr = Object.entries(m)
        .map(([name, selector]) => ({ name: String(name), selector: String(selector) }))
        .sort((a, b) => a.name.localeCompare(b.name));
      setLocators(arr);
    } catch {
      setLocators([]);
    }
  }, [API]);

  useEffect(() => {
    refreshLocators();
  }, [refreshLocators]);

  useEffect(() => {
    const loadOne = async () => {
      if (!selected) return;
      try {
        const wf: { name?: string; steps?: WorkflowStep[]; settings?: WorkflowSettings } = await fetch(`${API}/workflows/${selected}`).then((r) => r.json());
        setWfName(wf.name || selected.replace(".json", ""));
        setSteps((wf.steps || []).map((s) => ({ id: s.id, type: s.type, params: s.params || {}, enabled: s.enabled })));
        setSettings(wf.settings || {});
      } catch {
        setSteps([]);
      }
    };
    loadOne();
  }, [API, selected]);

  const handleSave = async () => {
    const payload = { name: wfName || selected, steps, settings };
    await fetch(`${API}/workflows/${selected}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  };

  const openWorkflowJson = () => {
    setWfJsonError("");
    setWfJsonDraft(JSON.stringify({ name: wfName || selected.replace(/\.json$/i, ""), steps, settings }, null, 2));
    setWfJsonOpen(true);
  };

  const applyWorkflowJson = async () => {
    try {
      const parsed = JSON.parse(wfJsonDraft || "{}");
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        setWfJsonError("JSON воркфлоу должен быть объектом");
        return;
      }
      const res = await fetch(`${API}/workflows/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed),
      });
      if (!res.ok) {
        const msg = await res.text();
        setWfJsonError(msg || "Воркфлоу не прошёл валидацию");
        return;
      }
      const wf: { name?: string; steps?: WorkflowStep[]; settings?: WorkflowSettings } = await res.json();
      setWfName(String(wf.name || ""));
      setSteps((wf.steps || []).map((s) => ({ id: s.id, type: s.type, params: s.params || {}, enabled: s.enabled })));
      setSettings(wf.settings || {});
      await fetch(`${API}/workflows/${selected}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(wf),
      });
      setWfJsonOpen(false);
    } catch (e) {
      setWfJsonError(String((e as Error)?.message || e || "Не удалось распарсить JSON"));
    }
  };
  return (
    <div className="space-y-6 h-full">
      <Dialog open={wfJsonOpen} onOpenChange={setWfJsonOpen}>
        <DialogContent className="max-w-5xl w-[95vw]" onOpenAutoFocus={(e) => e.preventDefault()}>
          <DialogHeader>
            <DialogTitle>JSON воркфлоу</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <textarea
              className="w-full px-3 py-2 rounded bg-muted/30 text-xs font-mono min-h-[420px]"
              value={wfJsonDraft}
              onChange={(e) => setWfJsonDraft(e.target.value)}
            />
            {wfJsonError ? <div className="text-xs text-destructive">{wfJsonError}</div> : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setWfJsonOpen(false)}>
              Отмена
            </Button>
            <Button onClick={applyWorkflowJson} disabled={!selected}>
              Применить и сохранить
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {/* Header */}
      <div className="space-y-1">
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            Воркфлоу и локаторы
          </h1>
          <Badge variant="secondary" className="text-xs">Шаг 2</Badge>
        </div>
        <p className="text-muted-foreground">
          Выберите UI‑элементы и создайте сценарий автоматизации.
        </p>
      </div>

      {/* Workflow selector */}
      <div className="rounded-xl border border-border p-4 shadow-card">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
          <Select value={selected} onValueChange={setSelected}>
            <SelectTrigger className="w-[280px]">
              <SelectValue placeholder="Выберите файл воркфлоу" />
            </SelectTrigger>
            <SelectContent>
              {files.map((f) => (
                <SelectItem key={f} value={f}>
                  {f}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="secondary" onClick={handleSave} disabled={!selected}>
            Сохранить воркфлоу
          </Button>
          <Button variant="outline" onClick={openWorkflowJson} disabled={!selected}>
            JSON воркфлоу
          </Button>
          <Button
            onClick={async () => {
              if (!selected) return;
              const body = new URLSearchParams();
              body.append("workflow", selected);
              await fetch(`${API}/run`, { method: "POST", body });
            }}
            disabled={!selected}
          >
            Тестировать
          </Button>
          </div>
          <div className="flex items-center gap-2">
            <Input
              value={newWfFile}
              onChange={(e) => setNewWfFile(e.target.value)}
              placeholder="Новый воркфлоу (например my_flow.json)"
              className="max-w-[320px]"
            />
            <Button
              variant="outline"
              onClick={async () => {
                const raw = newWfFile.trim();
                if (!raw) return;
                const file = raw.toLowerCase().endsWith(".json") ? raw : `${raw}.json`;
                const payload = { name: raw.replace(/\.json$/i, ""), steps: [], settings: {} };
                await fetch(`${API}/workflows/${encodeURIComponent(file)}`, {
                  method: "PUT",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(payload),
                });
                const res = await fetch(`${API}/workflows`).then((r) => r.json());
                setFiles(res.files || []);
                setSelected(file);
                setNewWfFile("");
              }}
            >
              Создать воркфлоу
            </Button>
            <Button variant="secondary" onClick={refreshLocators}>
              Обновить локаторы
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={inspectorUrl}
              onChange={(e) => setInspectorUrl(e.target.value)}
              placeholder="URL для инспектора"
              className="max-w-[360px]"
            />
            <Input
              value={inspectorTarget}
              onChange={(e) => setInspectorTarget(e.target.value)}
              placeholder="Цель (опционально)"
              className="max-w-[240px]"
            />
            <Button
              variant="outline"
              onClick={async () => {
                try {
                  const res = await fetch(`${API}/inspector/start`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      url: inspectorUrl.trim(),
                      target: inspectorTarget.trim(),
                    }),
                  });
                  if (!res.ok) {
                    const msg = await res.text().catch(() => "");
                    throw new Error(msg || `HTTP ${res.status}`);
                  }
                  toast.success("Инспектор запущен");
                } catch (e) {
                  toast.error("Не удалось запустить инспектор");
                }
              }}
            >
              Запустить инспектор
            </Button>
          </div>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          Выберите сохранённый воркфлоу, редактируйте шаги и параметры, затем сохраните. Каждый шаг можно включать/выключать, менять порядок, параметры принимают JSON.
        </p>
        <div className="mt-3 grid grid-cols-1 lg:grid-cols-5 gap-3">
          <div className="lg:col-span-4">
            <textarea
              className="w-full px-3 py-2 rounded bg-muted/30 text-xs font-mono"
              rows={3}
              placeholder="Импорт из Automa: вставьте экспортированный JSON"
              value={automaJson}
              onChange={(e) => setAutomaJson(e.target.value)}
            />
          </div>
          <div className="lg:col-span-1 flex gap-2 lg:flex-col">
            <Input
              type="file"
              accept="application/json,.json"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                const reader = new FileReader();
                reader.onload = () => {
                  const text = typeof reader.result === "string" ? reader.result : "";
                  if (text) setAutomaJson(text);
                };
                reader.readAsText(file);
              }}
              disabled={!selected}
            />
            <Button
              variant="outline"
              onClick={async () => {
                try {
                  const obj = JSON.parse(automaJson || "{}");
                  const stepsImported = automaToSteps(obj);
                  if (stepsImported.length > 0) {
                    setSteps(stepsImported);
                  }
                  const suggested = extractLocatorsFromSteps(stepsImported, locators);
                  for (const loc of suggested) {
                    await fetch(`${API}/locators`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ name: loc.name, selector: loc.selector }),
                    });
                  }
                  if (suggested.length > 0) await refreshLocators();
                } catch {
                  return;
                }
              }}
              disabled={!selected}
            >
              Импорт Automa
            </Button>
            <Button
              variant="secondary"
              onClick={() => setAutomaJson("")}
              disabled={!automaJson.trim()}
            >
              Очистить
            </Button>
          </div>
        </div>
      </div>

      {/* Split View */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 min-h-[600px]">
        <div className="lg:col-span-2">
          <LocatorLibrary
            locators={locators}
            onCreateLocator={async (loc) => {
              await fetch(`${API}/locators`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: loc.name, selector: loc.selector }),
              });
              await refreshLocators();
            }}
            onDeleteLocator={async (name) => {
              await fetch(`${API}/locators/${encodeURIComponent(name)}`, { method: "DELETE" });
              await refreshLocators();
            }}
          />
        </div>
        <div className="lg:col-span-3">
          <WorkflowBuilder steps={steps} onStepsChange={setSteps} onSave={handleSave} locators={locators} />
        </div>
      </div>

      {/* Wizard Navigation */}
      <WizardNavigation
        backPath="/data-studio"
        backLabel="Студия данных"
        nextPath="/settings"
        nextLabel="Настроить конфигурацию"
      />
    </div>
  );
}

type UnknownRecord = Record<string, unknown>;

function isRecord(v: unknown): v is UnknownRecord {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function getKey(obj: unknown, key: string): unknown {
  return isRecord(obj) ? obj[key] : undefined;
}

type AutomaNode = {
  id: string;
  data: UnknownRecord;
  type?: unknown;
  name?: unknown;
};

type AutomaEdge = {
  source: unknown;
  target: unknown;
};

function automaToSteps(obj: unknown): WorkflowStep[] {
  const normalized = normalizeAutomaPayload(obj);
  const steps: WorkflowStep[] = [];
  const nodes = getAutomaNodes(normalized);
  const edges = getAutomaEdges(normalized);
  if (nodes.length === 0) return [];

  const byId = new Map<string, AutomaNode>();
  for (const n of nodes) byId.set(String(n.id), n);

  const incoming = new Map<string, number>();
  const outgoing = new Map<string, string[]>();
  for (const e of edges) {
    const s = String(e.source || "");
    const t = String(e.target || "");
    if (!s || !t) continue;
    outgoing.set(s, [...(outgoing.get(s) || []), t]);
    incoming.set(t, (incoming.get(t) || 0) + 1);
  }

  for (const [k, arr] of outgoing.entries()) {
    outgoing.set(k, uniq(arr));
  }

  const start =
    nodes.find((n) => isAutomaTriggerBlock(getAutomaBlockName(n))) ||
    nodes.find((n) => (incoming.get(String(n.id)) || 0) === 0) ||
    nodes[0];

  const visited = new Set<string>();
  let curr = start ? String(start.id) : "";
  while (curr && !visited.has(curr)) {
    visited.add(curr);
    const n = byId.get(curr);
    const step = mapAutomaNodeToStep(n);
    if (step) steps.push(step);
    const outs = outgoing.get(curr) || [];
    curr = pickNextNodeId(outs, visited);
  }

  const filtered = steps.filter((s) => s.type !== "trigger");
  return filtered.length > 0 ? filtered : steps;
}

function coerceNode(v: unknown): AutomaNode | null {
  if (!isRecord(v)) return null;
  const id = String(v.id || v.name || cryptoId());
  const dataRaw = (isRecord(v.data) ? v.data : isRecord(v) ? v : {}) as UnknownRecord;
  const data = isRecord(dataRaw) ? dataRaw : {};
  return { id, data, type: v.type, name: v.name };
}

function getAutomaNodes(obj: unknown): AutomaNode[] {
  const d = getKey(obj, "drawflow");
  const dNodes = getKey(d, "nodes");
  if (Array.isArray(dNodes)) {
    return dNodes.map(coerceNode).filter((x): x is AutomaNode => Boolean(x));
  }
  const rootNodes = getKey(obj, "nodes");
  if (Array.isArray(rootNodes)) {
    return rootNodes.map(coerceNode).filter((x): x is AutomaNode => Boolean(x));
  }
  const drawflow2 = getKey(d, "drawflow");
  const home = getKey(drawflow2, "Home");
  const homeData = getKey(home, "data");
  if (isRecord(homeData)) {
    return Object.values(homeData)
      .map(coerceNode)
      .filter((x): x is AutomaNode => Boolean(x));
  }
  return [];
}

function coerceEdge(v: unknown): AutomaEdge | null {
  if (!isRecord(v)) return null;
  return { source: v.source, target: v.target };
}

function getAutomaEdges(obj: unknown): AutomaEdge[] {
  const d = getKey(obj, "drawflow");
  const dEdges = getKey(d, "edges");
  if (Array.isArray(dEdges)) return dEdges.map(coerceEdge).filter((x): x is AutomaEdge => Boolean(x));
  const rootEdges = getKey(obj, "edges");
  if (Array.isArray(rootEdges)) return rootEdges.map(coerceEdge).filter((x): x is AutomaEdge => Boolean(x));
  const drawflow2 = getKey(d, "drawflow");
  const home = getKey(drawflow2, "Home");
  const homeData = getKey(home, "data");
  if (isRecord(homeData)) {
    const edges: AutomaEdge[] = [];
    for (const node of Object.values(homeData)) {
      if (!isRecord(node)) continue;
      const src = String(node.id || "");
      const outputs = getKey(node, "outputs");
      if (!src || !isRecord(outputs)) continue;
      for (const out of Object.values(outputs)) {
        if (!isRecord(out)) continue;
        const conns = getKey(out, "connections");
        if (!Array.isArray(conns)) continue;
        for (const c of conns) {
          if (!isRecord(c)) continue;
          const tgt = String(c.node || "");
          if (!tgt) continue;
          edges.push({ source: src, target: tgt });
        }
      }
    }
    return edges;
  }
  return [];
}

function cryptoId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return String(Math.random()).slice(2);
  }
}

function mapAutomaNodeToStep(node: AutomaNode | undefined): WorkflowStep | null {
  if (!node) return null;
  const id = String(node.id || cryptoId());
  const data = isRecord(node.data) ? node.data : {};
  const rawType = getAutomaBlockName(node);

  if (rawType.includes("trigger-event") || rawType.includes("keyboard-event")) {
    const nested = getKey(data, "data");
    const selector = String(getKey(data, "selector") || getKey(nested, "selector") || "").trim();
    const eventParams = getKey(data, "eventParams") || getKey(nested, "eventParams");
    const code = String(getKey(eventParams, "code") || "").trim();
    const keyRaw = String(getKey(eventParams, "key") || "").trim();
    const key = keyRaw || keyFromKeyCode(code);
    const params: Record<string, unknown> = {};
    if (selector) params.selector = selector;
    if (key) params.key = key;
    return { id, type: "press", params, enabled: true };
  }

  if (isAutomaTriggerBlock(rawType)) {
    return { id, type: "trigger", params: {}, enabled: true };
  }

  if (rawType.includes("new-tab") || rawType.includes("go-to") || rawType.includes("url") || rawType.includes("navigate")) {
    const nested = getKey(data, "data");
    const url = String(getKey(data, "url") || getKey(nested, "url") || getKey(data, "value") || "").trim();
    return { id, type: "navigate", params: url ? { url } : {}, enabled: true };
  }

  if (rawType.includes("click")) {
    const nested = getKey(data, "data");
    const selector = String(getKey(data, "selector") || getKey(nested, "selector") || getKey(data, "element") || "").trim();
    return { id, type: "click", params: selector ? { selector } : {}, enabled: true };
  }

  if (rawType.includes("forms") || rawType.includes("type") || rawType.includes("input") || rawType.includes("fill")) {
    const nested = getKey(data, "data");
    const selector = String(getKey(data, "selector") || getKey(nested, "selector") || getKey(data, "element") || "").trim();
    const text = String(getKey(data, "text") || getKey(nested, "text") || getKey(data, "value") || "").trim();
    const params: Record<string, unknown> = {};
    if (selector) params.selector = selector;
    if (text) params.text = text;
    return { id, type: "fill", params, enabled: true };
  }

  if (rawType.includes("delay") || rawType.includes("wait")) {
    const nested = getKey(data, "data");
    const msRaw =
      getKey(data, "ms") ??
      getKey(data, "time") ??
      getKey(data, "delay") ??
      getKey(data, "timeout") ??
      getKey(nested, "ms") ??
      getKey(nested, "time") ??
      getKey(nested, "delay") ??
      getKey(nested, "timeout");
    const ms = typeof msRaw === "number" ? msRaw : Number(String(msRaw || "").trim() || "0");
    if (ms > 0) return { id, type: "wait", params: { sec: ms / 1000 }, enabled: true };
    return { id, type: "wait", params: {}, enabled: true };
  }

  return { id, type: rawType || "unknown", params: data || {}, enabled: true };
}

function normalizeAutomaPayload(obj: unknown): unknown {
  if (!isRecord(obj)) return obj;
  const d = obj.drawflow;
  if (typeof d === "string") {
    try {
      const parsed = JSON.parse(d);
      if (isRecord(parsed)) return { ...obj, drawflow: parsed };
      return obj;
    } catch {
      return obj;
    }
  }
  return obj;
}

function getAutomaBlockName(node: AutomaNode): string {
  const data = isRecord(node.data) ? node.data : {};
  const candidates = [
    node.name,
    getKey(data, "name"),
    getKey(data, "class"),
    getKey(data, "block"),
    getKey(data, "task"),
    getKey(data, "type"),
    node.type,
  ];
  const raw = candidates.map((v) => String(v || "").trim()).find(Boolean) || "";
  const t = raw.toLowerCase();
  if (t === "blockbasic" || t === "blockbasicwithfallback") {
    const alt = String(getKey(data, "class") || getKey(data, "name") || "").toLowerCase();
    return alt || "";
  }
  return t;
}

function isAutomaTriggerBlock(name: string): boolean {
  const n = String(name || "").trim().toLowerCase();
  return n === "trigger" || n === "webhook-trigger" || n === "schedule" || n === "schedule-trigger";
}

function keyFromKeyCode(code: string): string {
  const c = String(code || "").trim();
  if (c === "13") return "Enter";
  if (c === "9") return "Tab";
  if (c === "27") return "Escape";
  if (c === "32") return "Space";
  return "";
}

function pickNextNodeId(outIds: string[], visited: Set<string>): string {
  for (const t of outIds) {
    if (!visited.has(t)) return t;
  }
  return outIds[0] || "";
}

function uniq<T>(arr: T[]): T[] {
  const seen = new Set<T>();
  const out: T[] = [];
  for (const v of arr) {
    if (seen.has(v)) continue;
    seen.add(v);
    out.push(v);
  }
  return out;
}

function extractLocatorsFromSteps(steps: WorkflowStep[], existing: Locator[]): Locator[] {
  const existingBySelector = new Set(existing.map((l) => l.selector));
  const existingByName = new Set(existing.map((l) => l.name));
  const out: Locator[] = [];
  for (const s of steps) {
    const sel = String(s.params?.["selector"] || "").trim();
    if (!sel) continue;
    if (existingBySelector.has(sel)) continue;
    const base = suggestLocatorName(sel) || "locator";
    let name = base;
    let i = 2;
    while (existingByName.has(name) || out.some((l) => l.name === name)) {
      name = `${base}_${i}`;
      i += 1;
    }
    existingBySelector.add(sel);
    existingByName.add(name);
    out.push({ name, selector: sel });
  }
  return out;
}

function suggestLocatorName(selector: string): string {
  const s = String(selector || "").trim();
  if (!s) return "";
  const idMatch = s.match(/#([A-Za-z][A-Za-z0-9_-]*)/);
  if (idMatch) return idMatch[1];
  const testId = s.match(/\[data-testid\s*=\s*["']?([A-Za-z0-9_-]+)["']?\]/i);
  if (testId) return testId[1];
  const dataQa = s.match(/\[data-qa\s*=\s*["']?([A-Za-z0-9_-]+)["']?\]/i);
  if (dataQa) return dataQa[1];
  const classMatch = s.match(/\.([A-Za-z][A-Za-z0-9_-]*)/);
  if (classMatch) return classMatch[1];
  const words = s.replace(/[^A-Za-z0-9_-]+/g, " ").trim().split(/\s+/).filter(Boolean);
  const last = words[words.length - 1] || "";
  return last || "locator";
}
