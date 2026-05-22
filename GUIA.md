# Traductor de Libros — Guía rápida

Traduce libros en formato `.epub` del inglés al español.

## Primera vez (instalación)

1. Asegúrate de tener instalados **Python** y **Git** (si no, el instalador te avisará y te dirá de dónde descargarlos).
2. Haz doble clic en **`instalar.bat`**.
3. Cuando termine, se abrirá un archivo llamado **`API_KEY.txt`**. Pega ahí la clave que te he pasado y guárdalo (Archivo → Guardar).
4. Aparecerá un acceso directo **"Traductor EPUB"** en el escritorio.

> Esto solo se hace **una vez**.

## Uso normal

1. Doble clic en el acceso directo **"Traductor EPUB"** del escritorio.
2. Se abre una ventana negra (no la cierres) y, en unos segundos, el navegador con la página del traductor.
3. Arrastra o selecciona tu archivo `.epub` y pulsa **Traducir**.
4. Espera a que la barra llegue al 100 %. El libro traducido se descarga solo (acaba en `_es.epub`).
5. Cuando termines, cierra la ventana negra.

> Tradúcelo con calma: un libro entero puede tardar bastante. Si cierras a medias, no pasa nada — al volver a subir el mismo archivo continúa donde lo dejó.

## ¿Cuándo uso cada cosa?

| Archivo | Cuándo |
|---|---|
| **`instalar.bat`** | Una sola vez, la primera. O si algo deja de funcionar y hay que reinstalar. |
| Acceso directo "Traductor EPUB" (`run.bat`) | Cada vez que quieras traducir un libro. |
| **`setup.bat`** | Normalmente no hace falta tocarlo. Sirve para reinstalar si algo se rompe. |

## Si se agota la cuota diaria

La página te avisará. El progreso queda guardado: vuelve a intentarlo al día siguiente y continuará. Si quieres usar tu propia clave, edita el archivo `API_KEY.txt` (está en la carpeta `traductor-epub` dentro de tu carpeta de usuario) y pega la tuya.

## Problemas

- **No se abre el navegador**: abre tú uno y entra en `http://localhost:5000`.
- **Dice que falta Python o Git**: instálalos desde los enlaces que aparecen y vuelve a ejecutar `instalar.bat`.
