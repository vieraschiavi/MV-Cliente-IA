# 📲 MV Cliente IA en el celular

Hay **tres formas**, de la más fácil a la más completa. Las tres muestran la
**misma** interfaz: el APK es este mismo frontend adentro de un WebView.

| | Qué hace falta | Cuándo |
|---|---|---|
| **1. Desde el navegador** | Nada | Para probar, o si el celular no deja instalar APKs |
| **2. Agregar a pantalla de inicio** | Nada | Queda con ícono y a pantalla completa, como una app |
| **3. Instalar el APK** | Bajar un archivo | Cuando querés la app de verdad en el cajón de aplicaciones |

---

## 1 y 2 · Sin instalar nada (lo más rápido)

Abrí en el navegador del celular:

- **La web**: <https://mv-cliente-ia.vercel.app/app/>
- **O tu propio servidor**, si tenés el programa abierto en la PC:
  `http://192.168.1.10:8810` — la dirección que muestra el programa al
  arrancar. El celular tiene que estar en **la misma red Wi-Fi**.

Para que quede como app, con su ícono y sin barra del navegador:

- **Android / Chrome**: menú **⋮** → *Agregar a la pantalla principal*.
- **iPhone / Safari**: botón **Compartir** → *Agregar a inicio*.

Es idéntica al APK. Si sólo querés verlo funcionando, no sigas leyendo.

---

## 3 · Instalar el APK

**Archivo:** `MVClienteIA.apk`, en la
[última Release](https://github.com/vieraschiavi/MV-Cliente-IA/releases/latest).

Es un APK **release firmado con clave propia** — no el de debug. Eso importa:
el de debug deja que cualquiera con el celular y un cable lea lo que la app
guarda (tu clave del modelo, la del correo, las de X y LinkedIn).

### Comprobá que llegó entero

Al lado del APK, en la misma Release, está `MVClienteIA.apk.sha256`. En la PC:

```bash
sha256sum MVClienteIA.apk        # Linux / Mac
certutil -hashfile MVClienteIA.apk SHA256   # Windows
```

Tiene que dar **exactamente** lo que dice el `.sha256`. Si no coincide, el
archivo se dañó al transferirlo: bajalo de nuevo.

### Pasarlo al teléfono

Por Google Drive, Telegram **como "archivo"**, o cable USB.
**Evitá WhatsApp**: a veces cambia el archivo y después no instala.

### Instalarlo

1. Abrí **Archivos** / **Mis archivos** → **Descargas**.
2. Confirmá que el nombre termina en **`.apk`**. Si quedó como
   `MVClienteIA` sin extensión, o `.apk.zip`, **renombralo** a
   `MVClienteIA.apk`.
3. Tocá el archivo → Android pide **«Permitir instalar apps de esta fuente»**
   → activalo (es para la app desde la que instalás: Archivos o Chrome).
4. **Instalar**.

### Si dice «aplicación no instalada» o «paquete no válido»

Casi siempre es una de estas tres:

1. **El archivo llegó dañado.** Comprobá el SHA-256 de arriba.
2. **Ya tenías una versión con otra firma.** Desinstalá la vieja primero.
   Pasa si antes instalaste el APK de debug: cambió la firma.
3. **Android viejo.** Necesita Android 6 o superior.

Con cable USB y depuración activada, para ver el error exacto:

```
adb install -r MVClienteIA.apk
```

El código `INSTALL_FAILED_*` que aparezca dice la causa precisa.

---

## Configurar la app: adónde apunta

**El APK no trae el programa adentro** — trae la interfaz. El motor (las seis
fases, la IA, los correos) corre en un servidor, y hay que decirle cuál:

1. Abrí la app → **⚙️ Configuración**.
2. En **«Servidor»**, escribí la dirección:
   - Tu PC con el programa abierto: `http://192.168.1.10:8810`
     (misma Wi-Fi; la dirección la muestra el programa al arrancar).
   - O la web: `https://mv-cliente-ia.vercel.app`
3. **Probar conexión** para confirmar.

> **En una red que no es tuya** (un café, un aeropuerto) usá la dirección
> `https://` de la web, no `http://` de una LAN: por HTTP tus claves viajan
> en texto plano y cualquiera en esa red las lee. La app sólo permite texto
> plano contra redes privadas justamente por eso.

### La edición la pone el servidor, no el APK

Esto responde de una a la pregunta de la edición dueño en el celular: **no
hace falta ningún conversor para el APK**. El APK pregunta por la licencia al
servidor (`GET /api/licencia`), así que hereda lo que ese servidor sea:

| Si el APK apunta a… | La app se comporta como… |
|---|---|
| Tu PC con la edición **dueño** | dueño: sin clave y sin vencimiento |
| Tu PC con la edición **demo** | demo, con sus 14 días |
| La **web** | el cupo gratis de la web |

O sea: pasás tu PC a edición dueño con
`INSTALADOR/OWNER/Convertir-a-edicion-dueno.bat` y el celular que apunte ahí
queda en dueño solo, sin tocar el APK.

---

## Para el dueño: cómo se firma y se publica

Lo construye el CI (`.github/workflows/apk.yml`) con `assembleRelease` y lo
publica en la Release. Necesita la clave de firma una sola vez:

```bash
bash packaging/armar_keystore.sh
```

Genera `mvclienteia.jks` (RSA 4096) e imprime los cuatro secrets para pegar en
**Settings → Secrets and variables → Actions**:

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

> ⚠️ **Guardá el `.jks` y la contraseña.** Android identifica la app por su
> firma: si se pierde el keystore, ninguna actualización futura se va a poder
> instalar encima de las copias ya instaladas — los usuarios tendrían que
> desinstalar y perder sus datos. No se puede recuperar, ni Google puede.

Sin esos secrets el workflow **falla a propósito**, con las instrucciones en
el log. Es preferible a publicar un APK de debug, que fue lo que pasaba antes.

El workflow además comprueba que el APK **no quede marcado como depurable**
antes de publicarlo (`aapt2 dump badging`), así que si eso se colara de nuevo,
corta ahí y no llega a la Release.
