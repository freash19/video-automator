import { useEffect, useState } from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Globe,
  Clock,
  Cpu,
  Key,
  FolderOpen,
  HelpCircle,
  Save,
  RotateCcw,
} from "lucide-react";
import { WizardNavigation } from "@/components/common/WizardNavigation";
import { toast } from "sonner";
import { API_BASE_URL } from "@/lib/utils";

interface SettingFieldProps {
  label: string;
  tooltip: string;
  children: React.ReactNode;
}

type AppConfig = Record<string, unknown> & {
  headless?: boolean;
  max_concurrency?: number;
  download_dir?: string;
  pre_fill_wait?: number;
  delay_between_scenes?: number;
  reload_timeout_ms?: number;
  playwright_timeout_ms?: number;
  search_results_timeout_ms?: number;
  validation_ready_timeout_ms?: number;
  save_notification_timeout_ms?: number;
  generation_redirect_timeout_ms?: number;
  post_reload_wait?: number;
  enable_enhance_voice?: boolean;
  media_source?: string;
  orientation_choice?: string;
  close_media_panel_after_broll?: boolean;
  enable_notifications?: boolean;
  pre_generation_pause_sec?: number;
  confirm_timeout_sec?: number;
  abort_on_validation_failure?: boolean;
  interactive_on_mismatch?: boolean;
  save_fallback_wait_sec?: number;
  max_scenes?: number;
  parallel_mode?: string;
  browser?: string;
  chrome_cdp_url?: string;
  multilogin_cdp_url?: string;
  profile_to_use?: string;
  profiles?: Record<string, unknown>;
  telegram_bot_token?: string;
  telegram_chat_id?: string;
};

function SettingField({ label, tooltip, children }: SettingFieldProps) {
  return (
    <div className="flex items-start justify-between py-4 border-b border-border last:border-0">
      <div className="flex items-center gap-2">
        <Label className="text-foreground">{label}</Label>
        <Tooltip>
          <TooltipTrigger asChild>
            <HelpCircle className="w-4 h-4 text-muted-foreground cursor-help" />
          </TooltipTrigger>
          <TooltipContent className="max-w-[200px]">
            <p className="text-sm">{tooltip}</p>
          </TooltipContent>
        </Tooltip>
      </div>
      <div className="w-[280px]">{children}</div>
    </div>
  );
}

export default function Settings() {
  const API = API_BASE_URL;
  const [config, setConfig] = useState<AppConfig>({});
  const [headless, setHeadless] = useState<boolean>(false);
  const [parallelWorkers, setParallelWorkers] = useState<number[]>([2]);
  const [downloadDir, setDownloadDir] = useState<string>("./downloads");
  const [preFillWaitSec, setPreFillWaitSec] = useState<number>(1.5);
  const [delayBetweenScenesSec, setDelayBetweenScenesSec] = useState<number>(1.5);
  const [reloadTimeoutSec, setReloadTimeoutSec] = useState<number>(90);
  const [playwrightTimeoutSec, setPlaywrightTimeoutSec] = useState<number>(3);
  const [searchResultsTimeoutSec, setSearchResultsTimeoutSec] = useState<number>(5);
  const [validationReadyTimeoutSec, setValidationReadyTimeoutSec] = useState<number>(6);
  const [saveNotificationTimeoutSec, setSaveNotificationTimeoutSec] = useState<number>(4);
  const [generationRedirectTimeoutSec, setGenerationRedirectTimeoutSec] = useState<number>(180);
  const [postReloadWaitSec, setPostReloadWaitSec] = useState<number>(1.5);
  const [enhanceVoice, setEnhanceVoice] = useState<boolean>(false);
  const [mediaSource, setMediaSource] = useState<string>("all");
  const [orientationChoice, setOrientationChoice] = useState<string>("Горизонтальная");
  const [closeMediaPanelAfterBroll, setCloseMediaPanelAfterBroll] = useState<boolean>(true);
  const [enableNotifications, setEnableNotifications] = useState<boolean>(false);
  const [preGenerationPauseSec, setPreGenerationPauseSec] = useState<number>(20);
  const [confirmTimeoutSec, setConfirmTimeoutSec] = useState<number>(10);
  const [abortOnValidationFailure, setAbortOnValidationFailure] = useState<boolean>(false);
  const [interactiveOnMismatch, setInteractiveOnMismatch] = useState<boolean>(true);
  const [saveFallbackWaitSec, setSaveFallbackWaitSec] = useState<number>(7);
  const [maxScenes, setMaxScenes] = useState<number>(15);
  const [parallelMode, setParallelMode] = useState<string>("tabs");
  const [browserMode, setBrowserMode] = useState<string>("chrome");
  const [chromeCdpUrl, setChromeCdpUrl] = useState<string>("http://localhost:9222");
  const [multiloginCdpUrl, setMultiloginCdpUrl] = useState<string>("");
  const [profileToUse, setProfileToUse] = useState<string>("ask");
  const [telegramBotToken, setTelegramBotToken] = useState<string>("");
  const [telegramChatId, setTelegramChatId] = useState<string>("");
  const [advancedJson, setAdvancedJson] = useState<string>("");

  useEffect(() => {
    const load = async () => {
      try {
        const cfg: AppConfig = await fetch(`${API}/config`).then((r) => r.json());
        setConfig(cfg);
        setHeadless(Boolean(cfg.headless));
        setParallelWorkers([Number(cfg.max_concurrency || 2)]);
        setDownloadDir(String(cfg.download_dir || "./downloads"));
        setPreFillWaitSec(Number(cfg.pre_fill_wait || 1.5));
        setDelayBetweenScenesSec(Number(cfg.delay_between_scenes || 1.5));
        setReloadTimeoutSec(Math.round(Number(cfg.reload_timeout_ms || 90000) / 1000));
        setPlaywrightTimeoutSec(Math.round(Number(cfg.playwright_timeout_ms || 3000) / 1000));
        setSearchResultsTimeoutSec(Math.round(Number(cfg.search_results_timeout_ms || 5000) / 1000));
        setValidationReadyTimeoutSec(Math.round(Number(cfg.validation_ready_timeout_ms || 6000) / 1000));
        setSaveNotificationTimeoutSec(Math.round(Number(cfg.save_notification_timeout_ms || 4000) / 1000));
        setGenerationRedirectTimeoutSec(Math.round(Number(cfg.generation_redirect_timeout_ms || 180000) / 1000));
        setPostReloadWaitSec(Number(cfg.post_reload_wait || 1.5));
        setEnhanceVoice(Boolean(cfg.enable_enhance_voice));
        setMediaSource(String(cfg.media_source || "all"));
        setOrientationChoice(String(cfg.orientation_choice || "Горизонтальная"));
        setCloseMediaPanelAfterBroll(Boolean(cfg.close_media_panel_after_broll ?? true));
        setEnableNotifications(Boolean(cfg.enable_notifications));
        setPreGenerationPauseSec(Number(cfg.pre_generation_pause_sec ?? 20));
        setConfirmTimeoutSec(Number(cfg.confirm_timeout_sec ?? 10));
        setAbortOnValidationFailure(Boolean(cfg.abort_on_validation_failure));
        setInteractiveOnMismatch(Boolean(cfg.interactive_on_mismatch ?? true));
        setSaveFallbackWaitSec(Number(cfg.save_fallback_wait_sec ?? 7));
        setMaxScenes(Number(cfg.max_scenes ?? 15));
        setParallelMode(String(cfg.parallel_mode || "tabs"));
        setBrowserMode(String(cfg.browser || "chrome"));
        setChromeCdpUrl(String(cfg.chrome_cdp_url || "http://localhost:9222"));
        setMultiloginCdpUrl(String(cfg.multilogin_cdp_url || ""));
        setProfileToUse(String(cfg.profile_to_use || "ask"));
        setTelegramBotToken(String(cfg.telegram_bot_token || ""));
        setTelegramChatId(String(cfg.telegram_chat_id || ""));
        setAdvancedJson(JSON.stringify(cfg, null, 2));
      } catch (e) {
        void e;
      }
    };
    load();
  }, []);

  const handleSave = async () => {
    const payload = {
      headless,
      max_concurrency: parallelWorkers[0],
      download_dir: downloadDir,
      pre_fill_wait: preFillWaitSec,
      delay_between_scenes: delayBetweenScenesSec,
      reload_timeout_ms: Math.round(reloadTimeoutSec * 1000),
      playwright_timeout_ms: Math.round(playwrightTimeoutSec * 1000),
      search_results_timeout_ms: Math.round(searchResultsTimeoutSec * 1000),
      validation_ready_timeout_ms: Math.round(validationReadyTimeoutSec * 1000),
      save_notification_timeout_ms: Math.round(saveNotificationTimeoutSec * 1000),
      generation_redirect_timeout_ms: Math.round(generationRedirectTimeoutSec * 1000),
      post_reload_wait: postReloadWaitSec,
      enable_enhance_voice: enhanceVoice,
      media_source: mediaSource,
      orientation_choice: orientationChoice,
      close_media_panel_after_broll: closeMediaPanelAfterBroll,
      enable_notifications: enableNotifications,
      pre_generation_pause_sec: preGenerationPauseSec,
      confirm_timeout_sec: confirmTimeoutSec,
      abort_on_validation_failure: abortOnValidationFailure,
      interactive_on_mismatch: interactiveOnMismatch,
      save_fallback_wait_sec: saveFallbackWaitSec,
      max_scenes: maxScenes,
      parallel_mode: parallelMode,
      browser: browserMode,
      chrome_cdp_url: chromeCdpUrl,
      multilogin_cdp_url: multiloginCdpUrl,
      profile_to_use: profileToUse,
      telegram_bot_token: telegramBotToken,
      telegram_chat_id: telegramChatId,
    };
    await fetch(`${API}/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    toast.success("Конфигурация сохранена");
  };

  const handleReset = () => {
    toast.info("Settings reset to defaults");
  };

  const handleSaveAdvanced = async () => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(advancedJson);
    } catch {
      toast.error("JSON невалидный");
      return;
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      toast.error("JSON должен быть объектом");
      return;
    }
    await fetch(`${API}/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parsed),
    });
    toast.success("Конфиг JSON сохранён");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Конфигурация</h1>
          <p className="text-muted-foreground">
            Настройте поведение и параметры автоматизации.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handleReset}>
            <RotateCcw className="w-4 h-4 mr-2" />
            Сбросить
          </Button>
          <Button onClick={handleSave}>
            <Save className="w-4 h-4 mr-2" />
            Сохранить конфиг
          </Button>
        </div>
      </div>

      {/* Settings Accordion */}
      <div className="rounded-xl border border-border shadow-card">
        <Accordion type="multiple" defaultValue={["browser", "timeouts", "parallel", "media"]} className="w-full">
          {/* Browser Settings */}
          <AccordionItem value="browser" className="border-b border-border">
            <AccordionTrigger className="px-6 hover:no-underline hover:bg-muted/30">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-primary/10 text-primary">
                  <Globe className="w-4 h-4" />
                </div>
                <div className="text-left">
                  <div className="font-semibold">Настройки браузера</div>
                  <div className="text-sm text-muted-foreground font-normal">
                    Управление режимами и внешним видом
                  </div>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-6 pb-4">
              <SettingField
                label="Режим Headless"
                tooltip="Без UI. Быстрее, но сложнее отладка."
              >
                <Switch checked={headless} onCheckedChange={(v) => setHeadless(Boolean(v))} />
              </SettingField>

              <SettingField
                label="Режим браузера"
                tooltip="Источник браузера: Chrome CDP или Multilogin."
              >
                <Select value={browserMode} onValueChange={setBrowserMode}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="chrome">chrome</SelectItem>
                    <SelectItem value="multilogin">multilogin</SelectItem>
                  </SelectContent>
                </Select>
              </SettingField>

              <SettingField
                label="Chrome CDP URL"
                tooltip="Адрес CDP для подключения к Chrome."
              >
                <Input value={chromeCdpUrl} onChange={(e) => setChromeCdpUrl(e.target.value)} />
              </SettingField>

              <SettingField
                label="Multilogin CDP URL"
                tooltip="Адрес CDP для Multilogin (если используешь multilogin)."
              >
                <Input value={multiloginCdpUrl} onChange={(e) => setMultiloginCdpUrl(e.target.value)} />
              </SettingField>

              <SettingField
                label="Profile To Use"
                tooltip="Какой профиль использовать: ask или имя профиля из profiles."
              >
                <Select value={profileToUse} onValueChange={setProfileToUse}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ask">ask</SelectItem>
                    {Object.keys((config.profiles || {}) as Record<string, unknown>).map((k) => (
                      <SelectItem key={k} value={k}>
                        {k}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </SettingField>
            </AccordionContent>
          </AccordionItem>

          {/* Timeouts & Delays */}
          <AccordionItem value="timeouts" className="border-b border-border">
            <AccordionTrigger className="px-6 hover:no-underline hover:bg-muted/30">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-warning/10 text-warning">
                  <Clock className="w-4 h-4" />
                </div>
                <div className="text-left">
                  <div className="font-semibold">Таймауты и задержки</div>
                  <div className="text-sm text-muted-foreground font-normal">
                    Управление ожиданиями и таймаутами
                  </div>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-6 pb-4">
              <SettingField
                label="Reload Timeout (sec)"
                tooltip="Максимальное ожидание перезагрузки страницы."
              >
                <Input type="number" value={reloadTimeoutSec} onChange={(e) => setReloadTimeoutSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Playwright Timeout (sec)"
                tooltip="Таймаут по умолчанию для операций Playwright."
              >
                <Input type="number" value={playwrightTimeoutSec} onChange={(e) => setPlaywrightTimeoutSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Delay Between Scenes (sec)"
                tooltip="Задержка между заполнением сцен."
              >
                <Input type="number" value={delayBetweenScenesSec} onChange={(e) => setDelayBetweenScenesSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Pre-fill Wait (sec)"
                tooltip="Дополнительное ожидание перед началом заполнения после перезагрузки."
              >
                <Input type="number" value={preFillWaitSec} onChange={(e) => setPreFillWaitSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Post Reload Wait (sec)"
                tooltip="Запасное ожидание после перезагрузки, если селекторы не готовы."
              >
                <Input type="number" value={postReloadWaitSec} onChange={(e) => setPostReloadWaitSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Search Results Timeout (sec)"
                tooltip="Ожидание появления результатов поиска медиа."
              >
                <Input type="number" value={searchResultsTimeoutSec} onChange={(e) => setSearchResultsTimeoutSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Validation Ready Timeout (sec)"
                tooltip="Ожидание готовности DOM перед валидацией."
              >
                <Input type="number" value={validationReadyTimeoutSec} onChange={(e) => setValidationReadyTimeoutSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Save Notification Timeout (sec)"
                tooltip="Ожидание появления уведомления «Сохранено»."
              >
                <Input type="number" value={saveNotificationTimeoutSec} onChange={(e) => setSaveNotificationTimeoutSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Generation Redirect Timeout (sec)"
                tooltip="Ожидание редиректа на /projects после отправки."
              >
                <Input type="number" value={generationRedirectTimeoutSec} onChange={(e) => setGenerationRedirectTimeoutSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Save Fallback Wait (sec)"
                tooltip="Пауза, если уведомление «Сохранено» не появилось."
              >
                <Input type="number" value={saveFallbackWaitSec} onChange={(e) => setSaveFallbackWaitSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Pre-generation Pause (sec)"
                tooltip="Пауза перед отправкой на генерацию (заменяет confirm_timeout_sec)."
              >
                <Input type="number" value={preGenerationPauseSec} onChange={(e) => setPreGenerationPauseSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Confirm Timeout (sec)"
                tooltip="Таймаут подтверждения, если pre_generation_pause_sec не используется."
              >
                <Input type="number" value={confirmTimeoutSec} onChange={(e) => setConfirmTimeoutSec(Number(e.target.value))} />
              </SettingField>
            </AccordionContent>
          </AccordionItem>

          {/* Parallel Execution */}
          <AccordionItem value="parallel" className="border-b border-border">
            <AccordionTrigger className="px-6 hover:no-underline hover:bg-muted/30">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-success/10 text-success">
                  <Cpu className="w-4 h-4" />
                </div>
                <div className="text-left">
                  <div className="font-semibold">Parallel Execution</div>
                  <div className="text-sm text-muted-foreground font-normal">
                    Configure multi-threaded processing
                  </div>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-6 pb-4">
              <SettingField
                label="Worker Count"
                tooltip="Number of parallel browser instances to run."
              >
                <div className="space-y-3">
                  <Slider
                    value={parallelWorkers}
                    onValueChange={setParallelWorkers}
                    min={1}
                    max={8}
                    step={1}
                  />
                  <div className="text-center text-sm font-mono text-muted-foreground">
                    {parallelWorkers[0]} worker{parallelWorkers[0] > 1 ? "s" : ""}
                  </div>
                </div>
              </SettingField>

              <SettingField
                label="Parallel Mode"
                tooltip="Как запускать параллельно: tabs или profiles."
              >
                <Select value={parallelMode} onValueChange={setParallelMode}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="tabs">tabs</SelectItem>
                    <SelectItem value="profiles">profiles</SelectItem>
                  </SelectContent>
                </Select>
              </SettingField>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="media" className="border-b border-border">
            <AccordionTrigger className="px-6 hover:no-underline hover:bg-muted/30">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-muted text-muted-foreground">
                  <Globe className="w-4 h-4" />
                </div>
                <div className="text-left">
                  <div className="font-semibold">Медиа и голос</div>
                  <div className="text-sm text-muted-foreground font-normal">
                    B-roll и Enhance Voice
                  </div>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-6 pb-4">
              <SettingField
                label="Enhance Voice"
                tooltip="Нажимать Enhance Voice после заполнения сцены."
              >
                <Switch checked={enhanceVoice} onCheckedChange={(v) => setEnhanceVoice(Boolean(v))} />
              </SettingField>

              <SettingField
                label="Media Source"
                tooltip="Источник поиска b-roll."
              >
                <Select value={mediaSource} onValueChange={setMediaSource}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">all</SelectItem>
                    <SelectItem value="getty">getty</SelectItem>
                    <SelectItem value="storyblocks">storyblocks</SelectItem>
                    <SelectItem value="pexels">pexels</SelectItem>
                  </SelectContent>
                </Select>
              </SettingField>

              <SettingField
                label="Orientation"
                tooltip="Ориентация медиа в поиске."
              >
                <Select value={orientationChoice} onValueChange={setOrientationChoice}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Горизонтальная">Горизонтальная</SelectItem>
                    <SelectItem value="Вертикальная">Вертикальная</SelectItem>
                  </SelectContent>
                </Select>
              </SettingField>

              <SettingField
                label="Close Media Panel"
                tooltip="Закрывать панель Медиа после добавления b-roll."
              >
                <Switch checked={closeMediaPanelAfterBroll} onCheckedChange={(v) => setCloseMediaPanelAfterBroll(Boolean(v))} />
              </SettingField>
            </AccordionContent>
          </AccordionItem>

          {/* API Keys */}
          <AccordionItem value="api" className="border-b border-border">
            <AccordionTrigger className="px-6 hover:no-underline hover:bg-muted/30">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-purple-400/10 text-purple-400">
                  <Key className="w-4 h-4" />
                </div>
                <div className="text-left">
                  <div className="font-semibold">API Keys</div>
                  <div className="text-sm text-muted-foreground font-normal">
                    External service credentials
                  </div>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-6 pb-4">
              <SettingField
                label="Telegram Bot Token"
                tooltip="Токен бота для уведомлений."
              >
                <Input type="password" value={telegramBotToken} onChange={(e) => setTelegramBotToken(e.target.value)} />
              </SettingField>

              <SettingField
                label="Telegram Chat ID"
                tooltip="Чат ID для уведомлений."
              >
                <Input value={telegramChatId} onChange={(e) => setTelegramChatId(e.target.value)} />
              </SettingField>

              <SettingField
                label="Enable Notifications"
                tooltip="Включить локальные уведомления macOS."
              >
                <Switch checked={enableNotifications} onCheckedChange={(v) => setEnableNotifications(Boolean(v))} />
              </SettingField>
            </AccordionContent>
          </AccordionItem>

          {/* File Paths */}
          <AccordionItem value="paths">
            <AccordionTrigger className="px-6 hover:no-underline hover:bg-muted/30">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-muted text-muted-foreground">
                  <FolderOpen className="w-4 h-4" />
                </div>
                <div className="text-left">
                  <div className="font-semibold">File Paths</div>
                  <div className="text-sm text-muted-foreground font-normal">
                    Configure input/output directories
                  </div>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-6 pb-4">
              <SettingField
                label="Output Directory"
                tooltip="Where to save generated videos."
              >
                <Input value={downloadDir} onChange={(e) => setDownloadDir(e.target.value)} />
              </SettingField>

              <SettingField
                label="Max Scenes"
                tooltip="Максимальное число сцен в шаблоне."
              >
                <Input type="number" value={maxScenes} onChange={(e) => setMaxScenes(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Abort On Validation Failure"
                tooltip="Останавливать процесс, если валидация не прошла."
              >
                <Switch checked={abortOnValidationFailure} onCheckedChange={(v) => setAbortOnValidationFailure(Boolean(v))} />
              </SettingField>

              <SettingField
                label="Interactive On Mismatch"
                tooltip="Просить вмешательство пользователя при несоответствиях."
              >
                <Switch checked={interactiveOnMismatch} onCheckedChange={(v) => setInteractiveOnMismatch(Boolean(v))} />
              </SettingField>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="advanced">
            <AccordionTrigger className="px-6 hover:no-underline hover:bg-muted/30">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-muted text-muted-foreground">
                  <Cpu className="w-4 h-4" />
                </div>
                <div className="text-left">
                  <div className="font-semibold">Расширенные</div>
                  <div className="text-sm text-muted-foreground font-normal">
                    Редактирование полного `config.json`
                  </div>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-6 pb-4">
              <div className="space-y-3">
                <Textarea value={advancedJson} onChange={(e) => setAdvancedJson(e.target.value)} className="min-h-[260px] font-mono text-xs" />
                <div className="flex justify-end">
                  <Button variant="outline" onClick={handleSaveAdvanced}>
                    Сохранить JSON
                  </Button>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </div>

      {/* Wizard Navigation */}
      <WizardNavigation
        backPath="/workflow"
        backLabel="Workflow Builder"
        nextPath="/runner"
        nextLabel="Start Automation"
      />
    </div>
  );
}
