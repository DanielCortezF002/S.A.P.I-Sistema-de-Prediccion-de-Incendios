# Aviso de redacción — paquete E2E 2026-10-24

**Alcance:** `artifacts/oc-e2e-20261024/`  
**Motivo:** el repositorio es público y la PR #41 publicó artefactos con datos
identificatorios del entorno local.

Este aviso **no reproduce los valores retirados**. Solo documenta categorías,
conteos y reglas.

---

## 1. Qué se encontró

| Categoría | Archivos | Ocurrencias | Riesgo |
|---|---:|---:|---|
| IPv4 globalmente enrutable del host | 1 (`logs/web-v2.log`) | 3 | Alto: identifica la red de salida del operador |
| Nombre de perfil local de Windows | 19 logs | 31 | Medio: identifica al usuario del equipo |
| Credenciales, tokens o contenido de secretos | 0 | 0 | — |

El nombre aparecía en rutas absolutas (`C:\Users\<nombre>\...`), en una ruta
relativa (`..\Users\<nombre>\...`) y como token suelto en la línea `started by
<nombre>` de Surefire.

No se encontraron claves, contraseñas, cookies ni el contenido del volumen
`..._sapi_v2_secrets`.

---

## 2. Reglas aplicadas

| Regla | Reemplazo | Fundamento |
|---|---|---|
| IPv4 globalmente enrutable | `192.0.2.10` | RFC 5737, TEST-NET-1 (no enrutable) |
| `C:\Users\<nombre>` / `..\Users\<nombre>` | `C:\Users\<local-user>` / `..\Users\<local-user>` | Se conserva la forma de ruta |
| Token suelto del nombre | `<local-user>` | Elimina el identificador |

Se **conservaron** las direcciones RFC 1918 `10.99.99.0/24`, `127.0.0.1` y
`0.0.0.0` porque describen la red aislada documentada en
`tests/e2e/docker-compose.e2e-oc.yml` y son necesarias para reproducir la
evidencia.

---

## 3. Cómo se aplicó

- Script de sanitización con detección de codificación: UTF-16LE con BOM,
  UTF-8 con BOM y UTF-8 sin BOM.
- Se preservaron BOM, saltos de línea y el resto de los bytes; solo cambiaron los
  tramos reemplazados.
- Los 23 JSON del paquete siguen parseando.
- Verificación con escaneo consciente de codificación: **0** nombres residuales y
  **0** IPv4 globalmente enrutables adicionales.
- Falso positivo documentado: `21.0.12.1` es la versión de Java
  (`Java 21.0.12.1`), no una dirección IP.

---

## 4. Exposición histórica (importante)

Sanitizar el HEAD **no borra** los valores de los commits ya publicados. En
concreto:

- el commit `426605f86a98939cd5124ef0e9cea5aa0fc271d1` de la rama
  `test/oc-fullstack-e2e-20261024` (PR #41) sigue conteniendo los valores
  originales en su historia;
- GitHub puede conservar los blobs y las vistas de commits aunque el HEAD se
  sanee;
- un `force-push` o una reescritura de historia **no** se ejecutó: requiere
  autorización del Product Owner.

Opciones de remediación histórica, todas sujetas a decisión humana:

1. **Cerrar/abandonar PR #41 y la rama R1**, y adoptar la PR de sustitución R2
   (historia limpia, sin los valores).
2. **Reescribir la historia de la rama R1** y hacer `force-push` con
   autorización; esto cambia los SHA y rompe enlaces existentes.
3. **Solicitar a GitHub Support la purga** de los objetos y vistas cacheadas,
   además de cerrar la rama.

Mientras no se autorice una de ellas, la exposición histórica debe declararse
**abierta**.

### 4.1 Fuera del paquete E2E (preexistente, no modificado)

Un escaneo de archivos de texto del worktree R2 encontró el nombre del perfil
local también en **20 archivos históricos** fuera de
`artifacts/oc-e2e-20261024/` (151 ocurrencias), entre ellos:

- `SAPI_SPRINT2_CLOSEOUT_REPORT.md`;
- documentación de Hito 1/Hito 2;
- artefactos históricos `artifacts/hito1/` y `artifacts/hito2/`;
- `reports/coverage_run.txt` y un `git-log.txt` (donde el nombre puede ser
  también metadato legítimo de autoría).

No se modificaron: son registros históricos de otro alcance y varios pertenecen
a trabajo de Antigravity. **No hay IPv4 globalmente enrutable fuera de
`logs/web-v2.log`** (ya redactado). Su tratamiento requiere una decisión de
gobernanza separada; este paquete no los introduce ni los reproduce.

---

## 5. Copia intacta para auditoría

Se preservó una copia local **no publicada** del commit `426605f` en una ruta
bajo el perfil del operador (el segmento de usuario se muestra aquí como
`<local-user>` para no volver a publicarlo):

`C:\Users\<local-user>\AppData\Local\Temp\opencode\sapi-audit-baseline-426605f`

Incluye 1.064 archivos y un manifiesto `BASELINE-SHA256SUMS.txt` con los 80
archivos del paquete original. Esa copia conserva los valores originales y no
debe publicarse ni adjuntarse a la PR.

---

## 6. Verificación

```powershell
# Escaneo consciente de codificación (UTF-16LE incluido)
python C:\Users\<local-user>\AppData\Local\Temp\opencode\scan2.py artifacts/oc-e2e-20261024
```

Resultado esperado: sin IPv4 globalmente enrutables (salvo el falso positivo de
la versión de Java, documentado en §3) y sin nombres de perfil locales dentro de
`artifacts/oc-e2e-20261024/`.
