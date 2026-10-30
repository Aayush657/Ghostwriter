"""Central configuration, read from environment variables (prefix GW_) or a .env file."""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# faster-whisper sizes, smallest and fastest first. scripts\setup.ps1 downloads the one in .env.
# Ghostwriter listens in English: the ".en" models are trained for it; the others work too, more slowly.
WHISPER_SIZES = ("tiny.en", "base.en", "small.en", "medium.en", "tiny", "base", "small", "medium",
                 "large-v3-turbo", "large-v3")


class Settings(BaseSettings):
    """All tunable values in one place. See .env.example for documentation."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_prefix="GW_", extra="ignore"
    )

    data_dir: Path = PROJECT_ROOT / "data"
    models_dir: Path = PROJECT_ROOT / "models"

    ffmpeg_bin: str = "ffmpeg"  # a full path works too, if ffmpeg isn't on PATH
    ffprobe_bin: str = ""  # empty: the ffprobe next to ffmpeg (every ffmpeg build ships both)
    max_audio_minutes: int = 30  # longer recordings are refused before anything is saved

    ollama_url: str = "http://127.0.0.1:11434"
    llm_model: str = "gemma4:e4b"
    llm_num_ctx: int = 8192  # Ollama's smaller default would silently cut long transcripts
    # Optional: lets the Seance find stories by meaning ("a good cook" finds the kadhi story).
    # Without it the Seance still works, by keywords only.
    embed_model: str = "embeddinggemma:300m-qat-q8_0"

    whisper_model: str = "small.en"  # one of WHISPER_SIZES; bigger hears names better but is slower
    whisper_compute_type: str = "int8"

    tts_enabled: bool = True
    piper_bin: str = "piper"  # or the full path to piper.exe
    piper_voice: str = "en_GB-cori-high"  # file name in models/piper/ (chosen in the voice lab)

    plain_mode_default: bool = False

    @field_validator("whisper_model")
    @classmethod
    def _known_whisper_size(cls, size: str) -> str:
        if size not in WHISPER_SIZES:
            raise ValueError(f"GW_WHISPER_MODEL must be one of: {', '.join(WHISPER_SIZES)}")
        return size

    @field_validator("data_dir", "models_dir")
    @classmethod
    def _anchor_to_project(cls, path: Path) -> Path:
        """Relative paths in .env mean 'inside the project', not 'wherever you ran it from'."""
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def db_path(self) -> Path:
        return self.data_dir / "ghostwriter.db"

    @property
    def ffprobe(self) -> str:
        if self.ffprobe_bin:
            return self.ffprobe_bin
        ffmpeg = Path(self.ffmpeg_bin)
        return str(ffmpeg.with_name(ffmpeg.name.replace("ffmpeg", "ffprobe"))) if ffmpeg.parent != Path() else "ffprobe"

    @property
    def whisper_path(self) -> Path:
        """Plain folder holding the faster-whisper weights, e.g. models/whisper/small/model.bin."""
        return self.models_dir / "whisper" / self.whisper_model

    @property
    def piper_voice_path(self) -> Path:
        """The Piper voice model, e.g. models/piper/en_GB-cori-high.onnx (+ .onnx.json)."""
        return self.models_dir / "piper" / f"{self.piper_voice}.onnx"


settings = Settings()
