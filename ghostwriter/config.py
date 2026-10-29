"""Central configuration, read from environment variables (prefix GW_) or a .env file."""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All tunable values in one place. See .env.example for documentation."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_prefix="GW_", extra="ignore"
    )

    data_dir: Path = PROJECT_ROOT / "data"
    models_dir: Path = PROJECT_ROOT / "models"

    ffmpeg_bin: str = "ffmpeg"  # a full path works too, if ffmpeg isn't on PATH

    ollama_url: str = "http://127.0.0.1:11434"
    llm_model: str = "gemma4:e4b"
    llm_num_ctx: int = 8192  # Ollama's smaller default would silently cut long transcripts

    whisper_model: str = "small"
    whisper_compute_type: str = "int8"
    whisper_language: str = ""  # e.g. "hi" to force Hindi; empty means auto-detect

    tts_enabled: bool = True
    piper_bin: str = "piper"  # or the full path to piper.exe
    piper_voice: str = "en_GB-northern_english_male-medium"  # file name in models/piper/

    plain_mode_default: bool = False

    @field_validator("data_dir", "models_dir")
    @classmethod
    def _anchor_to_project(cls, path: Path) -> Path:
        """Relative paths in .env mean 'inside the project', not 'wherever you ran it from'."""
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def db_path(self) -> Path:
        return self.data_dir / "ghostwriter.db"

    @property
    def whisper_path(self) -> Path:
        """Plain folder holding the faster-whisper weights, e.g. models/whisper/small/model.bin."""
        return self.models_dir / "whisper" / self.whisper_model

    @property
    def piper_voice_path(self) -> Path:
        """The Piper voice model, e.g. models/piper/en_GB-northern_english_male-medium.onnx (+ .onnx.json)."""
        return self.models_dir / "piper" / f"{self.piper_voice}.onnx"


settings = Settings()
