from __future__ import annotations

from pathlib import Path

from app.config import STORAGE_DOWNLOADS_DIR


class DownloaderService:
    BASE_DIR = STORAGE_DOWNLOADS_DIR

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or self.BASE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def download(self, video_id: str, video_url: str) -> str | None:
        existing_path = self.get_path(video_id)
        if existing_path:
            return existing_path

        print(f"DOWNLOAD iniciando: {video_id} — {video_url}")
        try:
            from yt_dlp import YoutubeDL

            output_template = str(self.base_dir / f"{video_id}.%(ext)s")
            options = {
                "format": "bestaudio[ext=m4a]/bestaudio/best",
                "outtmpl": output_template,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
                "ignoreerrors": True,
                "socket_timeout": 120,
                "retries": 1,
                "fragment_retries": 1,
            }
            with YoutubeDL(options) as downloader:
                downloader.download([video_url])

            downloaded_path = self.get_path(video_id)
            if not downloaded_path:
                print(f"DOWNLOAD falhou: {video_id} — arquivo nao encontrado apos download")
                return None

            size_mb = Path(downloaded_path).stat().st_size / (1024 * 1024)
            print(f"DOWNLOAD concluído: {video_id} — {size_mb:.1f} MB")
            return downloaded_path
        except Exception as exc:
            print(f"DOWNLOAD falhou: {video_id} — {exc}")
            return None

    def cleanup(self, video_id: str) -> None:
        for path in self.base_dir.glob(f"{video_id}.*"):
            try:
                path.unlink()
            except OSError as exc:
                print(f"DOWNLOAD cleanup falhou: {video_id} — {exc}")

    def get_path(self, video_id: str) -> str | None:
        for path in self.base_dir.glob(f"{video_id}.*"):
            if path.is_file():
                return str(path)
        return None
