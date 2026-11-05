# Guía de colaboración — AgroChaco

## 1. Objetivo

Este documento establece las reglas para colaborar en el desarrollo de AgroChaco mediante Git y GitHub.

## 2. Ramas principales

- `main`: versión estable del proyecto.
- `develop`: integración de funcionalidades.
- `feature/nombre`: nuevas funcionalidades.
- `fix/nombre`: correcciones de errores.
- `docs/nombre`: cambios de documentación.

## 3. Flujo de trabajo

1. Actualizar la rama develop.
2. Crear una rama para la tarea asignada.
3. Implementar los cambios.
4. Probar el funcionamiento.
5. Realizar commits descriptivos.
6. Enviar los cambios mediante Pull Request hacia develop.
7. Revisar y aprobar antes de integrar.

## 4. Convención de commits

Utilizar mensajes claros:

- `feat:` nueva funcionalidad.
- `fix:` corrección.
- `docs:` documentación.
- `refactor:` reorganización del código.
- `test:` pruebas.
- `chore:` mantenimiento.

Ejemplos:

- `feat: implementar login`
- `feat: agregar simulación OpenMP`
- `fix: corregir conexión PostgreSQL`
- `docs: actualizar arquitectura`

## 5. Organización de módulos

El proyecto se divide en:

- Frontend: React y TypeScript.
- Backend: Python y FastAPI.
- Base de datos: PostgreSQL.
- Motor: C++17.
- Paralelismo: OpenMP.
- Distribución: MPI.
- Infraestructura: Docker y Docker Compose.

Cada colaborador debe coordinar los cambios que afecten interfaces entre módulos.

## 6. Seguridad

- No publicar archivos `.env`.
- No escribir contraseñas ni tokens directamente en el código.
- No subir archivos personales.
- No publicar resultados experimentales como datos científicos validados.
- Utilizar `.env.example` como plantilla sin credenciales reales.

## 7. Pull Requests

Cada Pull Request debe incluir:

- Descripción del cambio.
- Módulo afectado.
- Pruebas realizadas.
- Posibles dependencias o incompatibilidades.

Los cambios deben revisarse antes de incorporarse a `develop`.

## 8. Calidad del proyecto

Se debe procurar:

- Código organizado y legible.
- Validación de entradas.
- Documentación de funcionalidades.
- Pruebas de los módulos.
- Compatibilidad entre frontend, backend y motor.

---

AgroChaco — TEL420 Sistemas Paralelos, gestión 2026.
