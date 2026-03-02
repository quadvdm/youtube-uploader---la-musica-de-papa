#!/usr/bin/env python3
"""
Music Video + Metadata Generator
Genera un video desde 2 fotos + 1 audio WAV, hace OCR del texto en las fotos,
genera título/descripción/hashtags para subir manualmente a YouTube.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
import sys
import subprocess
import time
import shutil
import json
import urllib.request
import urllib.error

# ──────────────────────────────────────────────
# Instalación automática de dependencias
# ──────────────────────────────────────────────
REQUIRED_PACKAGES = [
    ("Pillow", "PIL"),
    ("pytesseract", "pytesseract"),
    ("moviepy", "moviepy"),
    ("numpy", "numpy"),
    ("opencv-python", "cv2"),
]

def install_if_missing():
    if getattr(sys, "frozen", False):
        return

    import importlib
    missing = []
    for pkg_name, import_name in REQUIRED_PACKAGES:
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing.append(pkg_name)
    if missing:
        print(f"Instalando paquetes faltantes: {missing}")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install"] + missing,
                stdout=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "No se pudieron instalar dependencias automáticamente. "
                "Instalalas manualmente con pip e intentá de nuevo."
            ) from exc

install_if_missing()

# ──────────────────────────────────────────────
# Imports post-instalación
# ──────────────────────────────────────────────
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import pytesseract
import numpy as np

# moviepy
import importlib
moviepy_module = importlib.import_module("moviepy")
if hasattr(moviepy_module, "ImageClip") and hasattr(moviepy_module, "AudioFileClip"):
    ImageClip = moviepy_module.ImageClip
    AudioFileClip = moviepy_module.AudioFileClip
else:
    editor_module = importlib.import_module("moviepy.editor")
    ImageClip = editor_module.ImageClip
    AudioFileClip = editor_module.AudioFileClip

import cv2


def configure_tesseract() -> bool:
    """Configura la ruta de Tesseract si está disponible en PATH o en rutas comunes."""
    custom_cmd = os.environ.get("TESSERACT_CMD")
    if custom_cmd and os.path.exists(custom_cmd):
        pytesseract.pytesseract.tesseract_cmd = custom_cmd
        return True

    path_cmd = shutil.which("tesseract")
    if path_cmd:
        pytesseract.pytesseract.tesseract_cmd = path_cmd
        return True

    windows_candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.join(os.path.expanduser("~"), r"AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for candidate in windows_candidates:
        if os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            return True

    return False


def tesseract_help_message() -> str:
    return (
        "No se encontró Tesseract OCR instalado.\n\n"
        "1) Instalalo desde: https://github.com/UB-Mannheim/tesseract/wiki\n"
        "2) Reiniciá la app.\n"
        "3) Si sigue fallando, agregá tesseract.exe al PATH o definí la variable TESSERACT_CMD.\n\n"
        "Ruta típica en Windows:\n"
        "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
    )


# ══════════════════════════════════════════════
# LÓGICA PRINCIPAL
# ══════════════════════════════════════════════

class MusicVideoProcessor:
    """Toda la lógica de procesamiento."""

    VIDEO_W = 1920
    VIDEO_H = 1080

    def __init__(self, progress_callback=None, log_callback=None):
        self.progress = progress_callback or (lambda v, t: None)
        self.log = log_callback or print

    def _apply_fps(self, clip, fps: int):
        if hasattr(clip, "with_fps"):
            return clip.with_fps(fps)
        if hasattr(clip, "set_fps"):
            return clip.set_fps(fps)
        setattr(clip, "fps", fps)
        return clip

    def _apply_audio(self, clip, audio_clip):
        if hasattr(clip, "with_audio"):
            return clip.with_audio(audio_clip)
        if hasattr(clip, "set_audio"):
            return clip.set_audio(audio_clip)
        setattr(clip, "audio", audio_clip)
        return clip

    # ── OCR ──────────────────────────────────
    def extract_text_from_image(self, image_path: str) -> str:
        self.log(f"🔍 Extrayendo texto de: {os.path.basename(image_path)}")
        if not configure_tesseract():
            raise RuntimeError(tesseract_help_message())

        img = Image.open(image_path)
        # Preprocesado para mejorar OCR
        img_gray = img.convert("L")
        img_sharp = img_gray.filter(ImageFilter.SHARPEN)
        try:
            text = pytesseract.image_to_string(img_sharp, lang="spa+eng")
        except pytesseract.TesseractNotFoundError as exc:
            raise RuntimeError(tesseract_help_message()) from exc
        return text.strip()

    # ── Descripción para YouTube ──────────────
    def generate_description(self, text1: str, text2: str) -> dict:
        """Parsea OCR y genera título Full Album + descripción + hashtags."""
        combined = f"{text1}\n\n{text2}"
        lines = [l.strip() for l in combined.splitlines() if l.strip()]

        album = "Álbum"
        artist = "Artista"

        cleaned = []
        for line in lines:
            normalized = " ".join(line.replace("|", " ").split())
            if normalized:
                cleaned.append(normalized)

        for index, line in enumerate(cleaned[:12]):
            upper = line.upper()
            if "RETRATO DE" in upper or "ALBUM" in upper or "ÁLBUM" in upper:
                album = line.title()
                if index + 1 < len(cleaned):
                    candidate_artist = cleaned[index + 1]
                    if len(candidate_artist.split()) >= 2 and not candidate_artist[:1].isdigit():
                        artist = candidate_artist.title()
                break

        if album == "Álbum":
            for line in cleaned:
                if line[:1].isdigit():
                    continue
                if len(line.split()) >= 2:
                    album = line.title()
                    break

        if artist == "Artista":
            for line in cleaned:
                if line[:1].isdigit():
                    continue
                if len(line.split()) >= 2 and line.title() != album:
                    artist = line.title()
                    break

        title_line = f"Full Album - {album} - {artist}"[:100]
        
        # Hashtags automáticos desde palabras clave del texto
        keywords = set()
        for line in lines:
            for word in line.split():
                word_clean = word.strip(".,;:!?\"'()[]").lower()
                if len(word_clean) > 4:
                    keywords.add(word_clean)
        
        # Hashtags de música siempre presentes
        base_tags = ["#music", "#músicaindependiente", "#newmusic", "#indiemusic", "#músicaargentina"]
        custom_tags = [f"#{w}" for w in list(keywords)[:10] if w.isalpha()]
        all_tags = base_tags + custom_tags

        description = f"""🎵 {title_line}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 TRACKLIST / INFORMACIÓN:

{combined}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✨ Si disfrutás la música, dejá tu like y suscribite para más contenido.
🔔 Activá la campanita para no perderte ningún lanzamiento.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{chr(10).join(all_tags)}
"""
        return {
            "title": title_line[:100],  # YouTube max 100 chars
            "description": description,
            "tags": [t.lstrip("#") for t in all_tags]
        }

    def save_metadata_file(self, output_path: str, metadata: dict) -> str:
        metadata_path = os.path.splitext(output_path)[0] + "_metadata.txt"
        hashtags_line = " ".join(f"#{tag}" for tag in metadata.get("tags", []))
        content = (
            "TITULO:\n"
            f"{metadata.get('title', '')}\n\n"
            "DESCRIPCION:\n"
            f"{metadata.get('description', '')}\n\n"
            "HASHTAGS:\n"
            f"{hashtags_line}\n"
        )
        with open(metadata_path, "w", encoding="utf-8") as file:
            file.write(content)
        self.log(f"📝 Metadata guardada: {metadata_path}")
        return metadata_path

    def improve_metadata_with_ai(self, metadata: dict) -> dict:
        """Corrige ortografía/estilo usando IA online (API compatible con OpenAI)."""
        api_key = os.environ.get("AI_API_KEY", "").strip()
        if not api_key:
            self.log("ℹ️ IA: AI_API_KEY no configurada. Se mantiene metadata original.")
            return metadata

        api_base = os.environ.get("AI_API_BASE", "https://api.openai.com/v1").rstrip("/")
        model = os.environ.get("AI_MODEL", "gpt-4o-mini")
        endpoint = f"{api_base}/chat/completions"

        prompt = {
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "tags": metadata.get("tags", []),
        }

        payload = {
            "model": model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Corregí ortografía y puntuación en español sin cambiar el sentido. "
                        "Mantené el formato del título: Full Album - <Álbum> - <Artista>. "
                        "No inventes datos. Devolvé SOLO JSON con claves: title, description, tags."
                    )
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt, ensure_ascii=False)
                }
            ]
        }

        request_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=request_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                raw = response.read().decode("utf-8", errors="ignore")
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
            fixed = json.loads(content) if isinstance(content, str) else content

            title = str(fixed.get("title", metadata.get("title", ""))).strip()[:100]
            description = str(fixed.get("description", metadata.get("description", ""))).strip()
            tags_in = fixed.get("tags", metadata.get("tags", []))
            if not isinstance(tags_in, list):
                tags_in = metadata.get("tags", [])

            tags = []
            for tag in tags_in:
                normalized = str(tag).replace("#", "").strip().lower()
                if normalized and normalized not in tags:
                    tags.append(normalized)

            if not title.startswith("Full Album -"):
                title = metadata.get("title", title)

            self.log("✨ Metadata corregida con IA.")
            return {
                "title": title,
                "description": description,
                "tags": tags or metadata.get("tags", [])
            }
        except Exception as exc:
            self.log(f"⚠️ IA no disponible ({exc}). Se usa metadata original.")
            return metadata

    # ── Preparar frame de imagen ──────────────
    def _prepare_half_frame(self, image_path: str, side: str) -> np.ndarray:
        """Redimensiona imagen para ocupar mitad del frame 1920x1080."""
        half_w = self.VIDEO_W // 2  # 960
        img = Image.open(image_path).convert("RGB")
        img = img.resize((half_w, self.VIDEO_H), Image.LANCZOS)
        return np.array(img)

    # ── Generar video ─────────────────────────
    def create_video(self, wav_path: str, img1_path: str, img2_path: str, output_path: str) -> str:
        self.log("🎬 Creando video...")
        self.progress(30, "Preparando imágenes...")

        left_frame = self._prepare_half_frame(img1_path, "left")
        right_frame = self._prepare_half_frame(img2_path, "right")

        # Combinar lado a lado
        combined = np.concatenate([left_frame, right_frame], axis=1)  # (1080, 1920, 3)

        self.progress(40, "Cargando audio...")
        audio = AudioFileClip(wav_path)
        duration = audio.duration
        self.log(f"⏱️ Duración del audio: {duration:.1f}s")

        self.progress(50, "Generando clip de video...")
        video_clip = ImageClip(combined, duration=duration)
        video_clip = self._apply_fps(video_clip, 24)
        video_clip = self._apply_audio(video_clip, audio)

        self.progress(60, "Exportando video (puede tardar unos minutos)...")
        video_clip.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            preset="fast",
            logger=None
        )
        video_clip.close()
        audio.close()
        self.log(f"✅ Video guardado: {output_path}")
        return output_path

# ══════════════════════════════════════════════
# INTERFAZ GRÁFICA
# ══════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🎵 Full Album Video Generator")
        self.geometry("780x700")
        self.resizable(False, False)
        self.configure(bg="#1a1a2e")

        self.wav_path = tk.StringVar()
        self.img1_path = tk.StringVar()
        self.img2_path = tk.StringVar()
        self.output_path = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "output_video.mp4"))
        self.last_metadata_path = ""

        self._build_ui()

    # ── UI ───────────────────────────────────
    def _build_ui(self):
        DARK = "#1a1a2e"
        CARD = "#16213e"
        ACCENT = "#e94560"
        TEXT = "#eaeaea"
        MUTED = "#a0a0b0"
        BTN_BG = "#0f3460"
        READY_BG = ACCENT
        DISABLED_BG = CARD

        style = ttk.Style(self)
        style.theme_use("clam")
        self.last_metadata = None
        style.configure("TProgressbar", troughcolor=CARD, background=ACCENT, thickness=18)

        # ── Header ──
        header = tk.Frame(self, bg=ACCENT, height=60)
        header.pack(fill="x")
        tk.Label(header, text="🎵  Full Album Video Generator",
                 font=("Segoe UI", 16, "bold"), bg=ACCENT, fg="white").pack(pady=15)

        main = tk.Frame(self, bg=DARK, padx=20, pady=10)
        main.pack(fill="both", expand=True)

        def section_label(parent, text):
            tk.Label(parent, text=text, font=("Segoe UI", 10, "bold"),
                     bg=DARK, fg=ACCENT).pack(anchor="w", pady=(12, 2))

        def file_row(parent, label, var, filetypes, is_save=False):
            row = tk.Frame(parent, bg=DARK)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, width=14, anchor="w",
                     font=("Segoe UI", 9), bg=DARK, fg=TEXT).pack(side="left")
            entry = tk.Entry(row, textvariable=var, width=46,
                             bg=CARD, fg=TEXT, insertbackground=TEXT,
                             relief="flat", font=("Segoe UI", 9))
            entry.pack(side="left", padx=(0, 6))
            cmd = (lambda v=var, ft=filetypes: self._save_file(v, ft)) if is_save \
                  else (lambda v=var, ft=filetypes: self._open_file(v, ft))
            tk.Button(row, text="📂 Elegir", command=cmd,
                      bg=BTN_BG, fg=TEXT, relief="flat",
                      font=("Segoe UI", 9), padx=8, cursor="hand2").pack(side="left")

        # Archivos de entrada
        section_label(main, "📁  Archivos de entrada")
        file_row(main, "Audio (.wav):", self.wav_path,
                 [("WAV files", "*.wav"), ("All", "*.*")])
        file_row(main, "Foto 1 (izq):", self.img1_path,
                 [("Images", "*.png *.jpg *.jpeg *.bmp *.tiff"), ("All", "*.*")])
        file_row(main, "Foto 2 (der):", self.img2_path,
                 [("Images", "*.png *.jpg *.jpeg *.bmp *.tiff"), ("All", "*.*")])

        # Salida
        section_label(main, "💾  Video de salida")
        file_row(main, "Guardar como:", self.output_path,
                 [("MP4 video", "*.mp4")], is_save=True)

        info_frame = tk.Frame(main, bg="#0f3460", pady=8, padx=12)
        info_frame.pack(fill="x", pady=(14, 2))
        tk.Label(info_frame,
                 text="ℹ️  La app genera video + metadata para subir manualmente a YouTube.\n"
                      "   Se crea un archivo *_metadata.txt con título, descripción y hashtags.",
                 font=("Consolas", 8), bg="#0f3460", fg="#90caf9",
                 justify="left").pack(anchor="w")

        # Barra de progreso
        section_label(main, "⚙️  Progreso")
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main, variable=self.progress_var,
                                             maximum=100, length=720)
        self.progress_bar.pack(fill="x")
        self.status_label = tk.Label(main, text="Listo para comenzar.",
                                      font=("Segoe UI", 9), bg=DARK, fg=MUTED)
        self.status_label.pack(anchor="w", pady=(2, 0))

        # Log
        section_label(main, "📋  Log")
        self.log_box = scrolledtext.ScrolledText(main, height=10, width=88,
                                                  bg=CARD, fg="#90ee90",
                                                  font=("Consolas", 8),
                                                  insertbackground=TEXT,
                                                  relief="flat")
        self.log_box.pack(fill="x")

        # Botones de acción
        btn_frame = tk.Frame(main, bg=DARK)
        btn_frame.pack(pady=12)

        self.btn_only_video = tk.Button(btn_frame, text="🎬  Solo generar video",
                                         command=self._start,
                                         bg=BTN_BG, fg=TEXT, relief="flat",
                                         font=("Segoe UI", 10, "bold"),
                                         padx=16, pady=8, cursor="hand2")
        self.btn_only_video.pack(side="left", padx=8)

        self.btn_copy_title = tk.Button(btn_frame, text="📋 Copiar título",
                        command=self._copy_title,
                        bg=BTN_BG, fg=TEXT, relief="flat",
                        font=("Segoe UI", 10, "bold"),
                        padx=16, pady=8, cursor="hand2",
                        state="disabled")
        self.btn_copy_title.pack(side="left", padx=8)

        self.btn_copy_description = tk.Button(btn_frame, text="📋 Copiar descripción",
                              command=self._copy_description,
                              bg=BTN_BG, fg=TEXT, relief="flat",
                              font=("Segoe UI", 10, "bold"),
                              padx=16, pady=8, cursor="hand2",
                              state="disabled")
        self.btn_copy_description.pack(side="left", padx=8)

        self.copy_btn_default_bg = BTN_BG
        self.copy_btn_ready_bg = READY_BG
        self.copy_btn_disabled_bg = DISABLED_BG
        self.copy_btn_text = TEXT
        self.copy_btn_muted = MUTED

    # ── Helpers ──────────────────────────────
    def _open_file(self, var, filetypes):
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            var.set(path)

    def _save_file(self, var, filetypes):
        path = filedialog.asksaveasfilename(filetypes=filetypes, defaultextension=".mp4")
        if path:
            var.set(path)

    def _log(self, msg):
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.update_idletasks()


    def _copy_title(self):
        title_to_copy = ""

        if self.last_metadata_path and os.path.exists(self.last_metadata_path):
            try:
                with open(self.last_metadata_path, "r", encoding="utf-8") as file:
                    lines = [line.rstrip("\n") for line in file]
                for index, line in enumerate(lines):
                    if line.strip().upper() == "TITULO:":
                        if index + 1 < len(lines):
                            title_to_copy = lines[index + 1].strip()
                        break
            except Exception:
                title_to_copy = ""

        if not title_to_copy and self.last_metadata:
            title_to_copy = self.last_metadata.get("title", "").strip()

        if not title_to_copy:
            messagebox.showwarning("Sin metadata", "Primero generá el video y la metadata.")
            return

        self.clipboard_clear()
        self.clipboard_append(title_to_copy)
        messagebox.showinfo("Copiado", "Título copiado al portapapeles.")

    def _copy_description(self):
        if not self.last_metadata:
            messagebox.showwarning("Sin metadata", "Primero generá el video y la metadata.")
            return
        self.clipboard_clear()
        self.clipboard_append(self.last_metadata.get("description", ""))
        messagebox.showinfo("Copiado", "Descripción copiada al portapapeles.")

    def _set_metadata_buttons(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.btn_copy_title.config(state=state)
        self.btn_copy_description.config(state=state)
        if enabled:
            self.btn_copy_title.config(
                bg=self.copy_btn_ready_bg,
                activebackground=self.copy_btn_ready_bg,
                fg="white",
                text="✅ Copiar título"
            )
            self.btn_copy_description.config(
                bg=self.copy_btn_ready_bg,
                activebackground=self.copy_btn_ready_bg,
                fg="white",
                text="✅ Copiar descripción"
            )
        else:
            self.btn_copy_title.config(
                bg=self.copy_btn_disabled_bg,
                activebackground=self.copy_btn_default_bg,
                fg=self.copy_btn_muted,
                text="📋 Copiar título"
            )
            self.btn_copy_description.config(
                bg=self.copy_btn_disabled_bg,
                activebackground=self.copy_btn_default_bg,
                fg=self.copy_btn_muted,
                text="📋 Copiar descripción"
            )
    def _set_progress(self, value, text=""):
        self.progress_var.set(value)
        if text:
            self.status_label.config(text=text)
        self.update_idletasks()

    def _set_buttons(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.btn_only_video.config(state=state)

    # ── Validación ───────────────────────────
    def _validate(self) -> bool:
        if not self.wav_path.get() or not os.path.exists(self.wav_path.get()):
            messagebox.showerror("Error", "Seleccioná un archivo WAV válido.")
            return False
        if not self.img1_path.get() or not os.path.exists(self.img1_path.get()):
            messagebox.showerror("Error", "Seleccioná la Foto 1.")
            return False
        if not self.img2_path.get() or not os.path.exists(self.img2_path.get()):
            messagebox.showerror("Error", "Seleccioná la Foto 2.")
            return False
        if not self.output_path.get():
            messagebox.showerror("Error", "Indicá dónde guardar el video.")
            return False
        if not configure_tesseract():
            messagebox.showerror("Tesseract no encontrado", tesseract_help_message())
            return False
        return True

    # ── Proceso principal ─────────────────────
    def _start(self):
        if not self._validate():
            return

        self.last_metadata = None
        self.last_metadata_path = ""
        self._set_metadata_buttons(False)
        self._set_buttons(False)
        self._set_progress(0, "Iniciando...")
        self.log_box.delete("1.0", "end")
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        processor = MusicVideoProcessor(
            progress_callback=self._set_progress,
            log_callback=self._log
        )
        try:
            self._log(f"ℹ️ MoviePy detectado: {getattr(moviepy_module, '__version__', 'desconocido')}")

            # 1. OCR
            self._set_progress(10, "Leyendo texto de fotos (OCR)...")
            self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self._log("PASO 1: OCR en imágenes")
            text1 = processor.extract_text_from_image(self.img1_path.get())
            text2 = processor.extract_text_from_image(self.img2_path.get())
            self._log(f"📖 Texto foto 1:\n{text1[:300]}{'...' if len(text1)>300 else ''}")
            self._log(f"📖 Texto foto 2:\n{text2[:300]}{'...' if len(text2)>300 else ''}")
            self._set_progress(20, "OCR completado. Generando descripción...")

            # 2. Metadata
            self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self._log("PASO 2: Generando metadata")
            metadata = processor.generate_description(text1, text2)

            self._log("PASO 2.5: Corrigiendo metadata con IA...")
            metadata = processor.improve_metadata_with_ai(metadata)

            self._log(f"📌 Título: {metadata['title']}")
            self._log(f"🏷️  Tags: {', '.join(metadata['tags'][:8])}")
            self._set_progress(25, "Metadata lista.")

            # 3. Video
            self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self._log("PASO 3: Generando video")
            processor.create_video(
                self.wav_path.get(),
                self.img1_path.get(),
                self.img2_path.get(),
                self.output_path.get()
            )

            self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self._log("PASO 4: Guardando metadata")
            metadata_path = processor.save_metadata_file(self.output_path.get(), metadata)
            self.last_metadata = metadata
            self.last_metadata_path = metadata_path
            self._set_metadata_buttons(True)
            self._set_progress(100, "✅ Video y metadata generados correctamente.")
            self._log("✅ Proceso completado. Listo para subir manualmente.")

            messagebox.showinfo(
                "¡Éxito!",
                "Video y metadata generados correctamente 🎬\n\n"
                f"Video: {self.output_path.get()}\n"
                f"Metadata: {metadata_path}"
            )

        except Exception as e:
            self._log(f"\n❌ ERROR: {e}")
            messagebox.showerror("Error", str(e))
            self._set_progress(0, "Error.")
        finally:
            self._set_buttons(True)


# ══════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════

if __name__ == "__main__":
    app = App()
    app.mainloop()
