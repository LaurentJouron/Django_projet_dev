from pathlib import Path

from environ import Env

BASE_DIR = Path(__file__).resolve().parent.parent

env = Env()
env_files = [
    BASE_DIR / ".env",
    BASE_DIR / ".env.local",  # For local configurations
    BASE_DIR
    / f".env.{env('DJANGO_ENV', default='development')}",  # For different environments
]

for env_file in env_files:
    if env_file.exists():
        env.read_env(env_file)
