# YouTube Vault — Local YouTube Research, Transcription & Archive Toolkit

**YouTube Vault** es una herramienta local y de código abierto para organizar metadatos, transcripciones, comentarios y análisis de vídeos de YouTube a los que tengas acceso legítimo. Está pensada para creadores, investigadores, documentalistas y personas que quieren conservar y estudiar su propio contenido de forma ordenada, reproducible y responsable.

> Este es mi primer proyecto público. Estoy aprendiendo en abierto y utilizando herramientas de IA como apoyo para diseñar, programar y mejorar el proyecto. Las contribuciones, ideas, correcciones y revisiones son bienvenidas.

## ¿Por qué contribuir?

El objetivo es construir una alternativa local, clara y práctica para investigación y archivado autorizado. Hay mucho espacio para mejorar: precisión de transcripción, accesibilidad, calidad de los reportes, pruebas automatizadas, traducciones, documentación y experiencia de usuario. Si te interesa Python, análisis de datos, UX, IA local o preservación digital, tu ayuda puede tener un impacto real.

- Interfaz web local y GUI de escritorio.
- Transcripción con faster-whisper, subtítulos como respaldo y marcas de tiempo.
- Metadatos, comentarios, análisis de sentimiento y reportes HTML/CSV/JSON.
- `manifest.json` con hashes SHA-256 para trazabilidad y archivado reproducible.
- Configuración local protegida y resultados excluidos de Git por defecto.

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para proponer mejoras de forma segura y ordenada.

## Uso responsable y límites

Este proyecto se publica con fines educativos, de investigación y de archivo autorizado. No descarga ni concede derechos sobre contenido de terceros.

- Procesa únicamente contenido propio, con autorización expresa o que puedas usar legalmente.
- Respeta los [Términos de Servicio de YouTube](https://www.youtube.com/t/terms), los derechos de autor, la privacidad y la legislación aplicable.
- No uses esta herramienta para evadir controles de acceso, CAPTCHA, restricciones geográficas, límites de servicio u otras medidas de una plataforma.
- Los comentarios, transcripciones, miniaturas, vídeos y audios pueden contener datos personales o material protegido. No publiques los resultados sin una revisión legal y de privacidad.
- El software se ofrece tal cual, sin garantías. Consulta [LICENSE](LICENSE).

Los avisos anteriores no son asesoría legal ni sustituyen una evaluación de derechos, permisos o privacidad. Tú eres responsable de verificar que el uso concreto sea legal y esté autorizado en tu jurisdicción.

## Requisitos

- Python 3.10 o superior.
- `ffmpeg` disponible en `PATH` para combinar medios y generar determinados artefactos.
- Dependencias Python listadas en `requirements.txt`.

## Instalación

```powershell
git clone https://github.com/TU_USUARIO/youtube-vault.git
cd youtube-vault
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
Copy-Item config.example.yaml config.yaml
python youtube_vault.py
```

Para usar la interfaz gráfica local, ejecuta:

```powershell
python youtube_vault_gui.py
```

La interfaz permite escoger las etapas, modelo Whisper e idioma, y muestra el registro de ejecución sin bloquear la ventana.

También hay un panel web local de flujo guiado, con análisis previo, estado de FFmpeg, progreso por etapas y resultados visibles. Tras instalar las dependencias, ejecútalo con:

```powershell
python vault_web.py
```

Se abrirá en `http://127.0.0.1:8765`; no se expone a la red local ni a Internet. El panel no evita ni suplanta controles de ninguna plataforma.

## Calidad y trazabilidad

- La transcripción prioriza `faster-whisper` y usa los subtítulos disponibles como respaldo. Ajusta `model` a `small`, `medium` o `large-v3` según tus recursos; los modelos mayores suelen mejorar la precisión, pero requieren más memoria y tiempo.
- `transcription.json` registra idioma detectado, configuración de procesamiento, duración y segmentos con marcas de tiempo.
- Cada ejecución incluye `manifest.json`, con el inventario de archivos y sus hashes SHA-256 para facilitar archivado, revisión y reproducibilidad.

## Configuración

`config.example.yaml` contiene valores seguros de partida. Cópialo a `config.yaml` para tus ajustes locales. Este último está ignorado por Git para evitar publicar información sensible, como una posible contraseña de control de Tor, rutas locales o cookies.

No añadas cookies del navegador, tokens, contraseñas ni datos descargados al repositorio. Si una plataforma exige autenticación o autorización, utiliza únicamente tus credenciales mediante mecanismos permitidos por esa plataforma.

El fallback opcional InnerTube solo se activa si defines `YOUTUBE_VAULT_INNERTUBE_KEY` en tu entorno local; nunca lo escribas en `config.yaml`, en commits, issues o pull requests.

## Salidas

El programa escribe en `salidas/`, que se excluye deliberadamente del control de versiones. Puede incluir vídeo, audio, subtítulos, comentarios, metadatos y reportes analíticos. Antes de compartir cualquier salida, revisa derechos de autor, datos personales y condiciones de la fuente.

## Publicación en GitHub

El repositorio incluye `.gitignore`, licencia MIT, dependencias y documentación para que se pueda hacer público sin subir resultados locales ni configuración privada. Antes del primer `push`, revisa lo que se incluirá:

```powershell
git status
git add youtube_vault.py README.md LICENSE requirements.txt config.example.yaml .gitignore
git diff --cached
```

## Licencia

Se distribuye bajo la [licencia MIT](LICENSE).
