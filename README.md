# YouTube Vault

Herramienta de línea de comandos para organizar metadatos, transcripciones, comentarios y análisis de vídeos de YouTube a los que el usuario tenga acceso legítimo.

## Uso responsable y límites

Este proyecto se publica con fines educativos, de investigación y de archivo autorizado. No descarga ni concede derechos sobre contenido de terceros.

- Procesa únicamente contenido propio, con autorización expresa o que puedas usar legalmente.
- Respeta los [Términos de Servicio de YouTube](https://www.youtube.com/t/terms), los derechos de autor, la privacidad y la legislación aplicable.
- No uses esta herramienta para evadir controles de acceso, CAPTCHA, restricciones geográficas, límites de servicio u otras medidas de una plataforma.
- Los comentarios, transcripciones, miniaturas, vídeos y audios pueden contener datos personales o material protegido. No publiques los resultados sin una revisión legal y de privacidad.
- El software se ofrece tal cual, sin garantías. Consulta [LICENSE](LICENSE).

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

## Configuración

`config.example.yaml` contiene valores seguros de partida. Cópialo a `config.yaml` para tus ajustes locales. Este último está ignorado por Git para evitar publicar información sensible, como una posible contraseña de control de Tor, rutas locales o cookies.

No añadas cookies del navegador, tokens, contraseñas ni datos descargados al repositorio. Si una plataforma exige autenticación o autorización, utiliza únicamente tus credenciales mediante mecanismos permitidos por esa plataforma.

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
