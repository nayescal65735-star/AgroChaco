# AgroChaco — Motor de Simulación Secuencial (C++17)

**Materia:** TEL420 Sistemas Paralelos (Gestión 2026)  
**Módulo:** `motor/` — Línea Base Secuencial de Cómputo ($T_1$)  
**Versión:** 1.1.0 (Etapa 1: Arquitectura Base, Validación Física y Correcciones de Auditoría)  

---

## 1. Visión General

El motor de simulación de **AgroChaco** es un software de modelado biofísico y cómputo numérico de alto rendimiento diseñado para evaluar el impacto de la sequía y el estrés hídrico en cultivos de maíz dentro del Gran Chaco boliviano (Tarija, Santa Cruz y Chuquisaca).

Esta primera versión implementa el **motor secuencial mono-hilo en C++17**, el cual actúa como:
1. **Línea base matemática y agronómica:** Modelo de referencia con resultados 100% deterministas y conservación estricta de masa de agua para futuras pruebas de equivalencia numérica con OpenMP, MPI e Híbrido.
2. **Línea base computacional ($T_1$):** Medición de tiempo monohilo con `std::chrono::high_resolution_clock` para el cálculo riguroso de *Speedup* ($S_p = T_1 / T_p$) y *Eficiencia Paralela* ($E_p = S_p / p$) en las etapas posteriores.
3. **Contrato de integración desacoplado:** Capa de serialización en formato JSON compatible directamente con el backend de FastAPI y la interfaz web en React/TypeScript (`SimulationResult`).

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

### Instrucciones de Compilación
Desde la raíz del repositorio (`~/AgroChaco`):

```bash
# 1. Configuración fuera del árbol de fuentes
cmake -B build -S motor

# 2. Compilación de biblioteca y ejecutables
cmake --build build

# Binarios generados en motor/bin/:
# - motor/bin/agrochaco_secuencial
# - motor/bin/test_motor
```

---

## 5. Ejecución del Motor Secuencial

```bash
# Ejecución con configuración JSON y exportación completa
./motor/bin/agrochaco_secuencial \
  --config motor/config/simulacion_villamontes.json \
  --output results/resultado_villamontes.json \
  --csv results/timeline_villamontes.csv
```

Opciones disponibles en CLI:
- `-c`, `--config <archivo.json>`: Ruta al archivo JSON de configuración.
- `-o`, `--output <archivo.json>`: Ruta donde se guardará el resultado estructurado JSON.
- `--csv <archivo.csv>`: Exportación tabular de la serie temporal diaria.
- `-d`, `--days <N>`: Sobrescribe la cantidad de días simulados (1-365).
- `-r`, `--rows <N>`: Sobrescribe las filas de la malla espacial.
- `--cols <N>`: Sobrescribe las columnas de la malla espacial.
- `-h`, `--help`: Muestra el menú de ayuda.

---

## 6. Suite de Pruebas Unitarias y Físicas

Para ejecutar la suite automatizada de 8 pruebas:
```bash
./motor/bin/test_motor
```

Pruebas cubiertas:
1. `testValidationRejectsInvalidParameters`: Rechazo de configuraciones con dimensiones, días o humedades no válidas.
2. `testWaterMassConservation`: Conservación estricta de masa ($|\Delta W + ET_a + Drenaje - P| < 10^{-11}\text{ mm}$) en celdas individuales y en la malla 2D.
3. `testNoPrecipitationDay`: Comportamiento de desecación pura sin drenaje gravitacional en días secos.
4. `testExtremeRainfall`: Precipitación extrema ($150\text{ mm}$) saturando hasta Capacidad de Campo y evacuando el exceso.
5. `testZeroEtcHandling`: Robustez matemática ante $ET_c = 0$, asegurando que no existan divisiones por cero ni valores NaN.
6. `testProlongedDroughtAndPmpConvergence`: Sequía prolongada de 100 días convergiendo asintóticamente a PMP con $CWSI \to 1.0$.
7. `testFao33YieldLossCalculation`: Sensibilidad diferencial por etapas fenológicas (floración R1 vs maduración R6) y acotamiento en $[0, 100]\%$.
8. `testSequentialEngineReproducibility`: Determinismo numérico estricto bit a bit entre ejecuciones sucesivas.
