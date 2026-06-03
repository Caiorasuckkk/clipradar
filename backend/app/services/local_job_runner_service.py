from __future__ import annotations

import json
import os
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
            _p("include_diagnostics", "--include-diagnostics", "bool"),
            _p("download_missing", "--download-missing", "bool"),
            _p("overwrite", "--overwrite", "bool"),
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
        COMMON_ARGS + (_p("include_diagnostics", "--include-diagnostics", "bool"), _p("overwrite", "--overwrite", "bool")),
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
        sanitized = self._sanitize_params(definition, params or {})
        command = self._build_command(definition, sanitized)
        run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8]
        run = {
            "run_id": run_id,
            "job_key": job_key,
            "command": command,
            "params": sanitized,
            "status": "queued",
            "started_at": None,
            "finished_at": None,
            "elapsed_seconds": None,
            "stdout_tail": "",
            "stderr_tail": "",
            "full_stdout_path": str(self._stdout_path(run_id)),
            "full_stderr_path": str(self._stderr_path(run_id)),
            "exit_code": None,
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
        return self._normalize_stale_run(self._load_run(run_id))

    def get_logs(self, run_id: str) -> dict[str, Any] | None:
        run = self._load_run(run_id)
        if not run:
            return None
        return {
            "run_id": run_id,
            "status": run.get("status"),
            "stdout_tail": _tail(_read_text(Path(str(run.get("full_stdout_path") or "")))),
            "stderr_tail": _tail(_read_text(Path(str(run.get("full_stderr_path") or "")))),
        }

    def mark_cancel_unsupported(self, run_id: str) -> dict[str, Any] | None:
        run = self._load_run(run_id)
        if not run:
            return None
        run["cancel_supported"] = False
        run["cancel_message"] = "cancel_not_supported_in_this_version"
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
        run.update({"status": "running", "started_at": started_at})
        self._write_run(run)
        exit_code: int | None = None
        try:
            with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_file, stderr_path.open(
                "w", encoding="utf-8", errors="replace"
            ) as stderr_file:
                env = dict(**os.environ, PYTHONUNBUFFERED="1")
                completed = subprocess.run(
                    command,
                    cwd=str(config.BACKEND_DIR),
                    env=env,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=7200,
                    check=False,
                )
                exit_code = completed.returncode
        except Exception as exc:
            stderr_path.write_text(str(exc), encoding="utf-8")
            exit_code = -1

        finished_at = datetime.utcnow().isoformat()
        stdout = _read_text(stdout_path)
        stderr = _read_text(stderr_path)
        run = self._load_run(run_id) or run
        run.update(
            {
                "status": "success" if exit_code == 0 else "failed",
                "finished_at": finished_at,
                "elapsed_seconds": round(time.perf_counter() - started_perf, 2),
                "stdout_tail": _tail(stdout),
                "stderr_tail": _tail(stderr),
                "exit_code": exit_code,
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

    def _normalize_stale_run(self, run: dict[str, Any] | None) -> dict[str, Any] | None:
        if not run or run.get("status") not in {"queued", "running"}:
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
