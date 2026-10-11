import { useQueryClient } from "@tanstack/react-query";
import { FileUp } from "lucide-react";
import { Fragment, useId, useState, type DragEvent } from "react";

import { useIngestJobs, type IngestJob, type IngestStatus } from "@/api/ingest";
import ProgressBar from "@/components/ProgressBar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { startTransfer, useTransfer, type Transfer } from "@/lib/transfer";

// The "Загрузка" page (SPEC §6.4): a file goes to the server with its own progress bar (XHR),
// its processing has another one (ingest.progress over SSE, see useEvents), and the history lists
// the reports of past uploads.

const STATUS_LABELS: Record<IngestStatus, string> = {
  queued: "В очереди",
  processing: "Обработка",
  done: "Готово",
  failed: "Ошибка",
};

const KIND_LABELS = { invalid: "некорректная запись", conflict: "конфликт" } as const;

const numberFormat = new Intl.NumberFormat("ru-RU");

function formatNumber(value: number): string {
  return numberFormat.format(value);
}

function formatMb(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toLocaleString("ru-RU", { maximumFractionDigits: 1 })} МБ`;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

function percent(part: number, whole: number): number {
  return whole > 0 ? Math.min(100, Math.round((part / whole) * 100)) : 0;
}

function isActive(job: IngestJob): boolean {
  return job.status === "queued" || job.status === "processing";
}

// The job of this tab's upload while it runs; otherwise the newest running job of the user
// (e.g. from another tab); otherwise this tab's finished job.
function processingJob(jobs: IngestJob[] | undefined, jobId: string | undefined) {
  if (!jobs) return undefined;
  const own = jobs.find((job) => job.id === jobId);
  if (own && isActive(own)) return own;
  return jobs.find(isActive) ?? own;
}

export default function Upload() {
  const queryClient = useQueryClient();
  const jobs = useIngestJobs();
  const transfer = useTransfer();
  const job = processingJob(jobs.data, transfer?.jobId);

  return (
    <div className="grid grid-cols-1 gap-6">
      <Card>
        <CardHeader>
          <CardTitle>
            <h2>Загрузка</h2>
          </CardTitle>
          <CardDescription>
            Файл NDJSON (генератор htgen или экспорт устройств), до 500 МБ. Пока файл
            обрабатывается, можно открывать другие разделы.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-5">
          <DropZone
            disabled={transfer?.status === "sending"}
            onFile={(file) => void startTransfer(file, queryClient)}
          />
          {transfer && <TransferProgress transfer={transfer} />}
          {job && <JobProgress job={job} />}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>
            <h2>История загрузок</h2>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <History jobs={jobs} />
        </CardContent>
      </Card>
    </div>
  );
}

function DropZone({ disabled, onFile }: { disabled: boolean; onFile: (file: File) => void }) {
  const id = useId();
  const [over, setOver] = useState(false);

  const drop = (event: DragEvent) => {
    event.preventDefault();
    setOver(false);
    const file = event.dataTransfer.files[0];
    if (file && !disabled) onFile(file);
  };

  return (
    <label
      htmlFor={id}
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={drop}
      className={`flex flex-col items-center gap-2 rounded-lg border-2 border-dashed px-4 py-8 text-center text-sm ${
        disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:bg-accent/50"
      } ${over ? "border-primary bg-accent/50" : "border-muted-foreground/30"}`}
    >
      <FileUp aria-hidden className="size-8 text-muted-foreground" />
      <span>
        Перетащите файл сюда или <span className="font-medium underline">выберите файл</span>
      </span>
      <input
        id={id}
        type="file"
        accept=".ndjson,.jsonl,.json,.txt,application/x-ndjson"
        aria-label="Выберите файл NDJSON"
        className="sr-only"
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0];
          // The same file may be chosen again later.
          event.target.value = "";
          if (file) onFile(file);
        }}
      />
    </label>
  );
}

function TransferProgress({ transfer }: { transfer: Transfer }) {
  const value = transfer.status === "sent" ? 100 : percent(transfer.loaded, transfer.total);
  return (
    <section aria-label="Передача файла" className="grid gap-2">
      <div className="flex flex-wrap justify-between gap-x-4 text-sm">
        <span className="min-w-0 truncate font-medium">Передача файла · {transfer.fileName}</span>
        <span className="text-muted-foreground">
          {formatMb(transfer.loaded)} из {formatMb(transfer.total)}
        </span>
      </div>
      <ProgressBar label="Передача файла" value={value} />
      {transfer.status === "sent" && (
        <p className="text-sm text-muted-foreground">Файл передан, идёт обработка.</p>
      )}
      {transfer.status === "failed" && (
        <p role="alert" className="text-sm text-destructive">
          {transfer.error}
        </p>
      )}
    </section>
  );
}

function JobProgress({ job }: { job: IngestJob }) {
  const { counts } = job;
  return (
    <section aria-label="Обработка" className="grid gap-2">
      <div className="flex flex-wrap justify-between gap-x-4 text-sm">
        <span className="min-w-0 truncate font-medium">
          Обработка · {job.filename ?? "поток"}
        </span>
        <span className={job.status === "failed" ? "text-destructive" : "text-muted-foreground"}>
          {STATUS_LABELS[job.status]}
        </span>
      </div>
      <ProgressBar label="Обработка" value={Math.round(job.progress * 100)} />
      <p className="text-sm text-muted-foreground">
        {formatMb(job.bytes_done)} из {formatMb(job.bytes_total)} · новых {formatNumber(counts.new)},
        дублей {formatNumber(counts.duplicate)}, конфликтов {formatNumber(counts.conflict)},
        некорректных {formatNumber(counts.invalid)}
      </p>
    </section>
  );
}

function History({ jobs }: { jobs: ReturnType<typeof useIngestJobs> }) {
  if (jobs.isPending) {
    return (
      <div role="status" aria-label="Загрузка истории" className="grid gap-2">
        {[0, 1, 2].map((row) => (
          <div key={row} className="h-8 animate-pulse rounded bg-muted" />
        ))}
      </div>
    );
  }
  if (jobs.isError) {
    return (
      <div role="alert" className="grid justify-items-start gap-3 text-sm">
        <p>Не удалось загрузить историю.</p>
        <Button variant="outline" size="sm" onClick={() => void jobs.refetch()}>
          Повторить
        </Button>
      </div>
    );
  }
  if (jobs.data.length === 0) {
    return <p className="text-sm text-muted-foreground">Загрузок пока нет — загрузите файл.</p>;
  }
  return (
    // On a phone the table scrolls inside its box, the page itself does not (SPEC §4).
    <div className="overflow-x-auto">
      <table aria-label="История загрузок" className="w-full text-sm">
        <thead className="text-left text-muted-foreground">
          <tr className="border-b">
            <th className="py-2 pr-3 font-medium">Файл</th>
            <th className="py-2 pr-3 font-medium">Загружен</th>
            <th className="py-2 pr-3 font-medium">Статус</th>
            <th className="py-2 pr-3 text-right font-medium">Всего</th>
            <th className="py-2 pr-3 text-right font-medium">Новые</th>
            <th className="py-2 pr-3 text-right font-medium">Дубли</th>
            <th className="py-2 pr-3 text-right font-medium">Конфликты</th>
            <th className="py-2 pr-3 text-right font-medium">Некорректные</th>
            <th className="py-2 font-medium">
              <span className="sr-only">Подробности</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {jobs.data.map((job) => (
            <HistoryRow key={job.id} job={job} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HistoryRow({ job }: { job: IngestJob }) {
  const [open, setOpen] = useState(false);
  const detailsId = useId();
  const { counts, errors, warnings } = job;
  const notes = errors.length + warnings.length;
  const label = errors.length > 0 ? `Ошибки (${errors.length})` : `Предупреждения (${warnings.length})`;
  const number = "py-2 pr-3 text-right tabular-nums";

  return (
    <Fragment>
      <tr className="border-b align-top">
        <td className="max-w-48 truncate py-2 pr-3">{job.filename ?? "поток"}</td>
        <td className="py-2 pr-3 whitespace-nowrap">{formatTime(job.created_at)}</td>
        <td className={`py-2 pr-3 ${job.status === "failed" ? "text-destructive" : ""}`}>
          {STATUS_LABELS[job.status]}
        </td>
        <td className={number}>{formatNumber(counts.total)}</td>
        <td className={number}>{formatNumber(counts.new)}</td>
        <td className={number}>{formatNumber(counts.duplicate)}</td>
        <td className={number}>{formatNumber(counts.conflict)}</td>
        <td className={number}>{formatNumber(counts.invalid)}</td>
        <td className="py-1">
          {notes > 0 && (
            <Button
              variant="ghost"
              size="sm"
              aria-expanded={open}
              aria-controls={detailsId}
              onClick={() => setOpen(!open)}
            >
              {label}
            </Button>
          )}
        </td>
      </tr>
      {open && (
        <tr id={detailsId} className="border-b bg-muted/40">
          <td colSpan={9} className="px-3 py-2">
            <ul className="grid gap-1 text-xs">
              {errors.map((error) => (
                <li key={`${error.kind}-${error.line}`}>
                  Строка {error.line} — {KIND_LABELS[error.kind]}: {error.reason}
                </li>
              ))}
              {warnings.map((warning) => (
                <li key={warning} className="text-muted-foreground">
                  {warning}
                </li>
              ))}
            </ul>
            {errors.length >= 50 && (
              <p className="mt-1 text-xs text-muted-foreground">Показаны первые 50 строк.</p>
            )}
          </td>
        </tr>
      )}
    </Fragment>
  );
}
