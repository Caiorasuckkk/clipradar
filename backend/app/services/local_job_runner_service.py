from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from app import config
from app.services.candidate_review_service import filter_candidate_clips, load_candidate_queue
from app.services.log_sanitizer import sanitize


ParamType = Literal["bool", "int", "float", "str"]


@dataclass(frozen=True)
class JobParam:
    name: str
    flag: str
    param_type: ParamType


@dataclass(frozen=True)
class JobDefinition:
    job_key: str
    label: str
    description: str
    module: str
    allowed_args: tuple[JobParam, ...]
    is_long_running: bool
    category: str

    @property
    def command_base(self) -> list[str]:
        return [sys.executable, "-m", self.module]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "job_key": self.job_key,
            "label": self.label,
            "description": self.description,
            "command_base": f"python -m {self.module}",
            "allowed_args": [
                {"name": arg.name, "flag": arg.flag, "type": arg.param_type}
                for arg in self.allowed_args
            ],
            "is_long_running": self.is_long_running,
            "category": self.category,
        }


def _p(name: str, flag: str, param_type: ParamType) -> JobParam:
    return JobParam(name=name, flag=flag, param_type=param_type)


COMMON_ARGS = (
    _p("video_id", "--video-id", "str"),
    _p("limit", "--limit", "int"),
)

LOCKED_JOB_KEYS = {"find_videos_flow", "pipeline_ready_to_post", "render_candidate_previews"}


JOB_DEFINITIONS: dict[str, JobDefinition] = {
    "batch_status": JobDefinition(
        "batch_status",
        "Batch status",
        "Mostra o estado geral do lote local.",
        "app.jobs.batch_status",
        (_p("json", "--json", "bool"), _p("video_id", "--video-id", "str")),
        False,
        "status",
    ),
    "cleanup_stale_job_runs": JobDefinition(
        "cleanup_stale_job_runs",
        "Limpar runs presos",
        "Marca runs running sem processo vivo como stale/cancelled.",
        "app.jobs.cleanup_stale_job_runs",
        (),
        False,
        "maintenance",
    ),
    "discover_podcast_batch": JobDefinition(
        "discover_podcast_batch",
        "Descobrir videos",
        "Roda discovery de formatos cortáveis.",
        "app.jobs.discover_podcast_batch",
        (),
        True,
        "discovery",
    ),
    "find_videos_flow": JobDefinition(
        "find_videos_flow",
        "Encontrar vídeos",
        "Busca vídeos, processa os melhores, gera previews e prepara Candidate Clips.",
        "app.jobs.pipeline_find_candidates",
        (
            _p("max_videos", "--max-videos", "int"),
            _p("max_previews", "--max-previews", "int"),
            _p("max_previews_initial", "--max-previews-initial", "int"),
            _p("max_previews_total", "--max-previews-total", "int"),
            _p("render_all_good_candidates", "--render-all-good-candidates", "bool"),
            _p("include_diagnostics", "--include-diagnostics", "bool"),
            _p("download_missing", "--download-missing", "bool"),
            _p("overwrite", "--overwrite", "bool"),
            _p("no_candidate_limit", "--no-candidate-limit", "bool"),
            _p("max_candidates_per_video", "--max-candidates-per-video", "str"),
            _p("min_ranking_score", "--min-ranking-score", "float"),
            _p("min_source_score", "--min-source-score", "float"),
            _p("min_duration", "--min-duration", "float"),
            _p("max_duration", "--max-duration", "float"),
            _p("quality_threshold", "--quality-threshold", "float"),
            _p("dedup_overlap", "--dedup-overlap", "float"),
            _p("fast_mode", "--fast-mode", "bool"),
            _p("min_reviewable_to_release", "--min-reviewable-to-release", "int"),
            _p("max_seconds_before_partial_release", "--max-seconds-before-partial-release", "int"),
            _p("dry_run", "--dry-run", "bool"),
            _p("continue_on_error", "--continue-on-error", "bool"),
        ),
        True,
        "workflow",
    ),
    "review_selected_videos": JobDefinition(
        "review_selected_videos",
        "Ver selecionados",
        "Atualiza/revisa seleção de vídeos.",
        "app.jobs.review_selected_videos",
        (),
        False,
        "discovery",
    ),
    "process_queue": JobDefinition(
        "process_queue",
        "Process queue",
        "Processa a fila local de vídeos.",
        "app.jobs.process_queue",
        (_p("video_ids", "--video-ids", "str"), _p("dry_run", "--dry-run", "bool")),
        True,
        "discovery",
    ),
    "export_candidate_review_queue": JobDefinition(
        "export_candidate_review_queue",
        "Gerar fila de candidatos",
        "Exporta a fila mobile de Candidate Clips.",
        "app.jobs.export_candidate_review_queue",
        COMMON_ARGS
        + (
            _p("include_diagnostics", "--include-diagnostics", "bool"),
            _p("overwrite", "--overwrite", "bool"),
            _p("no_candidate_limit", "--no-candidate-limit", "bool"),
            _p("max_candidates_per_video", "--max-candidates-per-video", "str"),
            _p("min_ranking_score", "--min-ranking-score", "float"),
            _p("min_source_score", "--min-source-score", "float"),
            _p("min_duration", "--min-duration", "float"),
            _p("max_duration", "--max-duration", "float"),
            _p("quality_threshold", "--quality-threshold", "float"),
            _p("dedup_overlap", "--dedup-overlap", "float"),
        ),
        False,
        "candidates",
    ),
    "audit_candidates_by_video": JobDefinition(
        "audit_candidates_by_video",
        "Auditar candidates por vídeo",
        "Mostra quantos candidates cada vídeo gerou, filtrou, deduplicou e quantos previews estão prontos.",
        "app.jobs.audit_candidates_by_video",
        (_p("video_id", "--video-id", "str"), _p("json", "--json", "bool")),
        False,
        "candidates",
    ),
    "list_candidate_preview_status": JobDefinition(
        "list_candidate_preview_status",
        "Status dos previews",
        "Lista previews prontos e faltantes.",
        "app.jobs.list_candidate_preview_status",
        (_p("video_id", "--video-id", "str"), _p("missing_only", "--missing-only", "bool")),
        False,
        "candidates",
    ),
    "render_candidate_previews": JobDefinition(
        "render_candidate_previews",
        "Renderizar previews",
        "Renderiza previews faltantes para revisão mobile.",
        "app.jobs.render_candidate_previews",
        COMMON_ARGS
        + (
            _p("candidate_id", "--candidate-id", "str"),
            _p("overwrite", "--overwrite", "bool"),
            _p("dry_run", "--dry-run", "bool"),
            _p("download_missing", "--download-missing", "bool"),
            _p("only_missing", "--only-missing", "bool"),
            _p("max_missing", "--max-missing", "int"),
            _p("max_previews_initial", "--max-previews-initial", "int"),
            _p("max_previews_total", "--max-previews-total", "int"),
            _p("render_all_good_candidates", "--render-all-good-candidates", "bool"),
            _p("retry_failed", "--retry-failed", "bool"),
            _p("clean_partials", "--clean-partials", "bool"),
            _p("rerender_invalid", "--rerender-invalid", "bool"),
            _p("rerender_all", "--rerender-all", "bool"),
        ),
        True,
        "candidates",
    ),
    "export_feedback_dataset": JobDefinition(
        "export_feedback_dataset",
        "Exportar feedback",
        "Exporta dataset de feedback revisado.",
        "app.jobs.export_feedback_dataset",
        (),
        False,
        "feedback",
    ),
    "analyze_feedback_dataset": JobDefinition(
        "analyze_feedback_dataset",
        "Analisar feedback",
        "Mostra análise do dataset de feedback.",
        "app.jobs.analyze_feedback_dataset",
        (),
        False,
        "feedback",
    ),
    "export_approved_clips_plan": JobDefinition(
        "export_approved_clips_plan",
        "Exportar approved plan",
        "Exporta plano de cortes aprovados.",
        "app.jobs.export_approved_clips_plan",
        COMMON_ARGS
        + (
            _p("min_rating", "--min-rating", "int"),
            _p("include_rating_3", "--include-rating-3", "bool"),
            _p("include_diagnostics", "--include-diagnostics", "bool"),
            _p("reason", "--reason", "str"),
        ),
        False,
        "production",
    ),
    "pipeline_ready_to_post": JobDefinition(
        "pipeline_ready_to_post",
        "Pipeline ready-to-post",
        "Executa o pipeline local de preparação para postagem manual.",
        "app.jobs.pipeline_ready_to_post",
        COMMON_ARGS
        + (
            _p("dry_run", "--dry-run", "bool"),
            _p("download_missing", "--download-missing", "bool"),
            _p("overwrite", "--overwrite", "bool"),
            _p("continue_on_error", "--continue-on-error", "bool"),
            _p("package_name", "--package-name", "str"),
            _p("skip_approved_plan", "--skip-approved-plan", "bool"),
            _p("skip_render_approved", "--skip-render-approved", "bool"),
            _p("skip_vertical", "--skip-vertical", "bool"),
            _p("skip_final", "--skip-final", "bool"),
            _p("skip_final_metadata", "--skip-final-metadata", "bool"),
            _p("skip_posting_package", "--skip-posting-package", "bool"),
        ),
        True,
        "production",
    ),
    "export_ready_to_post_package": JobDefinition(
        "export_ready_to_post_package",
        "Exportar package",
        "Exporta pacote local ready-to-post.",
        "app.jobs.export_ready_to_post_package",
        (
            _p("limit", "--limit", "int"),
            _p("dry_run", "--dry-run", "bool"),
            _p("overwrite", "--overwrite", "bool"),
            _p("package_name", "--package-name", "str"),
            _p("clean_old", "--clean-old", "bool"),
        ),
        False,
        "package",
    ),
    "generate_finals_for_approved_candidates": JobDefinition(
        "generate_finals_for_approved_candidates",
        "Gerar finais aprovados pendentes",
        "Roda a geração automática de finais para candidates aprovados pendentes.",
        "app.jobs.generate_finals_for_approved_candidates",
        (
            _p("candidate_id", "--candidate-id", "str"),
            _p("retry_failed", "--retry-failed", "bool"),
            _p("status_only", "--status-only", "bool"),
        ),
        True,
        "production",
    ),
    "audit_approved_generation": JobDefinition(
        "audit_approved_generation",
        "Auditar geração de aprovados",
        "Compara candidates aprovados com finais, package latest, post metadata e generation state.",
        "app.jobs.audit_approved_generation",
        (),
        False,
        "status",
    ),
    "export_post_metadata": JobDefinition(
        "export_post_metadata",
        "Gerar metadados de postagem",
        "Gera títulos, descrições e status local para postagem manual.",
        "app.jobs.export_post_metadata",
        (),
        False,
        "package",
    ),
    "list_failed_candidate_downloads": JobDefinition(
        "list_failed_candidate_downloads",
        "Downloads falhados",
        "Lista ou limpa falhas de download de candidates.",
        "app.jobs.list_failed_candidate_downloads",
        (
            _p("video_id", "--video-id", "str"),
            _p("clear", "--clear", "bool"),
            _p("clear_video_id", "--clear-video-id", "str"),
        ),
        False,
        "maintenance",
    ),
}


class LocalJobRunnerService:
    def __init__(self, runs_dir: Path | None = None) -> None:
        self.runs_dir = runs_dir or config.STORAGE_JOB_RUNS_DIR
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def list_jobs(self) -> list[dict[str, Any]]:
        return [job.to_public_dict() for job in JOB_DEFINITIONS.values()]

    def start_job(self, job_key: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        definition = JOB_DEFINITIONS.get(job_key)
        if not definition:
            raise ValueError("job_not_allowed")
        if job_key in LOCKED_JOB_KEYS:
            existing = self._find_live_locked_run(job_key)
            if existing:
                return {
                    "status": "already_running",
                    "run_id": existing["run_id"],
                    "message": "Uma busca já está em andamento." if job_key == "find_videos_flow" else "Job pesado já está em andamento.",
                }
        sanitized = self._sanitize_params(definition, params or {})
        command = self._build_command(definition, sanitized)
        run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8]
        run = {
            "run_id": run_id,
            "job_key": job_key,
            "command": command,
            "params": sanitized,
            "status": "queued",
            "created_at": datetime.utcnow().isoformat(),
            "started_at": None,
            "finished_at": None,
            "elapsed_seconds": None,
            "stdout_tail": "",
            "stderr_tail": "",
            "full_stdout_path": str(self._stdout_path(run_id)),
            "full_stderr_path": str(self._stderr_path(run_id)),
            "exit_code": None,
            "pid": None,
            "latest_error": "",
        }
        self._write_run(run)
        thread = threading.Thread(target=self._execute_run, args=(run_id, command), daemon=True)
        thread.start()
        return {"run_id": run_id, "status": "queued"}

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        paths = sorted(self.runs_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        runs = [self._normalize_stale_run(self._load_run(path.stem)) for path in paths[: max(1, min(limit, 100))]]
        return [run for run in runs if run]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self._enrich_live_run(self._normalize_stale_run(self._load_run(run_id)))

    def get_logs(self, run_id: str) -> dict[str, Any] | None:
        run = self._load_run(run_id)
        if not run:
            return None
        stdout = sanitize(_tail(_read_text(Path(str(run.get("full_stdout_path") or "")))))
        partial = _partial_status_from_stdout(stdout)
        return {
            "run_id": run_id,
            "job_key": run.get("job_key"),
            "status": run.get("status"),
            "pid": run.get("pid"),
            "started_at": run.get("started_at"),
            "elapsed_seconds": run.get("elapsed_seconds"),
            "command": run.get("command"),
            "latest_error": run.get("latest_error"),
            "warning_message": run.get("warning_message"),
            "candidate_count": run.get("candidate_count"),
            "preview_ready": run.get("preview_ready"),
            "missing_preview": run.get("missing_preview"),
            "pending_reviewable_count": run.get("pending_reviewable_count"),
            "next_action": run.get("next_action"),
            **partial,
            "stdout_tail": stdout,
            "stderr_tail": sanitize(_tail(_read_text(Path(str(run.get("full_stderr_path") or ""))))),
        }

    def cancel_run(self, run_id: str) -> dict[str, Any] | None:
        run = self._load_run(run_id)
        if not run:
            return None
        pid = _int_or_none(run.get("pid"))
        message = "job_cancelled"
        now = datetime.utcnow().isoformat()
        run.update(
            {
                "status": "cancelled",
                "finished_at": run.get("finished_at") or now,
                "elapsed_seconds": _elapsed_from_started_at(run.get("started_at")),
                "exit_code": -1,
                "latest_error": message,
                "cancel_supported": True,
                "cancel_message": message,
            }
        )
        self._write_run(run)
        if pid and _process_exists(pid):
            _terminate_process_tree(pid)
        elif pid:
            message = "process_not_found_marked_cancelled"
        else:
            message = "pid_missing_marked_cancelled"
        run.update(
            {
                "status": "cancelled",
                "finished_at": now,
                "elapsed_seconds": _elapsed_from_started_at(run.get("started_at")),
                "exit_code": -1,
                "latest_error": message,
                "cancel_supported": True,
                "cancel_message": message,
                "stdout_tail": _tail(_read_text(Path(str(run.get("full_stdout_path") or "")))),
                "stderr_tail": _tail(_read_text(Path(str(run.get("full_stderr_path") or "")))),
            }
        )
        self._write_run(run)
        return run

    def _execute_run(self, run_id: str, command: list[str]) -> None:
        run = self._load_run(run_id)
        if not run:
            return
        stdout_path = self._stdout_path(run_id)
        stderr_path = self._stderr_path(run_id)
        started_at = datetime.utcnow().isoformat()
        started_perf = time.perf_counter()
        exit_code: int | None = None
        process: subprocess.Popen[str] | None = None
        try:
            with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_file, stderr_path.open(
                "w", encoding="utf-8", errors="replace"
            ) as stderr_file:
                env = dict(**os.environ, PYTHONUNBUFFERED="1")
                process = subprocess.Popen(
                    command,
                    cwd=str(config.BACKEND_DIR),
                    env=env,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                run.update({"status": "running", "started_at": started_at, "pid": process.pid})
                self._write_run(run)
                exit_code = process.wait(timeout=7200)
        except subprocess.TimeoutExpired:
            if process and process.pid:
                _terminate_process_tree(process.pid)
            stderr_path.write_text("job_timeout_after_7200_seconds", encoding="utf-8")
            exit_code = -1
        except Exception as exc:
            stderr_path.write_text(sanitize(str(exc)), encoding="utf-8")
            exit_code = -1

        finished_at = datetime.utcnow().isoformat()
        stdout = sanitize(_read_text(stdout_path))
        stderr = sanitize(_read_text(stderr_path))
        run = self._load_run(run_id) or run
        if run.get("status") == "cancelled":
            run.update(
                {
                    "stdout_tail": _tail(stdout),
                    "stderr_tail": _tail(stderr),
                    "elapsed_seconds": run.get("elapsed_seconds") or round(time.perf_counter() - started_perf, 2),
                    "exit_code": -1,
                }
            )
            self._write_run(run)
            return
        stdout_status = _pipeline_status_from_stdout(stdout)
        run_status = stdout_status if stdout_status == "success_with_warnings" and exit_code == 0 else ("success" if exit_code == 0 else "failed")
        latest_error = "" if exit_code == 0 else _tail(stderr or stdout, 800)
        partial_stdout = _partial_status_from_stdout(stdout)
        partial_result = _partial_candidate_result_for_run(run) if run_status == "failed" else {}
        warning_message = _pipeline_warning_from_stdout(stdout)
        if partial_result:
            run_status = "success_with_warnings"
            warning_message = warning_message or "Candidatos foram encontrados, mas uma etapa auxiliar falhou."
        run.update(
            {
                "status": run_status,
                "finished_at": finished_at,
                "elapsed_seconds": round(time.perf_counter() - started_perf, 2),
                "stdout_tail": _tail(stdout),
                "stderr_tail": _tail(stderr),
                "exit_code": exit_code,
                "latest_error": latest_error,
                "warning_message": warning_message,
                **partial_stdout,
                **partial_result,
            }
        )
        self._write_run(run)

    def _sanitize_params(self, definition: JobDefinition, params: dict[str, Any]) -> dict[str, Any]:
        allowed = {param.name: param for param in definition.allowed_args}
        unknown = sorted(set(params) - set(allowed))
        if unknown:
            raise ValueError(f"params_not_allowed: {', '.join(unknown)}")
        sanitized: dict[str, Any] = {}
        for name, value in params.items():
            param = allowed[name]
            if value is None or value == "":
                continue
            sanitized[name] = _coerce_param(name, value, param.param_type)
        return sanitized

    def _build_command(self, definition: JobDefinition, params: dict[str, Any]) -> list[str]:
        allowed = {param.name: param for param in definition.allowed_args}
        command = list(definition.command_base)
        for name, value in params.items():
            param = allowed[name]
            if param.param_type == "bool":
                if value:
                    command.append(param.flag)
            else:
                command.extend([param.flag, str(value)])
        return command

    def _run_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.json"

    def _stdout_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}_stdout.txt"

    def _stderr_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}_stderr.txt"

    def _load_run(self, run_id: str) -> dict[str, Any] | None:
        path = self._run_path(run_id)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def _write_run(self, run: dict[str, Any]) -> None:
        path = self._run_path(str(run["run_id"]))
        with path.open("w", encoding="utf-8") as file:
            json.dump(run, file, ensure_ascii=False, indent=2)

    def cleanup_stale_runs(self, mark_status: str = "cancelled") -> dict[str, Any]:
        updated: list[str] = []
        for path in sorted(self.runs_dir.glob("*.json")):
            run = self._load_run(path.stem)
            if not run or run.get("status") not in {"queued", "running"}:
                continue
            pid = _int_or_none(run.get("pid"))
            if pid and _process_exists(pid):
                continue
            if _is_recently_touched(path, seconds=30):
                continue
            now = datetime.utcnow().isoformat()
            stale_update = _stale_run_update(run, mark_status, now)
            run.update(stale_update)
            self._write_run(run)
            updated.append(str(run.get("run_id") or path.stem))
        return {"updated_count": len(updated), "updated_run_ids": updated}

    def _find_live_locked_run(self, job_key: str) -> dict[str, Any] | None:
        paths = sorted(self.runs_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in paths:
            run = self._load_run(path.stem)
            if not run or run.get("job_key") != job_key or run.get("status") not in {"queued", "running"}:
                continue
            pid = _int_or_none(run.get("pid"))
            if pid and _process_exists(pid):
                return run
            if run.get("status") == "queued" and not pid and time.time() - path.stat().st_mtime < 30:
                return run
            run.update(_stale_run_update(run, "failed", datetime.utcnow().isoformat()))
            self._write_run(run)
        return None

    def _normalize_stale_run(self, run: dict[str, Any] | None) -> dict[str, Any] | None:
        if not run or run.get("status") not in {"queued", "running"}:
            return run
        pid = _int_or_none(run.get("pid"))
        if run.get("status") == "running" and pid and not _process_exists(pid):
            if _is_recently_touched(self._run_path(str(run.get("run_id") or "")), seconds=30):
                return run
            run.update(_stale_run_update(run, "failed", datetime.utcnow().isoformat()))
            self._write_run(run)
            return run
        started_at = run.get("started_at")
        if not started_at:
            return run
        try:
            started = datetime.fromisoformat(str(started_at))
        except ValueError:
            return run
        if (datetime.utcnow() - started).total_seconds() < 3 * 60 * 60:
            return run
        run.update(
            {
                "status": "failed",
                "finished_at": datetime.utcnow().isoformat(),
                "elapsed_seconds": None,
                "exit_code": -1,
                "stderr_tail": "stale_run_marked_failed_after_runner_interruption",
            }
        )
        self._write_run(run)
        return run

    def _enrich_live_run(self, run: dict[str, Any] | None) -> dict[str, Any] | None:
        if not run:
            return None
        stdout_path = Path(str(run.get("full_stdout_path") or ""))
        stderr_path = Path(str(run.get("full_stderr_path") or ""))
        stdout = _tail(_read_text(stdout_path))
        stderr = _tail(_read_text(stderr_path))
        if stdout:
            run["stdout_tail"] = stdout
        if stderr:
            run["stderr_tail"] = stderr
        if run.get("job_key") == "find_videos_flow":
            run.update(_partial_status_from_stdout(stdout))
        return run


def _coerce_param(name: str, value: Any, param_type: ParamType) -> Any:
    if param_type == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "sim"}:
                return True
            if lowered in {"false", "0", "no", "nao", "não"}:
                return False
        raise ValueError(f"invalid_bool_param: {name}")
    if param_type == "int":
        return int(value)
    if param_type == "float":
        return float(value)
    return str(value)


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _tail(value: str, limit: int = 4000) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def _int_or_none(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _process_exists(pid: int) -> bool:
    if os.name == "nt":
        try:
            completed = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
            )
            return str(pid) in (completed.stdout or "")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _terminate_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


def _elapsed_from_started_at(started_at: Any) -> float | None:
    if not started_at:
        return None
    try:
        started = datetime.fromisoformat(str(started_at))
    except ValueError:
        return None
    return round((datetime.utcnow() - started).total_seconds(), 2)


def _is_recently_touched(path: Path, seconds: int) -> bool:
    try:
        return time.time() - path.stat().st_mtime < seconds
    except OSError:
        return False


def _partial_candidate_result_for_run(run: dict[str, Any]) -> dict[str, Any]:
    if run.get("job_key") != "find_videos_flow":
        return {}
    try:
        clips = load_candidate_queue()
        pending_reviewable_count = len(
            filter_candidate_clips(
                clips,
                status="pending",
                include_missing_previews=False,
            )
        )
    except Exception:
        return {}

    candidate_count = len(clips)
    preview_ready = sum(1 for clip in clips if clip.get("preview_exists"))
    missing_preview = max(0, candidate_count - preview_ready)
    pending = sum(1 for clip in clips if not clip.get("already_reviewed"))
    if candidate_count <= 0 and preview_ready <= 0 and pending <= 0:
        return {}

    if pending_reviewable_count > 0:
        next_action = "open_candidate_clips"
    elif missing_preview > 0:
        next_action = "render_missing_previews"
    else:
        next_action = "search_more_content"

    return {
        "candidate_count": candidate_count,
        "preview_ready": preview_ready,
        "missing_preview": missing_preview,
        "pending_reviewable_count": pending_reviewable_count,
        "candidate_pending_reviews": pending,
        "next_action": next_action,
    }


def _stale_run_update(
    run: dict[str, Any],
    mark_status: str,
    finished_at: str,
) -> dict[str, Any]:
    partial_result = _partial_candidate_result_for_run(run)
    status = "success_with_warnings" if partial_result else mark_status
    return {
        "status": status,
        "finished_at": finished_at,
        "elapsed_seconds": _elapsed_from_started_at(run.get("started_at")),
        "exit_code": -1,
        "latest_error": "process_not_found_stale_run",
        "warning_message": (
            "Candidatos foram encontrados, mas uma etapa auxiliar falhou."
            if partial_result
            else ""
        ),
        "stderr_tail": _tail(
            (
                _read_text(Path(str(run.get("full_stderr_path") or "")))
                + "\nprocess_not_found_stale_run"
            ).strip()
        ),
        **partial_result,
    }


def _partial_status_from_stdout(stdout: str) -> dict[str, Any]:
    matches = re.findall(r"^\[partial_status\]\s+(.+)$", stdout or "", re.MULTILINE)
    if not matches:
        return {}
    values: dict[str, str] = {}
    for part in matches[-1].split():
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        values[key] = value
    partial_reviewable = values.get("partial_reviewable") == "true"
    payload = {
        "partial_reviewable": partial_reviewable,
        "partial_candidate_count": _int_or_none(values.get("partial_candidate_count")) or 0,
        "partial_preview_ready": _int_or_none(values.get("partial_preview_ready")) or 0,
        "partial_pending_reviewable_count": _int_or_none(values.get("partial_pending_reviewable_count")) or 0,
        "current_video_id": values.get("current_video_id", ""),
        "current_video_index": _int_or_none(values.get("current_video_index")),
        "total_videos": _int_or_none(values.get("total_videos")),
        "current_step_detail": values.get("current_step_detail", ""),
        "pending_reviewable_count": _int_or_none(values.get("partial_pending_reviewable_count")) or 0,
        "candidate_count": _int_or_none(values.get("partial_candidate_count")) or 0,
        "preview_ready": _int_or_none(values.get("partial_preview_ready")) or 0,
    }
    if partial_reviewable:
        payload["next_action"] = "open_candidate_clips"
    return payload


def _pipeline_status_from_stdout(stdout: str) -> str:
    match = re.search(r"^status:\s*(success_with_warnings|success|failed)\s*$", stdout or "", re.MULTILINE)
    return match.group(1) if match else ""


def _pipeline_warning_from_stdout(stdout: str) -> str:
    match = re.search(r"^warning_message:\s*(.+?)\s*$", stdout or "", re.MULTILINE)
    return match.group(1).strip() if match else ""
