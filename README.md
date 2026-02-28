# 🎵 Full Album Video Generator

App de escritorio (Tkinter) para crear un video Full HD con:
- 1 audio `.wav`
- 2 imágenes (izquierda y derecha)
- OCR automático con Tesseract
- metadata para YouTube (`*_metadata.txt`)

La subida a YouTube se hace manualmente, usando el título y descripción generados.

---

## ✅ Qué hace

- Genera video `1920x1080` (mitad izquierda + mitad derecha)
- Duración del video = duración del audio WAV
- Extrae texto de ambas imágenes con OCR (`spa+eng`)
- Crea título: `Full Album - <Álbum> - <Artista>`
- Genera descripción + hashtags automáticos
- Guarda metadata en `nombre_video_metadata.txt`
- Permite copiar título y descripción al portapapeles desde la UI
- Mejora opcional con IA (corrección ortográfica/estilo)

---

## 📋 Requisitos

### 1) Python 3.9+
Descargar desde https://python.org

### 2) Tesseract OCR
- **Windows**: https://github.com/UB-Mannheim/tesseract/wiki
- **Linux**: `sudo apt install tesseract-ocr tesseract-ocr-spa`
- **macOS**: `brew install tesseract`

La app intenta encontrar Tesseract en:
- variable `TESSERACT_CMD`
- `PATH`
- rutas típicas de Windows

### 3) FFmpeg
- **Windows**: https://ffmpeg.org/download.html (agregar al `PATH`)
- **Linux**: `sudo apt install ffmpeg`
- **macOS**: `brew install ffmpeg`

---

## 🚀 Instalación y ejecución

```bash
pip install -r requirements.txt
python app.py
```

> Nota: la app también intenta instalar paquetes faltantes automáticamente al iniciar.

---

## 🎬 Uso

1. Ejecutar `python app.py`
2. Elegir:
   - Audio `.wav`
   - Foto 1 (izquierda)
   - Foto 2 (derecha)
3. Elegir dónde guardar el `.mp4`
4. Click en **Solo generar video**

Resultado:
- `video.mp4`
- `video_metadata.txt` (título, descripción, hashtags)

Luego podés usar los botones:
- **Copiar título**
- **Copiar descripción**

---

## 🤖 Mejora de metadata con IA (opcional)

Si configurás variables de entorno, la app corrige ortografía y estilo de la metadata usando una API compatible con OpenAI.

Variables:
- `AI_API_KEY` (obligatoria para usar IA)
- `AI_API_BASE` (opcional, por defecto `https://api.openai.com/v1`)
- `AI_MODEL` (opcional, por defecto `gpt-4o-mini`)

Si no están configuradas, la app usa metadata local sin IA.

---

## 🧩 Dependencias Python

- `Pillow`
- `pytesseract`
- `moviepy`
- `numpy`
- `opencv-python`

---

## ❓ Problemas comunes

| Problema | Solución |
|---|---|
| `Tesseract no encontrado` | Instalá Tesseract y/o definí `TESSERACT_CMD` |
| `ffmpeg not found` | Instalá FFmpeg y agregalo al `PATH` |
| Error al exportar video | Verificá que el `.wav` y las imágenes sean válidos |
| IA no disponible | Revisá `AI_API_KEY`, `AI_API_BASE` y conexión |
