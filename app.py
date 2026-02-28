#!/usr/bin/env python3
"""
YouTube Music Video Uploader
Genera un video desde 2 fotos + 1 audio WAV, hace OCR del texto en las fotos,
genera descripción y sube automáticamente a YouTube usando Chrome logueado.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
import sys
import subprocess
import time

# ──────────────────────────────────────────────
# Instalación automática de dependencias
# ──────────────────────────────────────────────
REQUIRED_PACKAGES = [
    ("Pillow", "PIL"),
    ("pytesseract", "pytesseract"),
    ("moviepy", "moviepy"),
    ("selenium", "selenium"),
    ("webdriver_manager", "webdriver_manager"),
    ("numpy", "numpy"),
    ("opencv-python", "cv2"),
]

def install_if_missing():
    import importlib
    missing = []
    for pkg_name, import_name in REQUIRED_PACKAGES:
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing.append(pkg_name)
    if missing:
        print(f"Instalando paquetes faltantes: {missing}")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing, 
                              stdout=subprocess.DEVNULL)

install_if_missing()

# ──────────────────────────────────────────────
# Imports post-instalación
# ──────────────────────────────────────────────
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import pytesseract
import numpy as np

# moviepy
try:
    from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips
except ImportError:
    from moviepy import ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import cv2


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

    # ── OCR ──────────────────────────────────
    def extract_text_from_image(self, image_path: str) -> str:
        self.log(f"🔍 Extrayendo texto de: {os.path.basename(image_path)}")
        img = Image.open(image_path)
        # Preprocesado para mejorar OCR
        img_gray = img.convert("L")
        img_sharp = img_gray.filter(ImageFilter.SHARPEN)
        text = pytesseract.image_to_string(img_sharp, lang="spa+eng")
        return text.strip()

    # ── Descripción para YouTube ──────────────
    def generate_description(self, text1: str, text2: str) -> dict:
        """Parsea el texto OCR y genera título + descripción + hashtags."""
        combined = f"{text1}\n\n{text2}"
        lines = [l.strip() for l in combined.splitlines() if l.strip()]

        # Intenta extraer info común de tracklists
        title_line = lines[0] if lines else "Música"
        
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
        video_clip = video_clip.set_fps(24)
        video_clip = video_clip.set_audio(audio)

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

    # ── Subir a YouTube via Selenium ──────────
    def upload_to_youtube(self, video_path: str, metadata: dict):
        self.log("🌐 Conectando con Chrome...")
        self.progress(75, "Conectando con Chrome...")

        # Conectar al Chrome ya abierto (debug port)
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        
        try:
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
        except Exception as e:
            self.log(f"⚠️ No se pudo conectar al Chrome existente: {e}")
            self.log("Abriendo nuevo Chrome...")
            chrome_options = Options()
            chrome_options.add_argument("--start-maximized")
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )

        wait = WebDriverWait(driver, 30)

        try:
            self.log("📤 Navegando a YouTube Studio...")
            self.progress(78, "Abriendo YouTube Studio...")
            driver.get("https://studio.youtube.com")
            time.sleep(3)

            # Click en "Crear" > "Subir videos"
            self.log("🖱️ Buscando botón de subida...")
            self.progress(80, "Iniciando subida...")

            # Botón CREATE
            create_btn = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "#create-icon, ytcp-button#create-icon, [test-id='create-icon']")
            ))
            create_btn.click()
            time.sleep(1)

            # Opción "Subir video"
            upload_option = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//*[contains(text(),'Subir') or contains(text(),'Upload')]")
            ))
            upload_option.click()
            time.sleep(2)

            # Input de archivo
            file_input = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='file']")
            ))
            file_input.send_keys(os.path.abspath(video_path))
            self.log("📁 Archivo enviado, esperando procesamiento...")
            self.progress(83, "Subiendo archivo...")
            time.sleep(5)

            # Título
            self.log("✏️ Completando título...")
            title_field = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#title-textarea #textbox, ytcp-social-suggestion-input #textbox")
            ))
            title_field.clear()
            title_field.send_keys(Keys.CONTROL + "a")
            title_field.send_keys(metadata["title"])
            self.progress(86, "Completando título...")

            # Descripción
            self.log("📝 Completando descripción...")
            desc_field = driver.find_element(
                By.CSS_SELECTOR, "#description-textarea #textbox"
            )
            desc_field.click()
            desc_field.send_keys(Keys.CONTROL + "a")
            desc_field.send_keys(metadata["description"])
            self.progress(89, "Completando descripción...")
            time.sleep(1)

            # No es para niños
            try:
                not_for_kids = driver.find_element(
                    By.CSS_SELECTOR, "#radioLabel [name='made_for_kids'] + label, #not-made-for-kids"
                )
                not_for_kids.click()
            except:
                pass

            # Siguiente x3
            for i in range(3):
                self.log(f"➡️ Paso {i+2}/4...")
                self.progress(90 + i, f"Paso {i+2} de 4...")
                next_btn = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "#next-button, ytcp-button#next-button")
                ))
                next_btn.click()
                time.sleep(2)

            # Público
            self.log("🌍 Configurando visibilidad: Público...")
            public_radio = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//*[@name='PUBLIC' or @value='PUBLIC']//ancestor::ytcp-paper-radio-button | //*[contains(@class,'public')][@role='radio']")
            ))
            public_radio.click()
            time.sleep(1)

            # Publicar
            self.log("🚀 Publicando video...")
            self.progress(97, "Publicando...")
            publish_btn = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "#done-button, ytcp-button#done-button")
            ))
            publish_btn.click()
            time.sleep(5)

            self.log("🎉 ¡Video subido exitosamente a YouTube!")
            self.progress(100, "¡Listo!")

        except Exception as e:
            self.log(f"❌ Error en Selenium: {e}")
            self.log("💡 Tip: Asegurate de que Chrome esté abierto con --remote-debugging-port=9222")
            raise
        finally:
            # No cerramos Chrome para no cerrar la sesión del usuario
            pass


# ══════════════════════════════════════════════
# INTERFAZ GRÁFICA
# ══════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🎵 YouTube Music Video Uploader")
        self.geometry("780x700")
        self.resizable(False, False)
        self.configure(bg="#1a1a2e")

        self.wav_path = tk.StringVar()
        self.img1_path = tk.StringVar()
        self.img2_path = tk.StringVar()
        self.output_path = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "output_video.mp4"))

        self._build_ui()

    # ── UI ───────────────────────────────────
    def _build_ui(self):
        DARK = "#1a1a2e"
        CARD = "#16213e"
        ACCENT = "#e94560"
        TEXT = "#eaeaea"
        MUTED = "#a0a0b0"
        BTN_BG = "#0f3460"

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TProgressbar", troughcolor=CARD, background=ACCENT, thickness=18)

        # ── Header ──
        header = tk.Frame(self, bg=ACCENT, height=60)
        header.pack(fill="x")
        tk.Label(header, text="🎵  YouTube Music Video Uploader",
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

        # Info Chrome
        info_frame = tk.Frame(main, bg="#0f3460", pady=8, padx=12)
        info_frame.pack(fill="x", pady=(14, 2))
        tk.Label(info_frame,
                 text="ℹ️  Para subir automáticamente, iniciá Chrome con depuración remota:\n"
                      "   chrome.exe --remote-debugging-port=9222",
                 font=("Consolas", 8), bg="#0f3460", fg="#90caf9",
                 justify="left").pack(anchor="w")
        tk.Button(info_frame, text="📋 Copiar comando",
                  command=self._copy_chrome_cmd,
                  bg=BTN_BG, fg=TEXT, relief="flat", font=("Segoe UI", 8),
                  padx=6, cursor="hand2").pack(anchor="e")

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
                                         command=lambda: self._start(upload=False),
                                         bg=BTN_BG, fg=TEXT, relief="flat",
                                         font=("Segoe UI", 10, "bold"),
                                         padx=16, pady=8, cursor="hand2")
        self.btn_only_video.pack(side="left", padx=8)

        self.btn_full = tk.Button(btn_frame, text="🚀  Generar y subir a YouTube",
                                   command=lambda: self._start(upload=True),
                                   bg=ACCENT, fg="white", relief="flat",
                                   font=("Segoe UI", 10, "bold"),
                                   padx=16, pady=8, cursor="hand2")
        self.btn_full.pack(side="left", padx=8)

    # ── Helpers ──────────────────────────────
    def _open_file(self, var, filetypes):
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            var.set(path)

    def _save_file(self, var, filetypes):
        path = filedialog.asksaveasfilename(filetypes=filetypes, defaultextension=".mp4")
        if path:
            var.set(path)

    def _copy_chrome_cmd(self):
        cmd = 'chrome.exe --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\\ChromeDebug"'
        self.clipboard_clear()
        self.clipboard_append(cmd)
        messagebox.showinfo("Copiado", "Comando copiado al portapapeles.\n\nEjecutalo en PowerShell o CMD antes de continuar.")

    def _log(self, msg):
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.update_idletasks()

    def _set_progress(self, value, text=""):
        self.progress_var.set(value)
        if text:
            self.status_label.config(text=text)
        self.update_idletasks()

    def _set_buttons(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.btn_only_video.config(state=state)
        self.btn_full.config(state=state)

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
        return True

    # ── Proceso principal ─────────────────────
    def _start(self, upload: bool):
        if not self._validate():
            return
        self._set_buttons(False)
        self._set_progress(0, "Iniciando...")
        self.log_box.delete("1.0", "end")
        thread = threading.Thread(target=self._run, args=(upload,), daemon=True)
        thread.start()

    def _run(self, upload: bool):
        processor = MusicVideoProcessor(
            progress_callback=self._set_progress,
            log_callback=self._log
        )
        try:
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

            # 4. Upload
            if upload:
                self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                self._log("PASO 4: Subiendo a YouTube")
                processor.upload_to_youtube(self.output_path.get(), metadata)
            else:
                self._set_progress(100, "✅ Video generado correctamente.")
                self._log("✅ Video generado. No se subió a YouTube.")

            messagebox.showinfo(
                "¡Éxito!",
                f"{'Video generado y subido a YouTube 🎉' if upload else 'Video generado correctamente 🎬'}\n\n"
                f"Archivo: {self.output_path.get()}"
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
