#!/usr/bin/env bash
# Crea la clave de firma del APK y deja listos los cuatro secrets de GitHub.
#
#   bash packaging/armar_keystore.sh
#
# Sale de la metodología de MV Agendate IA, que genera su keystore la primera
# vez que se construye el APK (`movil/construir-apk-release.sh`) en vez de
# pedirle al dueño que averigüe la línea de `keytool`.
#
# POR QUÉ HACE FALTA
# Hasta la auditoría, el APK que se publicaba era el de DEBUG: `debuggable`
# en true y firmado con la clave de debug de Gradle. Con eso, cualquiera con
# el teléfono en la mano y `adb` corría `run-as` y se llevaba el localStorage
# del WebView — la clave del modelo, la del correo y las de X y LinkedIn. El
# workflow ahora exige un release firmado; esto genera la clave para hacerlo.
#
# GUARDÁ EL ARCHIVO .jks Y LA CONTRASEÑA.
# Android identifica una app por su firma: si se pierde el keystore, ninguna
# actualización va a poder instalarse encima de las copias ya instaladas. Los
# usuarios tendrían que desinstalar y volver a instalar, perdiendo sus datos.
# No hay forma de recuperarlo — ni Google puede.
set -euo pipefail

SALIDA="${1:-mvclienteia.jks}"
ALIAS="${MVCLIENTE_KEY_ALIAS:-mvclienteia}"
# 10000 días ~ 27 años. Google Play exige que el certificado siga válido
# después de 2033, así que una validez corta deja la app sin poder actualizarse.
DIAS="${MVCLIENTE_KEY_DIAS:-10000}"

if [ -e "$SALIDA" ]; then
  echo "ERROR: ya existe $SALIDA." >&2
  echo "       No lo piso: si es el keystore con el que ya firmaste," >&2
  echo "       reemplazarlo dejaría sin actualizacion a lo instalado." >&2
  exit 1
fi

if ! command -v keytool >/dev/null 2>&1; then
  echo "ERROR: falta 'keytool' (viene con Java)." >&2
  echo "       Instalalo con: sudo apt install default-jdk   (o el JDK de tu sistema)" >&2
  exit 1
fi

# La contraseña se pide sin eco, o llega por entorno para poder automatizar.
if [ -n "${MVCLIENTE_KEYSTORE_PASS:-}" ]; then
  CLAVE="$MVCLIENTE_KEYSTORE_PASS"
else
  read -r -s -p "Contraseña para el keystore (no se ve al escribir): " CLAVE
  echo
  read -r -s -p "Repetila: " CLAVE2
  echo
  [ "$CLAVE" = "$CLAVE2" ] || { echo "ERROR: no coinciden." >&2; exit 1; }
fi

if [ ${#CLAVE} -lt 8 ]; then
  # keytool rechaza menos de 6; 8 es el mínimo razonable para algo que no se
  # puede rotar nunca más.
  echo "ERROR: la contraseña tiene que tener al menos 8 caracteres." >&2
  exit 1
fi

echo "[1/2] Generando la clave de firma (RSA 4096, $DIAS dias)..."
keytool -genkeypair -v \
  -keystore "$SALIDA" \
  -storepass "$CLAVE" -keypass "$CLAVE" \
  -alias "$ALIAS" \
  -keyalg RSA -keysize 4096 -validity "$DIAS" \
  -dname "CN=MV Cliente IA, OU=MV, O=MV, L=Montevideo, C=UY" \
  >/dev/null 2>&1

echo "[2/2] Listo: $SALIDA"
echo
echo "=================================================================="
echo " Cargá estos cuatro secrets en GitHub"
echo "   Settings -> Secrets and variables -> Actions -> New secret"
echo "=================================================================="
echo
echo "  ANDROID_KEYSTORE_PASSWORD   ->  (la contraseña que acabas de poner)"
echo "  ANDROID_KEY_PASSWORD        ->  (la misma)"
echo "  ANDROID_KEY_ALIAS           ->  $ALIAS"
echo "  ANDROID_KEYSTORE_BASE64     ->  el texto largo que sigue:"
echo
base64 -w0 "$SALIDA" 2>/dev/null || base64 "$SALIDA" | tr -d '\n'
echo
echo
echo "=================================================================="
echo " GUARDA $SALIDA Y LA CONTRASENA en un lugar seguro."
echo " Android identifica la app por su firma: sin este archivo, ninguna"
echo " actualizacion futura se va a poder instalar encima de las copias"
echo " ya instaladas. No se puede recuperar."
echo "=================================================================="
