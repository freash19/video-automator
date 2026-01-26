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
  Video,
  Plus,
  Trash2,
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
  enable_generation?: boolean;
  pre_generation_pause_sec?: number;
  confirm_timeout_sec?: number;
  abort_on_validation_failure?: boolean;
  interactive_on_mismatch?: boolean;
  save_fallback_wait_sec?: number;
  max_scenes?: number;
  parallel_mode?: string;
  profiles?: Record<string, unknown>;
  telegram_bot_token?: string;
  telegram_chat_id?: string;
  checks?: Record<string, { enabled?: boolean; attempts?: number; interval_sec?: number }>;
  telegram_broadcast_all?: boolean;
  video_bitrate_kbps?: number;
  video_resolution?: string;
  video_codec?: string;
  audio_codec?: string;
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
  const [enableGeneration, setEnableGeneration] = useState<boolean>(true);
  const [preGenerationPauseSec, setPreGenerationPauseSec] = useState<number>(20);
  const [confirmTimeoutSec, setConfirmTimeoutSec] = useState<number>(10);
  const [abortOnValidationFailure, setAbortOnValidationFailure] = useState<boolean>(false);
  const [interactiveOnMismatch, setInteractiveOnMismatch] = useState<boolean>(true);
  const [saveFallbackWaitSec, setSaveFallbackWaitSec] = useState<number>(7);
  const [maxScenes, setMaxScenes] = useState<number>(15);
  const [parallelMode, setParallelMode] = useState<string>("tabs");
  const [telegramBotToken, setTelegramBotToken] = useState<string>("");
  const [telegramChatId, setTelegramChatId] = useState<string>("");
  const [telegramBroadcastAll, setTelegramBroadcastAll] = useState<boolean>(false);
  const [advancedJson, setAdvancedJson] = useState<string>("");
  const [verifySceneCheckEnabled, setVerifySceneCheckEnabled] = useState<boolean>(true);
  const [verifySceneCheckAttempts, setVerifySceneCheckAttempts] = useState<number>(3);
  const [verifySceneCheckIntervalSec, setVerifySceneCheckIntervalSec] = useState<number>(0.2);
  const [validationCheckEnabled, setValidationCheckEnabled] = useState<boolean>(true);
  const [validationCheckAttempts, setValidationCheckAttempts] = useState<number>(3);
  const [validationCheckIntervalSec, setValidationCheckIntervalSec] = useState<number>(1.5);
  
  // Video settings
  const [videoBitrateKbps, setVideoBitrateKbps] = useState<number>(5000);
  const [videoResolution, setVideoResolution] = useState<string>("1080p");
  const [videoCodec, setVideoCodec] = useState<string>("h264");
  const [audioCodec, setAudioCodec] = useState<string>("aac");
  
  // Browser profiles
  const [profiles, setProfiles] = useState<Record<string, { cdp_url?: string; profile_path?: string; browser_type?: "chrome" | "chromium" }>>({});
  const [editingProfileName, setEditingProfileName] = useState<Record<string, string>>({});

  useEffect(() => {
    const load = async () => {
      try {
        const cfg: AppConfig = await fetch(`${API}/config`).then((r) => r.json());
        setConfig(cfg);
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
        setEnableGeneration(Boolean(cfg.enable_generation ?? true));
        setPreGenerationPauseSec(Number(cfg.pre_generation_pause_sec ?? 20));
        setConfirmTimeoutSec(Number(cfg.confirm_timeout_sec ?? 10));
        setAbortOnValidationFailure(Boolean(cfg.abort_on_validation_failure));
        setInteractiveOnMismatch(Boolean(cfg.interactive_on_mismatch ?? true));
        setSaveFallbackWaitSec(Number(cfg.save_fallback_wait_sec ?? 7));
        setMaxScenes(Number(cfg.max_scenes ?? 15));
        setParallelMode(String(cfg.parallel_mode || "tabs"));
        setTelegramBotToken(String(cfg.telegram_bot_token || ""));
        setTelegramChatId(String(cfg.telegram_chat_id || ""));
        setTelegramBroadcastAll(Boolean(cfg.telegram_broadcast_all));
        const checks = (cfg.checks || {}) as Record<string, { enabled?: boolean; attempts?: number; interval_sec?: number }>;
        const verifyCfg = checks.verify_scene || {};
        const validationCfg = checks.validation || {};
        setVerifySceneCheckEnabled(Boolean(verifyCfg.enabled ?? true));
        setVerifySceneCheckAttempts(Number(verifyCfg.attempts ?? 3));
        setVerifySceneCheckIntervalSec(Number(verifyCfg.interval_sec ?? 0.2));
        setValidationCheckEnabled(Boolean(validationCfg.enabled ?? true));
        setValidationCheckAttempts(Number(validationCfg.attempts ?? 3));
        setValidationCheckIntervalSec(Number(validationCfg.interval_sec ?? 1.5));
        // Video settings
        setVideoBitrateKbps(Number(cfg.video_bitrate_kbps ?? 5000));
        setVideoResolution(String(cfg.video_resolution || "1080p"));
        setVideoCodec(String(cfg.video_codec || "h264"));
        setAudioCodec(String(cfg.audio_codec || "aac"));
        setProfiles((cfg.profiles || {}) as Record<string, { cdp_url?: string; profile_path?: string }>);
        setAdvancedJson(JSON.stringify(cfg, null, 2));
      } catch (e) {
        void e;
      }
    };
    load();
  }, []);

  const handleSave = async () => {
    const payload = {
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
      enable_generation: enableGeneration,
      pre_generation_pause_sec: preGenerationPauseSec,
      confirm_timeout_sec: confirmTimeoutSec,
      abort_on_validation_failure: abortOnValidationFailure,
      interactive_on_mismatch: interactiveOnMismatch,
      save_fallback_wait_sec: saveFallbackWaitSec,
      max_scenes: maxScenes,
      parallel_mode: parallelMode,
      telegram_bot_token: telegramBotToken,
      telegram_chat_id: telegramChatId,
      telegram_broadcast_all: telegramBroadcastAll,
      checks: {
        verify_scene: {
          enabled: verifySceneCheckEnabled,
          attempts: verifySceneCheckAttempts,
          interval_sec: verifySceneCheckIntervalSec,
        },
        validation: {
          enabled: validationCheckEnabled,
          attempts: validationCheckAttempts,
          interval_sec: validationCheckIntervalSec,
        },
      },
      video_bitrate_kbps: videoBitrateKbps,
      video_resolution: videoResolution,
      video_codec: videoCodec,
      audio_codec: audioCodec,
      profiles: profiles,
    };
    await fetch(`${API}/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    toast.success("Конфигурация сохранена");
  };

  const handleReset = () => {
    toast.info("Настройки сброшены по умолчанию");
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
        <Accordion type="multiple" defaultValue={[]} className="w-full">
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
                label="Таймаут перезагрузки (сек)"
                tooltip="Максимальное ожидание перезагрузки страницы."
              >
                <Input type="number" value={reloadTimeoutSec} onChange={(e) => setReloadTimeoutSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Таймаут Playwright (сек)"
                tooltip="Таймаут по умолчанию для операций Playwright."
              >
                <Input type="number" value={playwrightTimeoutSec} onChange={(e) => setPlaywrightTimeoutSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Пауза между сценами (сек)"
                tooltip="Задержка между заполнением сцен."
              >
                <Input type="number" value={delayBetweenScenesSec} onChange={(e) => setDelayBetweenScenesSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Ожидание перед заполнением (сек)"
                tooltip="Дополнительное ожидание перед началом заполнения после перезагрузки."
              >
                <Input type="number" value={preFillWaitSec} onChange={(e) => setPreFillWaitSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Ожидание после перезагрузки (сек)"
                tooltip="Запасное ожидание после перезагрузки, если селекторы не готовы."
              >
                <Input type="number" value={postReloadWaitSec} onChange={(e) => setPostReloadWaitSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Ожидание результатов поиска (сек)"
                tooltip="Ожидание появления результатов поиска медиа."
              >
                <Input type="number" value={searchResultsTimeoutSec} onChange={(e) => setSearchResultsTimeoutSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Ожидание перед валидацией (сек)"
                tooltip="Ожидание готовности DOM перед валидацией."
              >
                <Input type="number" value={validationReadyTimeoutSec} onChange={(e) => setValidationReadyTimeoutSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Ожидание уведомления «Сохранено» (сек)"
                tooltip="Ожидание появления уведомления «Сохранено»."
              >
                <Input type="number" value={saveNotificationTimeoutSec} onChange={(e) => setSaveNotificationTimeoutSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Таймаут редиректа (сек)"
                tooltip="Ожидание редиректа на /projects после отправки."
              >
                <Input type="number" value={generationRedirectTimeoutSec} onChange={(e) => setGenerationRedirectTimeoutSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Пауза при отсутствии уведомления (сек)"
                tooltip="Пауза, если уведомление «Сохранено» не появилось."
              >
                <Input type="number" value={saveFallbackWaitSec} onChange={(e) => setSaveFallbackWaitSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Включить генерацию"
                tooltip="Отправка проекта на генерацию после заполнения сцен."
              >
                <Switch checked={enableGeneration} onCheckedChange={(v) => setEnableGeneration(Boolean(v))} />
              </SettingField>

              <SettingField
                label="Пауза перед генерацией (сек)"
                tooltip="Пауза перед отправкой на генерацию (заменяет confirm_timeout_sec)."
              >
                <Input type="number" value={preGenerationPauseSec} onChange={(e) => setPreGenerationPauseSec(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Таймаут подтверждения (сек)"
                tooltip="Таймаут подтверждения, если pre_generation_pause_sec не используется."
              >
                <Input type="number" value={confirmTimeoutSec} onChange={(e) => setConfirmTimeoutSec(Number(e.target.value))} />
              </SettingField>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="checks" className="border-b border-border">
            <AccordionTrigger className="px-6 hover:no-underline hover:bg-muted/30">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-muted/30 text-muted-foreground">
                  <RotateCcw className="w-4 h-4" />
                </div>
                <div className="text-left">
                  <div className="font-semibold">Проверки</div>
                  <div className="text-sm text-muted-foreground font-normal">
                    Включение и повторы валидаций
                  </div>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-6 pb-4">
              <SettingField
                label="Проверка текста сцены"
                tooltip="Проверка текста после вставки сцены."
              >
                <div className="flex items-center gap-2">
                  <Switch checked={verifySceneCheckEnabled} onCheckedChange={(v) => setVerifySceneCheckEnabled(Boolean(v))} />
                  <Input
                    type="number"
                    value={verifySceneCheckAttempts}
                    onChange={(e) => setVerifySceneCheckAttempts(Number(e.target.value))}
                    className="w-[90px]"
                    min={1}
                  />
                  <Input
                    type="number"
                    value={verifySceneCheckIntervalSec}
                    onChange={(e) => setVerifySceneCheckIntervalSec(Number(e.target.value))}
                    className="w-[90px]"
                    min={0}
                    step={0.1}
                  />
                </div>
              </SettingField>

              <SettingField
                label="Итоговая проверка"
                tooltip="Повторная проверка заполненности сцен."
              >
                <div className="flex items-center gap-2">
                  <Switch checked={validationCheckEnabled} onCheckedChange={(v) => setValidationCheckEnabled(Boolean(v))} />
                  <Input
                    type="number"
                    value={validationCheckAttempts}
                    onChange={(e) => setValidationCheckAttempts(Number(e.target.value))}
                    className="w-[90px]"
                    min={1}
                  />
                  <Input
                    type="number"
                    value={validationCheckIntervalSec}
                    onChange={(e) => setValidationCheckIntervalSec(Number(e.target.value))}
                    className="w-[90px]"
                    min={0}
                    step={0.1}
                  />
                </div>
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
                  <div className="font-semibold">Параллельное выполнение</div>
                  <div className="text-sm text-muted-foreground font-normal">
                    Настройка параллельной обработки
                  </div>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-6 pb-4">
              <SettingField
                label="Количество воркеров"
                tooltip="Количество параллельных экземпляров браузера."
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
                    {parallelWorkers[0]} воркеров
                  </div>
                </div>
              </SettingField>

              <SettingField
                label="Режим параллели"
                tooltip="Как запускать параллельно: tabs или profiles."
              >
                <Select value={parallelMode} onValueChange={setParallelMode}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="tabs">Вкладки</SelectItem>
                    <SelectItem value="profiles">Профили</SelectItem>
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
                    B-roll и усиление голоса
                  </div>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-6 pb-4">
              <SettingField
                label="Усиление голоса"
                tooltip="Нажимать «Усилить голос» после заполнения сцены."
              >
                <Switch checked={enhanceVoice} onCheckedChange={(v) => setEnhanceVoice(Boolean(v))} />
              </SettingField>

              <SettingField
                label="Источник медиа"
                tooltip="Источник поиска B-roll."
              >
                <Select value={mediaSource} onValueChange={setMediaSource}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Все</SelectItem>
                    <SelectItem value="getty">Getty</SelectItem>
                    <SelectItem value="storyblocks">Storyblocks</SelectItem>
                    <SelectItem value="pexels">Pexels</SelectItem>
                  </SelectContent>
                </Select>
              </SettingField>

              <SettingField
                label="Ориентация"
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
                label="Закрывать панель Медиа"
                tooltip="Закрывать панель Медиа после добавления B-roll."
              >
                <Switch checked={closeMediaPanelAfterBroll} onCheckedChange={(v) => setCloseMediaPanelAfterBroll(Boolean(v))} />
              </SettingField>
            </AccordionContent>
          </AccordionItem>

          {/* Video Settings */}
          <AccordionItem value="video" className="border-b border-border">
            <AccordionTrigger className="px-6 hover:no-underline hover:bg-muted/30">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-blue-400/10 text-blue-400">
                  <Video className="w-4 h-4" />
                </div>
                <div className="text-left">
                  <div className="font-semibold">Параметры видео</div>
                  <div className="text-sm text-muted-foreground font-normal">
                    Качество и кодеки для выходного видео
                  </div>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-6 pb-4">
              <SettingField
                label="Битрейт (kbps)"
                tooltip="Выше битрейт = лучше качество, но больше размер файла."
              >
                <Select value={String(videoBitrateKbps)} onValueChange={(v) => setVideoBitrateKbps(Number(v))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="2000">2000 kbps (Низкое качество)</SelectItem>
                    <SelectItem value="5000">5000 kbps (Среднее качество)</SelectItem>
                    <SelectItem value="8000">8000 kbps (Высокое качество)</SelectItem>
                    <SelectItem value="15000">15000 kbps (Максимальное качество)</SelectItem>
                  </SelectContent>
                </Select>
              </SettingField>

              <SettingField
                label="Разрешение"
                tooltip="Выбор разрешения выходного видео. 'Оригинальное' сохранит исходное разрешение."
              >
                <Select value={videoResolution} onValueChange={setVideoResolution}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="720p">720p (HD)</SelectItem>
                    <SelectItem value="1080p">1080p (Full HD)</SelectItem>
                    <SelectItem value="4k">4K</SelectItem>
                    <SelectItem value="original">Оригинальное</SelectItem>
                  </SelectContent>
                </Select>
              </SettingField>

              <SettingField
                label="Видео кодек"
                tooltip="H.264 имеет лучшую совместимость, H.265 обеспечивает лучшее сжатие."
              >
                <Select value={videoCodec} onValueChange={setVideoCodec}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="h264">H.264 (совместимость)</SelectItem>
                    <SelectItem value="h265">H.265 (сжатие)</SelectItem>
                  </SelectContent>
                </Select>
              </SettingField>

              <SettingField
                label="Аудио кодек"
                tooltip="AAC обеспечивает лучшее качество на том же битрейте."
              >
                <Select value={audioCodec} onValueChange={setAudioCodec}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="aac">AAC (рекомендуется)</SelectItem>
                    <SelectItem value="mp3">MP3</SelectItem>
                  </SelectContent>
                </Select>
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
                  <div className="font-semibold">Ключи API</div>
                  <div className="text-sm text-muted-foreground font-normal">
                    Учетные данные внешних сервисов
                  </div>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-6 pb-4">
              <SettingField
                label="Токен Telegram-бота"
                tooltip="Токен бота для уведомлений."
              >
                <Input type="password" value={telegramBotToken} onChange={(e) => setTelegramBotToken(e.target.value)} />
              </SettingField>

              <SettingField
                label="Chat ID Telegram"
                tooltip="Если включена рассылка — можно оставить пустым."
              >
                <Input value={telegramChatId} onChange={(e) => setTelegramChatId(e.target.value)} />
              </SettingField>

              <SettingField
                label="Рассылка во все чаты бота"
                tooltip="Отправлять уведомления во все чаты, где был активен бот."
              >
                <Switch checked={telegramBroadcastAll} onCheckedChange={(v) => setTelegramBroadcastAll(Boolean(v))} />
              </SettingField>

              <SettingField
                label="Включить уведомления"
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
                  <div className="font-semibold">Пути к файлам</div>
                  <div className="text-sm text-muted-foreground font-normal">
                    Настройка директорий ввода/вывода
                  </div>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-6 pb-4">
              <SettingField
                label="Папка вывода"
                tooltip="Куда сохранять файлы и результаты."
              >
                <Input value={downloadDir} onChange={(e) => setDownloadDir(e.target.value)} />
              </SettingField>

              <SettingField
                label="Максимум сцен"
                tooltip="Максимальное число сцен в шаблоне."
              >
                <Input type="number" value={maxScenes} onChange={(e) => setMaxScenes(Number(e.target.value))} />
              </SettingField>

              <SettingField
                label="Останов при ошибке валидации"
                tooltip="Останавливать процесс, если валидация не прошла."
              >
                <Switch checked={abortOnValidationFailure} onCheckedChange={(v) => setAbortOnValidationFailure(Boolean(v))} />
              </SettingField>

              <SettingField
                label="Ручное подтверждение при несоответствиях"
                tooltip="Просить вмешательство пользователя при несоответствиях."
              >
                <Switch checked={interactiveOnMismatch} onCheckedChange={(v) => setInteractiveOnMismatch(Boolean(v))} />
              </SettingField>
            </AccordionContent>
          </AccordionItem>

          {/* Browser Profiles */}
          <AccordionItem value="profiles" className="border-b border-border">
            <AccordionTrigger className="px-6 hover:no-underline hover:bg-muted/30">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-primary/10 text-primary">
                  <Globe className="w-4 h-4" />
                </div>
                <div className="text-left">
                  <div className="font-semibold">Профили браузера</div>
                  <div className="text-sm text-muted-foreground font-normal">
                    Управление профилями Chrome и Chromium
                  </div>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-6 pb-4">
              <div className="space-y-4">
                {Object.entries(profiles).map(([name, profile]) => {
                  const browserType = profile.browser_type || (profile.cdp_url ? "chrome" : "chromium");
                  const displayName = editingProfileName[name] !== undefined ? editingProfileName[name] : name;
                  
                  return (
                    <div key={name} className="rounded-lg border border-border p-4 space-y-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex-1">
                          <Label className="text-xs text-muted-foreground mb-1 block">Название профиля</Label>
                          <Input
                            value={displayName}
                            onChange={(e) => {
                              setEditingProfileName({ ...editingProfileName, [name]: e.target.value });
                            }}
                            onBlur={() => {
                              if (editingProfileName[name] && editingProfileName[name] !== name) {
                                const newProfiles: typeof profiles = {};
                                Object.entries(profiles).forEach(([k, v]) => {
                                  if (k === name) {
                                    newProfiles[editingProfileName[name]] = v;
                                  } else {
                                    newProfiles[k] = v;
                                  }
                                });
                                setProfiles(newProfiles);
                                const newEditing = { ...editingProfileName };
                                delete newEditing[name];
                                setEditingProfileName(newEditing);
                              }
                            }}
                            placeholder="Имя профиля"
                            className="font-semibold"
                          />
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive hover:text-destructive mt-6"
                          onClick={() => {
                            const newProfiles = { ...profiles };
                            delete newProfiles[name];
                            setProfiles(newProfiles);
                            const newEditing = { ...editingProfileName };
                            delete newEditing[name];
                            setEditingProfileName(newEditing);
                          }}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                      <div className="space-y-2">
                        <div>
                          <Label className="text-xs text-muted-foreground">Тип браузера</Label>
                          <Select
                            value={browserType}
                            onValueChange={(v) => {
                              const newProfile = { ...profile, browser_type: v as "chrome" | "chromium" };
                              if (v === "chromium") {
                                delete newProfile.cdp_url;
                              } else if (!newProfile.cdp_url) {
                                newProfile.cdp_url = "http://localhost:9222";
                              }
                              setProfiles({
                                ...profiles,
                                [name]: newProfile,
                              });
                            }}
                          >
                            <SelectTrigger className="mt-1">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="chrome">Chrome (CDP)</SelectItem>
                              <SelectItem value="chromium">Chromium (встроенный)</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        {browserType === "chrome" && (
                          <div>
                            <Label className="text-xs text-muted-foreground">CDP URL</Label>
                            <Input
                              value={profile.cdp_url || ""}
                              onChange={(e) => {
                                setProfiles({
                                  ...profiles,
                                  [name]: { ...profile, cdp_url: e.target.value },
                                });
                              }}
                              placeholder="http://localhost:9222"
                              className="mt-1"
                            />
                          </div>
                        )}
                        <div>
                          <Label className="text-xs text-muted-foreground">Путь к профилю (опционально)</Label>
                          <Input
                            value={profile.profile_path || ""}
                            onChange={(e) => {
                              setProfiles({
                                ...profiles,
                                [name]: { ...profile, profile_path: e.target.value },
                              });
                            }}
                            placeholder="~/chrome_automation"
                            className="mt-1"
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => {
                    const newName = `profile_${Object.keys(profiles).length + 1}`;
                    setProfiles({
                      ...profiles,
                      [newName]: { browser_type: "chrome", cdp_url: "", profile_path: "" },
                    });
                  }}
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Добавить профиль
                </Button>
              </div>
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
        backLabel="Конструктор воркфлоу"
        nextPath="/runner"
        nextLabel="Запуск автоматизации"
      />
    </div>
  );
}
