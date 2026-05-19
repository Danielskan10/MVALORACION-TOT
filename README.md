# README.md — MREVISION WEB

## Objetivo

Construir una aplicación web para control y revisión de procesos de valoración financiera.

La aplicación debe unir dos frentes principales:

1. **Revisión de insumos** que se cargan a las aplicaciones de valoración.
2. **Revisión de resultados** e informes generados por dichas aplicaciones.

El objetivo es detectar errores operativos, diferencias de precios, problemas de causación, monedas incorrectas y variaciones anormales antes de entregar información final.

---

# 1. Revisión de Insumos

La aplicación debe detectar y procesar automáticamente archivos diarios descargados desde distintas fuentes operativas.

## Archivos esperados

* SP
* SW
* TP
* MX
* 572
* 575
* 596
* LUCLUC
* MITRA
* PORFIN

## Funcionalidades

* Conversión automática a Excel.
* Validación de estructura.
* Revisión de columnas faltantes.
* Detección de archivos incompletos.
* Comparación vs día anterior.
* Validación de cantidades.
* Validación de curvas e insumos de valoración.
* Monitoreo de variaciones históricas.
* Detección de diferencias monetarias relevantes.
* Alertas automáticas por cambios anormales.

---

# 2. Revisión de Resultados de Valoración

La aplicación debe revisar los informes generados por las aplicaciones de valoración.

## Validaciones requeridas

### Precios

* Validación de precios cargados.
* Comparación vs históricos.
* Detección de variaciones atípicas.

### Causaciones

* Validación de causaciones diarias.
* Revisión de signos.
* Revisión de acumulados.
* Validación de cálculos financieros.

### Monedas

* Validación de monedas correctas.
* Revisión de conversiones.
* Detección de inconsistencias.

### Operaciones

* Validación de nocionales.
* Revisión de fechas.
* Validación de tasas.
* Comparación contra insumos originales.

---

# Dashboard Web

La aplicación debe incluir un dashboard interactivo con:

* Estado de carga.
* Archivos procesados.
* Variaciones diarias.
* Alertas críticas.
* Gráficas históricas.
* KPIs operativos.
* Resumen diario de revisión.

---

# Gestión de Datos

La app debe permitir:

* Ver información detallada.
* Filtrar datos.
* Buscar operaciones.
* Editar registros.
* Eliminar registros.
* Aprobar revisiones.
* Marcar errores operativos.
* Guardar observaciones.

---

# Exportación

La aplicación debe permitir descargar:

* Excel de revisiones.
* Archivos con fórmulas.
* Reportes operativos.
* Consolidados diarios.
* Informes de diferencias.

Los Excel exportados deben ser visualmente organizados y listos para uso operativo.

---

# Tecnologías esperadas

## Backend

* Python
* Pandas
* Numpy
* Openpyxl

## Frontend

* Flask o FastAPI
* HTML
* JavaScript
* Plotly / AG Grid

## Base de datos

* SQLite o PostgreSQL

---

# Objetivo Final

Crear una plataforma web de monitoreo y control operativo que permita:

* Revisar insumos de valoración.
* Validar resultados financieros.
* Detectar errores operativos.
* Analizar variaciones.
* Gestionar revisiones.
* Centralizar controles diarios.
* Generar reportes y dashboards.
* Reducir riesgo operativo en valoración financiera.
