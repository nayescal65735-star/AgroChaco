# AgroChaco — Motor de Simulación Paralela y Distribuida (C++17)

**Materia:** TEL420 Sistemas Paralelos (Gestión 2026)  
**Módulo:** `motor/` — Motores Secuencial, OpenMP, MPI e Híbrido
**Versión:** 2.0.0 (Motores paralelos, distribuidos y validación de rendimiento)

---

## 1. Visión General

El motor de simulación de **AgroChaco** es un software de modelado biofísico y cómputo numérico de alto rendimiento diseñado para evaluar el impacto de la sequía y el estrés hídrico en cultivos de maíz dentro del Gran Chaco boliviano (Tarija, Santa Cruz y Chuquisaca).

El módulo implementa cuatro modalidades de ejecución en **C++17**: secuencial, paralela con OpenMP, distribuida con MPI e híbrida MPI + OpenMP. El motor secuencial actúa como referencia matemática y computacional para evaluar las versiones paralelas.
1. **Referencia matemática y agronómica:** El motor secuencial proporciona la línea base para contrastar los resultados de las implementaciones paralelas y distribuidas.
2. **Cómputo paralelo y distribuido:** OpenMP utiliza memoria compartida; MPI distribuye el trabajo entre procesos; el motor híbrido combina ambos modelos.
3. **Integración de resultados:** Los motores generan resultados estructurados en JSON, compatibles con el contrato de integración del backend y la interfaz del proyecto.

---

## 2. Fundamentos Biofísicos y Ecuaciones

### 2.1. Distinción Rigurosa: ¿CWSI Térmico o Déficit Relativo de Evapotranspiración?
En la literatura científica agronómica:
- El **CWSI canónico (Idso et al. 1981; Jackson et al. 1981)** se fundamenta en la temperatura radiométrica del dosel foliar ($T_c$) medida mediante sensores infrarrojos respecto a la temperatura del aire ($T_a$):
  $$CWSI_{termico} = \frac{(T_c - T_a) - (T_c - T_a)_{lower}}{(T_c - T_a)_{upper} - (T_c - T_a)_{lower}}$$
- En **AgroChaco**, el indicador reportado como `cwsi` en la interfaz se calcula a partir del balance hídrico del suelo (FAO-56):
  $$Indicador = 1 - \frac{ET_a}{ET_c}$$
  Científicamente, este indicador corresponde al **Índice de Déficit Relativo de Evapotranspiración (RED / ETDI)**. Se mantiene la denominación `cwsi` exclusivamente por compatibilidad con los tipos del frontend, representando la fracción de demanda evaporativa insatisfecha por falta de agua en el perfil del suelo.

### 2.2. Modelo Hidrológico Mono-Capa y Conservación de Masa
Para cada celda de la parcela en el paso diario $t$, con profundidad radicular $Z_r$ y precipitación uniforme $P_t$:
1. **Conservación estricta de masa:**
   $$\Delta W + ET_a + Drenaje = P_t$$
   Donde:
   - $W_{inicial} = (\theta_{t-1} / 100) \times (Z_r \times 1000)$ mm de columna de agua.
   - $P_t$ es la lluvia incidente uniforme en toda la parcela (sin factores multiplicativos arbitrarios).
   - $Drenaje = \max(0, W_{inicial} + P_t - W_{CC})$ es el exceso gravitacional por encima de la Capacidad de Campo ($CC$).
   - $ET_a = \min(ET_c \times K_s, W_{infiltrada} - W_{PMP})$ es la transpiración real del cultivo.
   - $\Delta W = W_{final} - W_{inicial}$.
   - El error de balance $|\Delta W + ET_a + Drenaje - P_t| < 10^{-11}\text{ mm}$ en cada celda y en el promedio de la malla.
2. **Coeficiente de estrés hídrico ($K_s$, FAO-56):**
   Con fracción de agotamiento fácilmente utilizable $p = 0.50$:
   $$\theta^* = CC - p \cdot (CC - PMP)$$
   $$K_s(\theta) = \begin{cases} 
   1.0 & \text{si } \theta \ge \theta^* \\
   \frac{\theta - PMP}{\theta^* - PMP} & \text{si } PMP < \theta < \theta^* \\
   0.0 & \text{si } \theta \le PMP 
   \end{cases}$$

### 2.3. Modelo de Rendimiento de Cultivo (FAO-33 Stewart-Doorenbos)
La reducción en el rendimiento potencial se calcula mediante la **formulación aditiva por etapas fenológicas de FAO-33** (Doorenbos & Kassam 1979, ecuación 2), eliminando ponderaciones heurísticas y preservando la magnitud de $K_y > 1$:
$$1 - \frac{Y_a}{Y_m} = \left[ \sum_{i=1}^{n} K_{y, i} \times \left(1 - \frac{ET_{a, i}}{ET_{c, i}}\right) \times \frac{ET_{c, i}}{ET_{c, total}} \right] \times Factor_{variedad}$$

- **Sensibilidad por etapa ($K_{y, i}$ para maíz):**
  - Vegetativo (V3 - V12): $K_y = 0.40$
  - Floración y Polinización (R1): $K_y = 1.25$ (**Etapa Crítica**, mayor penalización)
  - Llenado de Grano (R2 - R4): $K_y = 0.50$
  - Maduración (R5 - R6): $K_y = 0.20$
- **Límite físico:** La pérdida de rendimiento se acota estrictamente en el intervalo $[0.0, 100.0]\%$.

---

## 3. Clasificación de Parámetros y Limitaciones Científicas

| Categoría | Parámetros | Origen / Justificación |
| :--- | :--- | :--- |
| **Configurados por el usuario** | `rows`, `cols`, `cellSizeMeters`, `simulationDays`, `initialMoisturePercent`, `droughtScenario`, `zone`, `soilType`, `cornVariety` | Entradas de la simulación validadas por `ConfigValidator`. |
| **Datos de referencia científica** | - Coeficientes $K_c$ por etapa (FAO-56: 0.40 a 1.20)<br>- Coeficientes $K_y$ por etapa (FAO-33: 0.20 a 1.25)<br>- Coordenadas, lluvia anual y temperatura media de zonas chaqueñas | Literatura agronómica estándar FAO y estaciones meteorológicas de referencia (SENAMHI / INIAF). |
| **Supuestos de modelación** | - Modelo de balance de cubo mono-capa (*single-layer bucket model*)<br>- Precipitación uniforme sobre la parcela sin transporte lateral<br>- Factor de rusticidad varietal ($0.85$ Criollo, $0.95$ INIAF, $1.05$ Dekalb) | Simplificaciones de cómputo para simulación distribuida. No calibradas en parcelas experimentales. |

> [!WARNING]
> **Aviso de Integridad Científica:**  
> Este motor es una herramienta de simulación computacional para análisis comparativo de escenarios climáticos y evaluación de escalabilidad paralela (HPC). **No constituye un modelo calibrado experimentalmente con ensayos agronómicos de campo en el Gran Chaco.**

---

## 4. Compilación y Requisitos

### Requisitos del Sistema
- Compilador de C++ con soporte C++17 (`g++ >= 9.0` o `clang++ >= 10.0`).
- `CMake >= 3.16`.
- GNU `make`.
- OpenMP compatible con el compilador C++.
- OpenMPI (`libopenmpi-dev` y `openmpi-bin`) para las versiones MPI e híbrida.

### Instrucciones de Compilación
Desde la raíz del repositorio (`~/AgroChaco`):

```bash
# 1. Configuración fuera del árbol de fuentes
cmake -B build -S motor

# 2. Compilación de biblioteca y ejecutables
cmake --build build

# Ejecutables generados en motor/bin/:
# - agrochaco_secuencial
# - agrochaco_openmp
# - agrochaco_mpi
# - agrochaco_hibrido
# - test_motor
```

---


## 5. Ejecución de los Motores

### 5.1. Secuencial

    ./motor/bin/agrochaco_secuencial --config motor/config/simulacion_yacuiba.json --days 120 --rows 500 --cols 500 --output results/secuencial.json

### 5.2. OpenMP

    ./motor/bin/agrochaco_openmp --config motor/config/simulacion_yacuiba.json --days 120 --rows 500 --cols 500 --threads 16 --output results/openmp.json

### 5.3. MPI

    mpirun -np 4 ./motor/bin/agrochaco_mpi --config motor/config/simulacion_yacuiba.json --days 120 --rows 500 --cols 500 --output results/mpi.json

### 5.4. Híbrido MPI + OpenMP

    mpirun -np 2 ./motor/bin/agrochaco_hibrido --config motor/config/simulacion_yacuiba.json --days 120 --rows 500 --cols 500 --threads 8 --output results/hibrido.json

### 5.5. Opciones

- `--config`: archivo JSON de configuración.
- `--output`: archivo de resultados JSON.
- `--csv`: exportación de resultados diarios.
- `--days`: días de simulación.
- `--rows`: filas de la malla.
- `--cols`: columnas de la malla.
- `--threads`: hilos OpenMP.
- `mpirun -np`: procesos MPI.

Los resultados incluyen el campo `executionTimeSeconds`.

---

## 6. Suite de Pruebas Unitarias

Ejecutar:

    ./motor/bin/test_motor

También se puede utilizar CTest:

    ctest --test-dir build --output-on-failure

La suite contiene ocho pruebas: validación de parámetros, conservación de masa de agua, día sin precipitación, lluvia extrema, ETc igual a cero, sequía prolongada, cálculo FAO-33 y reproducibilidad secuencial.

**Resultado registrado:** 8/8 pruebas aprobadas y CTest con 100 % de éxito.

---

## 7. Evaluación del Rendimiento

### 7.1. Configuración experimental

| Parámetro | Valor |
|---|---|
| Zona | Yacuiba |
| Días | 120 |
| Filas | 500 |
| Columnas | 500 |
| Celdas | 250.000 |
| Ejecuciones medidas | 5 por motor |
| Calentamiento | 1 ejecución por motor |
| Procesador | Intel Core i7-13700 |
| Sistema operativo | Ubuntu 24.04.2 LTS |

### 7.2. Resultados

| Motor | Recursos | Promedio (s) | Mediana (s) | Speedup | Eficiencia |
|---|---|---:|---:|---:|---:|
| Secuencial | 1 hilo | 0.2450 | 0.2440 | 1.00x | 100.00 % |
| OpenMP | 16 hilos | 0.0408 | 0.0400 | 6.00x | 37.53 % |
| MPI | 4 procesos | 0.0682 | 0.0670 | 3.59x | 89.81 % |
| Híbrido | 2 × 8 | 0.1194 | 0.1210 | 2.05x | 12.82 % |

### 7.3. Fórmulas

Speedup:

    S_p = T_1 / T_p

Eficiencia:

    E_p = (S_p / p) * 100

Donde T1 es el tiempo secuencial, Tp el tiempo paralelo y p el número de trabajadores nominales.

### 7.4. Análisis

- OpenMP obtuvo el menor tiempo promedio.
- MPI consiguió un speedup de 3.59x.
- El híbrido presentó mayor costo de coordinación en esta configuración.
- El motor secuencial constituye la referencia experimental.

Los resultados corresponden a las condiciones de esta prueba y no son universales.

---

## 8. Verificación de Resultados Agronómicos

Los cinco indicadores se mantuvieron consistentes en las cinco ejecuciones medidas de cada motor.

| Indicador | Secuencial | OpenMP | MPI | Híbrido |
|---|---:|---:|---:|---:|
| CWSI promedio | 0.67 | 0.67 | 0.67 | 0.67 |
| Humedad final (%) | 8.5 | 8.5 | 8.5 | 8.5 |
| Déficit hídrico (mm) | 373.1 | 373.1 | 373.1 | 373.1 |
| Pérdida de rendimiento (%) | 95.0 | 95.0 | 95.0 | 95.0 |
| Rendimiento estimado (tn/ha) | 0.27 | 0.27 | 0.27 | 0.27 |

La comparación se realizó con la precisión almacenada en los archivos JSON.

---

## 9. Archivos de Resultados

Los resultados experimentales se almacenan en:

    results/benchmark_final/

Incluyen los archivos JSON de las ejecuciones, `mediciones.csv` y `resumen.csv`.

Estos archivos respaldan el análisis experimental y se conservan localmente.
