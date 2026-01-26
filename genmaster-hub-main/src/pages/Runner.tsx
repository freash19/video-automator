import { ConsoleLog } from "@/components/runner/ConsoleLog";
import { WorkerStatus } from "@/components/runner/WorkerStatus";
import { RunnerControls } from "@/components/runner/RunnerControls";

export default function Runner() {
  return (
    <div className="space-y-6 h-full">
      {/* Header */}
      <div className="space-y-1">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          Запуск автоматизации
        </h1>
        <p className="text-muted-foreground">
          Запускайте и контролируйте выполнение воркфлоу в реальном времени.
        </p>
      </div>

      {/* Controls */}
      <RunnerControls />

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 min-h-[500px]">
        <div className="lg:col-span-2 h-[500px]">
          <ConsoleLog />
        </div>
        <div className="lg:col-span-1">
          <WorkerStatus />
        </div>
      </div>
    </div>
  );
}
