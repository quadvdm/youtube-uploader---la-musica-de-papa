# 🎵 YouTube Music Video Uploader

Genera un video para YouTube a partir de 2 fotos y 1 archivo WAV,
lee el texto de las fotos con OCR y sube automáticamente al canal
que esté logueado en Chrome.

---

## 📋 Requisitos previos

### 1. Python 3.9+
Descargá desde https://python.org

### 2. Tesseract OCR
- **Windows**: https://github.com/UB-Mannheim/tesseract/wiki  
  Instalá y asegurate de que esté en el PATH, o agregá esta línea al inicio de `app.py`:
  ```python
  pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
  ```
- **Linux**: `sudo apt install tesseract-ocr tesseract-ocr-spa`
- **macOS**: `brew install tesseract`

### 3. FFmpeg
- **Windows**: https://ffmpeg.org/download.html  → agregar al PATH
- **Linux**: `sudo apt install ffmpeg`
- **macOS**: `brew install ffmpeg`

### 4. Google Chrome (actualizado)

---

## 🚀 Instalación

```bash
# 1. Instalá dependencias Python
pip install -r requirements.txt

# 2. Ejecutá la app
python app.py
```

La app instala automáticamente los paquetes faltantes al iniciar.

---

## 🌐 Cómo configurar Chrome para la subida automática

La app necesita conectarse al Chrome donde ya estás logueado en YouTube.

**Paso 1:** Cerrá Chrome completamente.

**Paso 2:** Abrí Chrome con el puerto de depuración activo:

```
# Windows (PowerShell o CMD)
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\ChromeDebug"

# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="$HOME/ChromeDebug"

# Linux
google-chrome --remote-debugging-port=9222 --user-data-dir="$HOME/ChromeDebug"
```

> ⚠️ La primera vez abrirá un perfil nuevo. Iniciá sesión en YouTube/Google en ese perfil.

**Paso 3:** Dejá Chrome abierto y ejecutá la app.

---

## 🎬 Uso

1. **Abrí la app**: `python app.py`
2. **Seleccioná** el archivo WAV, la Foto 1 y la Foto 2
3. **Elegí** dónde guardar el video de salida (MP4)
4. Hacé click en:
   - **"Solo generar video"** → crea el MP4 sin subir
   - **"Generar y subir a YouTube"** → crea el MP4 y lo sube automáticamente

---

## 📐 Formato del video generado

- Resolución: **1920 × 1080** (Full HD, ideal para YouTube)
- Foto 1 ocupa la **mitad izquierda** (960×1080)
- Foto 2 ocupa la **mitad derecha** (960×1080)
- Duración: la del archivo WAV
- Codec: H.264 + AAC

---

## 🔍 OCR y descripción automática

La app lee el texto de ambas fotos con Tesseract OCR y genera:
- **Título** (primeras palabras del texto detectado)
- **Descripción** con el tracklist/info completa
- **Hashtags** automáticos basados en el contenido

---

## ❓ Problemas comunes

| Problema | Solución |
|----------|----------|
| `tesseract not found` | Instalá Tesseract y agregalo al PATH |
| `ffmpeg not found` | Instalá FFmpeg y agregalo al PATH |
| Error de conexión Chrome | Seguí los pasos de "Configurar Chrome" arriba |
| Video sin audio | Asegurate que el WAV no esté corrupto |
