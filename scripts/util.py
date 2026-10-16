"""Miúdos que todos os scripts usam: ffmpeg, caminhos, plataforma, cronômetro.

Nada aqui sabe de vídeo; sabe de máquina.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ASSETS = RAIZ / "assets"
FONTE_TITULO = ASSETS / "fontes" / "Montserrat[wght].ttf"
FONTE_MONO = ASSETS / "fontes" / "IBMPlexMono-Regular.ttf"
RNNOISE = ASSETS / "rnnoise" / "sh.rnnn"
TRILHAS = ASSETS / "trilhas"

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts"}

# Quantas threads o ffmpeg pode usar. Sem teto ele toma a máquina inteira, e num Mac de 16 GB
# com outra coisa rodando isso já travou tudo. 4 é o bastante pra não doer e não travar.
THREADS = str(max(2, min(4, (os.cpu_count() or 4) // 2)))


class Falha(SystemExit):
    """Erro com mensagem pra gente ler, sem traceback."""

    def __init__(self, msg: str):
        super().__init__(f"cyborgcut: {msg}")


# ---------------------------------------------------------------- plataforma
def so() -> str:
    """'mac', 'linux' ou 'windows'."""
    s = sys.platform
    if s == "darwin":
        return "mac"
    if s.startswith("win"):
        return "windows"
    return "linux"


def apple_silicon() -> bool:
    return so() == "mac" and platform.machine() == "arm64"


def tem(programa: str) -> str | None:
    return shutil.which(programa)


@lru_cache(maxsize=None)
def filtros_ffmpeg() -> set[str]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
    out = set()
    for linha in r.stdout.splitlines():
        partes = linha.split()
        if len(partes) >= 2 and partes[0] and partes[0][0] in ".T":
            out.add(partes[1])
    return out


def tem_filtro(nome: str) -> bool:
    return nome in filtros_ffmpeg()


# ---------------------------------------------------------------- ffmpeg
def run(cmd: list, quieto=True, erro="comando falhou") -> subprocess.CompletedProcess:
    cmd = [str(c) for c in cmd]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        cauda = (r.stderr or r.stdout or "")[-1500:]
        raise Falha(f"{erro}\n  $ {' '.join(cmd)}\n{cauda}")
    return r


def ffmpeg(args: list, erro="ffmpeg falhou") -> subprocess.CompletedProcess:
    """ffmpeg quieto, com teto de threads na decodificação, nos filtros e na codificação."""
    args = [str(a) for a in args]
    if "-threads" not in args:
        # encoder: antes do último argumento (a saída); decoder e filtros: no começo
        args = ["-threads", THREADS, "-filter_threads", THREADS, *args[:-1], "-threads", THREADS, args[-1]]
    return run(["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y", *args], erro=erro)


def _ancestrais() -> set[int]:
    """Meu pid e os de quem me chamou (o shell que me lançou pode ter 'ffmpeg' na linha de comando)."""
    out, pid = set(), os.getpid()
    for _ in range(12):
        out.add(pid)
        try:
            r = subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True, text=True)
            pid = int(r.stdout.strip() or 0)
        except Exception:
            break
        if pid <= 1:
            break
    return out


def outros_renders() -> list[str]:
    """Processos pesados de vídeo que NÃO são meus nem de quem me chamou: ffmpeg, avconvert,
    whisper e transcrições de outra sessão. Olha o programa, não a linha de comando inteira."""
    try:
        r = subprocess.run(["ps", "-Ao", "pid,ppid,command"], capture_output=True, text=True)
    except Exception:
        return []
    ignorar = _ancestrais()
    out = []
    for linha in r.stdout.splitlines()[1:]:
        partes = linha.split(None, 2)
        if len(partes) < 3:
            continue
        pid, ppid, cmd = int(partes[0]), int(partes[1]), partes[2]
        if pid in ignorar or ppid in ignorar:
            continue
        prog = os.path.basename(cmd.split()[0]).lower()
        pesado = prog in ("ffmpeg", "avconvert", "whisper-cli", "whisper")
        if not pesado and prog.startswith("python"):
            pesado = any(k in cmd for k in ("transcrever.py", "transcribe.py", "whisper", "montar"))
        if pesado:
            out.append(cmd[:100])
    return out


def esperar_maquina(limite_s: int = 1800):
    """Se outra sessão está renderizando, espera ela acabar antes de pesar a máquina."""
    t0 = time.time()
    avisado = False
    while time.time() - t0 < limite_s:
        outros = outros_renders()
        if not outros:
            return
        if not avisado:
            aviso(f"outro render em andamento nesta máquina, esperando pra não travar: {outros[0]}")
            avisado = True
        time.sleep(10)
    aviso("outro render não terminou em 30 min; seguindo mesmo assim, com poucas threads")


def ffprobe(path: Path) -> dict:
    r = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            erro=f"ffprobe não abriu {path}")
    return json.loads(r.stdout)


def info_video(path: Path) -> dict:
    """Duração, tamanho já virado em pé (rotation aplicada), fps, transferência de cor, se tem áudio."""
    d = ffprobe(path)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    if v is None:
        raise Falha(f"{path.name} não tem vídeo")
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    if "rotate" in (v.get("tags") or {}):
        rot = int(v["tags"]["rotate"])
    w, h = int(v["width"]), int(v["height"])
    if rot % 180 != 0:
        w, h = h, w
    num, den = (v.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den or 1)
    return dict(
        duracao=float(d["format"].get("duration") or v.get("duration") or 0),
        largura=w, altura=h, fps=fps, rotacao=rot,
        transferencia=v.get("color_transfer") or "",
        primarias=v.get("color_primaries") or "",
        codec=v.get("codec_name"), pix_fmt=v.get("pix_fmt"),
        tem_audio=a is not None,
    )


def duracao(path: Path) -> float:
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(r.stdout.strip() or 0)


def caminho_filtro(p: Path) -> str:
    """Caminho dentro de um filtro do ffmpeg. No Windows o ':' do 'C:' é separador de opção,
    então vai escapado; a barra invertida também."""
    s = str(Path(p).resolve())
    if so() == "windows":
        s = s.replace("\\", "/").replace(":", "\\:")
    return s.replace("'", "\\'")


def hardlink_ou_copia(origem: Path, destino: Path):
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        destino.unlink()
    try:
        os.link(origem, destino)
    except OSError:
        shutil.copy2(origem, destino)


def videos_em(pasta: Path) -> list[Path]:
    return sorted(p for p in pasta.iterdir() if p.suffix.lower() in VIDEO_EXT and not p.name.startswith("."))


# ---------------------------------------------------------------- cronômetro
class Cronometro:
    """Anota quanto cada etapa levou, em `tempos.tsv` da pasta de trabalho."""

    def __init__(self, arquivo: Path):
        self.arquivo = arquivo
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        if not self.arquivo.exists():
            self.arquivo.write_text("etapa\tinicio\tfim\tsegundos\n", encoding="utf-8")

    @contextmanager
    def etapa(self, nome: str):
        t0 = time.time()
        try:
            yield
        finally:
            t1 = time.time()
            with self.arquivo.open("a", encoding="utf-8") as fh:
                fh.write(f"{nome}\t{int(t0)}\t{int(t1)}\t{t1 - t0:.1f}\n")
            print(f"  [{t1 - t0:6.1f}s] {nome}", flush=True)


def aviso(msg: str):
    print(f"aviso: {msg}", file=sys.stderr, flush=True)
