"""
MV Cliente IA · cama musical de los videos
==========================================
Una pista suave sintetizada con el propio ffmpeg: no hay un mp3 de un banco
de música con licencia que vencer ni que versionar, y sale del mismo largo
que el video. Son acordes en colchón (la menor · fa · do · sol, la vuelta más
gastada del pop, a propósito: no tiene que llamar la atención) con ataque y
caída lentos, un eco corto y un corte de agudos para que no compita con la
voz. El video la baja sola cuando habla la locución (ver `mezclar`).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

# Frecuencias (Hz) de cada acorde: fundamental grave, tercera, quinta, octava.
ACORDES = (
    (110.00, 130.81, 164.81, 220.00),   # La menor
    (87.31, 110.00, 130.81, 174.61),    # Fa
    (130.81, 164.81, 196.00, 261.63),   # Do
    (98.00, 123.47, 146.83, 196.00),    # Sol
)
COMPAS = 4.0          # segundos por acorde
VOLUMEN = 0.50        # de la cama, antes de la atenuación bajo la voz


def _acorde(frecuencias: tuple[float, ...]) -> str:
    """Expresión de aevalsrc: suma de senos con envolvente de entrada y
    salida de un segundo, para que el cambio de acorde no haga clic."""
    pesos = (1.0, 0.55, 0.5, 0.3)
    suma = "+".join(f"{p}*sin(2*PI*{f}*t)" for p, f in zip(pesos, frecuencias, strict=True))
    return f"0.18*({suma})*min(1,t/1.2)*min(1,({COMPAS}-t)/1.0)"


def pista(ff: str, segundos: float, destino: Path) -> Path:
    """Una cama de `segundos` (la vuelta de acordes repetida) en estéreo."""
    vueltas = int(segundos // (COMPAS * len(ACORDES))) + 1
    entradas, etiquetas = [], []
    for i, frec in enumerate(ACORDES * vueltas):
        entradas += ["-f", "lavfi", "-i",
                     f"aevalsrc='{_acorde(frec)}':s=44100:d={COMPAS}"]
        etiquetas.append(f"[{i}:a]")
    filtro = (f"{''.join(etiquetas)}concat=n={len(etiquetas)}:v=0:a=1,"
              "lowpass=f=1800,aecho=0.8:0.6:90|180:0.25|0.15,"
              f"volume={VOLUMEN},atrim=0:{segundos:.2f},"
              f"afade=t=in:st=0:d=1.5,afade=t=out:st={max(0, segundos - 2.5):.2f}:d=2.5,"
              "pan=stereo|c0=c0|c1=c0")
    subprocess.run([ff, "-y", "-loglevel", "error", *entradas,
                    "-filter_complex", filtro, "-ar", "44100", str(destino)], check=True)
    return destino


def mezclar(ff: str, video: Path, cama: Path, destino: Path) -> Path:
    """Video + cama con atenuación automática: la locución comprime la
    música (sidechain), así la voz siempre se entiende y en los respiros
    entre escenas la música sube sola."""
    filtro = ("[0:a]asplit=2[voz][llave];"
              "[1:a][llave]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[cama];"
              "[voz][cama]amix=inputs=2:duration=first:normalize=0[a]")
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(video), "-i", str(cama),
                    "-filter_complex", filtro, "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", str(destino)], check=True)
    return destino
