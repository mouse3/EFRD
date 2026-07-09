# README, Sistema EFRD (Equilibrio Fiscal y Resiliencia Dinámica)
## 1. Visión general

Es un motor de redistribución de renta que simula un sistema fiscal donde **cada hogar tiene un umbral de dignidad personalizado** (`k_hogar`) basado en su composición familiar y el coste de vida de su municipio.
El sistema clasifica a cada hogar en dos categorías: 
- **Contribuyente:** su renta supera `k_hogar`. Paga una cuota progresiva y asintótica sobre el excedente. Nunca pierde más del `L × 100%` de su renta (por defecto 60%). 
- **Receptor:** su renta no alcanza `k_hogar`. El Estado le complementa hasta ese umbral mediante un subsidio.

Una de las ventajas que proporciona es que, a diferencia del IRPF tradicional, no existen tramos fijos. Una única fórmula continua cubre a toda la población, garantizando que la transición entre receptor y contribuyente sea suave y sin saltos bruscos.
Esto garantiza que nunca se gane menos trabajando más y que la progresividad sea infinita.

---

## 2. Arquitectura y flujo de datos 
``` 
[Fuentes externas] 
Catastro · Padrón · IRPF/AEAT · Seg. Social · Servicios Sociales · INE 
	│ 
	▼ 
conexion/transformador.py       ← pobla la BD principal (externo al proyecto) 
	│ 
	▼ 
Base_Datos_MACRO.db 
	└── tabla: Base_Datos_MACRO ← una fila por persona censada 
		  │ 
		  ▼ 
main.py 
  ├── EFRD_Protocol_v4_1()           ← calcula k_base, verifica solvencia 
  ├── procesar_simulacion_efrd()     ← calcula cuota de cada hogar → resultados_ciudadanos 
  └── generar_liquidaciones()        ← agrega por ref_catastral → Liquidaciones_EFRD.db 
	    │ 
	    ├──▶ Base_Datos_MACRO.db 
			    └── tabla: resultados_ciudadanos 
		|
		|
		└──▶ Liquidaciones_EFRD.db 
				└── tabla: liquidaciones_hogares 
		│ 
		▼ 
diagnostico.py    ← análisis macroeconómico independiente 
├── graficar_diagnostico_comparativo() ← ANTES vs DESPUÉS 
├── calcular_analizar_y_graficar_pareto_semilog() 
└── graficar_distribucion_saldos() 
		│ 
		▼
ejemplos/salida/*.png + *.txt         ← gráficas e informes conexion/outputs/efrd_config.json     ← parámetros del motor para diagnostico.py 
```

 ---
## 3. Fundamento matemático 

Para visualizar este apartado de una manera gráfica, visitar: [link](https://www.desmos.com/calculator/8nxnfzbpfo?lang=es)
### 3.1 Suelo vitalicio base (`k_base`) 
``` 
k_base = α · (Y / N) · G · π 
``` 

| Variable       | Significado                                    | Fuente                                   |
| -------------- | ---------------------------------------------- | ---------------------------------------- |
| $\alpha$       | Fracción del PIB per cápita destinada al suelo | Parámetro de política (0.05 por refecto) |
| Y              | PIB nominal en euros                           | INE / Banco de España                    |
| N              | Población total censada en la Base de Datos    | Conteo de 'dni_nie_nif'                  |
| G              | Coeficientes de Gini                           | Parámetro de política (0.33 por defecto) |
| $\pi$ (IPC_Pi) | Factor IPC = 1+tasa de inflación               | INE                                      |

El factor `G` hace que **a mayor desigualdad, mayor sea el suelo base** que el sistema puede garantizar, forzando a que una economía más desigual tengs más renta distribuible de forma eficiente. 
### 3.2 Umbral del hogar (`k_hogar`) 
``` 
k_hogar = k_base × φ × γ 
``` 
- **φ (phi):** multiplicador de composición familiar.
	- Persona sola: φ = 1.0 
	- +0.5 por cada adulto adicional en el hogar 
	- +0.3 por cada hijo menor de edad 
	- Ejemplo: dos adultos y un hijo → φ = 1.0 + 0.5 + 0.3 = **1.8** 
- **γ (gamma):** índice de coste de vida del municipio, derivado del valor catastral. Municipios caros tienen γ > 1; municipios rurales, γ < 1. 
### 3.3 Cuota del contribuyente 
sea la renta un sinónimo de "ingreso bruto", entonces, para un hogar con `renta > k_hogar`: 
``` 
x = (renta − k_hogar) / k_hogar     ← exceso relativo de renta 
tasa = L · (1 − e^(−σ · |x|))         ← tasa efectiva (asintótica) 
cuota = (renta − k_hogar) · tasa 
neto = renta − cuota 
``` 
Propiedades de la función: 
- Cuando `x → 0` (renta apenas supera el umbral): 
	- `tasa → 0`. No se paga casi nada. 
- Cuando `x → ∞` (renta muy superior al umbral):
	- `tasa → L`. Nunca se supera el límite máximo. 
- La función es **estrictamente creciente y continua**: no hay saltos de tipo marginal.
### 3.4 Subsidio del receptor 
Para un hogar con `renta ≤ k_hogar`: 
``` 
subsidio = k_hogar − renta  (siempre positivo) 
neto =     k_hogar          (el Estado completa hasta el umbral) 
``` 
El Estado no da más que el umbral: garantiza la dignidad, no la igualdad. 
### 3.5 Caso borde: `k_hogar = 0` 
Si por algún motivo `k_hogar = 0` (datos corruptos o gamma = 0), `_calcular_x` satura `x = 10`, lo que produce `tasa ≈ L` (máxima contribución posible). Esto evita una división por cero y documenta el caso explícitamente.
### 3.6 Umbral AROPE 
``` 
k_arope = 0.6 × renta_mediana_nacional 
``` 
Estándar europeo de riesgo de pobreza. Si `k_base < k_arope`, el sistema no cumple el mínimo de dignidad reconocido por la UE. El motor ofrece el **Protocolo PSD** para corregirlo si el presupuesto lo permite. 

--- 
## 4. Estructura de archivos ``` 
```
C:.
│   README(Guia).md 			<- Esta guia
│   requirements.txt			<- Dependencias del código
│   main.py						<- programa principal (punto de entrada)
│   EFRD.py						<- motor distributivo + visualizadores
│   diagnostico.py				<- análisis macroeconómico (independiente del resto del código)	  ┐
│   simulacion.py				<- calculo de cuotas individuales								  |
│   traductores.py				<- adaptadores de datos externos (INE, BdE…)					  |
│   LICENSE						<- La licencia bajo la que opera el proyecto (GPL-3.0)			  |
│																								  |
├───.obsidian					<- Carpeta de formatos para visualizar la documentación			  |
│       app.json																				  |
│       appearance.json																			  |
│       core-plugins.json																		  |
│       workspace.json																			  |
│																								  |
├───ejemplos																					  |
│   └───salida					  <- Carpeta de resultados de diagnostico.py ─────────────────────┘
│           distribucion_saldos_histograma.png
│           grafica_diagnostico_macro_semilog.png
│           ingresos_informe_pareto.txt
|
├───Análisis					<- Estudios sobre el sistema
│   └───Cadenas-Markov
│           ANÉXO TÉCNICO.md
│           Markov.ipynb
│
├───conexión					
│   │   crear_db_ejemplo.py		 <- Crea las bases inputs/ de ejemplo
│   │   emulador.py				 <- Ofrece la posibilidad de ejecutar código monolineares de sql
│   │   generador_aleatorio.py  <- Genera Base_Datos_Macro.db con datos aleatorios (sin basarte en inputs/)
│   │   transformador.py  		 <- (externo y realista) genera Base_Datos_MACRO.db basado en inputs/
│   │																							|
│   ├───Croquis																					|
│   │       Croquis_Base_datos.dbml																|
│   │       Croquis_base_datos.pdf																|
│   │																							|
│   ├───inputs																		<───────────┘
│   │       asistencia.db
│   │       cnp.db
│   │       hacienda.db
│   │       ine.db
│   │       padron.db
│   │       vivienda.db
│   │
│   └───outputs
│           Base_Datos_MACRO.db  <- BD principal (personas + resultados)
|	    Liquidaciones_EFRD.db <- BD de salida (liquidaciones por hogar)
│           efrd_config.json 	  <- parámetros del motor para diagnostico.py
│           
│
├───Documentacion
│       Propuesta técnica.md
│
│
│
└───Screenshots				  <- Capturas de pantalla de los gráficos que ofrece main.py
        Impacto_alpha_1.png
        Impacto_alpha_2.png
        Impacto_limite_maximo_1.png
        Impacto_limite_maximo_2.png
        Impacto_sigma_progresividad.png
        Mapa_Calor_sist_redistributivo.png
```
---
## 5. Módulo EFRD.py — Motor principal 
### 5.1 Clase `EFRD_Protocol_v4_1` 
Núcleo del sistema. Se instancia una vez por ejecución y encapsula todos los parámetros macroeconómicos y la lógica de solvencia. 
**Constructor:** 
```python 
EFRD_Protocol_v4_1(
	PIB_Y, # PIB nominal en EUR 
	Gini, # Coeficiente de Gini (0–1) 
	Alpha, # Fracción del PIB per cápita para k_base 
	Sigma, # Velocidad de progresividad de la cuota 
	Limite_L, # Techo asintótico de la tasa efectiva (0–1) 
	G_op, # Gastos operativos del Estado en EUR/mes 
	IPC_Pi, # Factor IPC (1 + tasa de inflación) 
	db_path, # Ruta a Base_Datos_MACRO.db 
	tabla_central, # Nombre de la tabla principal 
	modo # 'interactivo' | 'deuda' | 'ajuste' | 'test' 
	) 
``` 
**Secuencia de inicialización:** 
1. `_cargar_datos_desde_db()` — lee y agrupa hogares desde SQLite 
2. `calcular_k_base()` — calcula el suelo vitalicio base 
3. `_ejecutar_logica_central()` — verifica solvencia y dignidad
4. `_finalizar_auditoria()` — imprime liquidación y guarda `efrd_config.json`

**Métodos públicos principales:** 

| Método                                             | Descripción                                                                  |
| -------------------------------------------------- | ---------------------------------------------------------------------------- |
| calcular_k_base($\alpha$, Y, N, G, $\pi$)          | Estático. Fórmula canónica del sueldo vitalicio                              |
| `_calcular_x(diferencial, k_hogar)`                | Estático. Exceso relativo de renta (con saturación en k=0)                   |
| simular_balance(k_prueba)                          | Simula la recaudación y subsidios para un k dado. Usado en búsqueda binaria. |
| calcular_cuota_hogar(renta, adultos, hijos, gamma) | Calcula una cuota para un hogar hipotético. Usado por los visualizadores.    |

### 5.2 Protocolo de solvencia (búsqueda binaria) 
Cuando `simular_balance(k_base) < 0`, el motor ejecuta 25 iteraciones de búsqueda binaria entre `[0, k_base]` para encontrar el `k_equilibrio` máximo que mantiene el sistema solvente. La precisión tras 25 iteraciones es `k_base / 2^25`, prácticamente irrelevante en la práctica. 
### 5.3 Protocolo de dignidad (PSD) 
Si `k_base < k_arope`, el motor comprueba si subir hasta `k_arope` seguiría siendo solvente. Si sí, ofrece activarlo (solo en modo interactivo). Si el Protocolo de Solvencia ya ajustó `k_base` a la baja, el PSD queda bloqueado para evitar contradicción lógica. 
### 5.4 Protocolo de Masa Crítica 
Verifica que al menos el 40% de los hogares sean contribuyentes netos. Si no se cumple, emite una alerta estructural: el sistema tiene demasiados receptores para ser autosostenible a largo plazo sin deuda. 
```python 
RATIO_MASA_CRITICA_MIN = 0.40 
``` 
### 5.5 Clase `EFRD_AdvancedVisualizer()` 
Herramienta de análisis de sensibilidad paramétrica. Usa `deepcopy` del motor para simular variaciones de `σ`, `L` y `α` sin modificar el estado del motor original. 

| Método              | Qué muestra                                           |
| ------------------- | ----------------------------------------------------- |
| comparar_sigmas()   | Cuota vs ingreso para distintos valores de $\sigma$   |
| comparar_limite_L() | Tipo efectivo vs ingreso para distintos techos L      |
| comparar_alpha()    | Ingreso neto vs ingreso bruto para distintos $\alpha$ |
| mapa_calor()        | Ingreso neto como función de (bruto, $\phi$)          |

### 5.6 Clase `EFRD_AnalyticVisualizer` 
Es un visualizador analítico sobre datos reales de la BD. Lee directamente de SQLite. 

| Método                              | Qué muestra                                                    |
| ----------------------------------- | -------------------------------------------------------------- |
| graficar_curva_sostenibilidad()     | Recaudación, subsidios y saldo neto en función de k_base       |
| graficar_ingreso_bruto_vs_neto()    | Curvas de redistribución para distintas composiciones de hogar |
| graficar_tipo_impositivo_efectivo() | Progresividad asintótica con línea de techo L                  |
| graficar_mapa_calor_bienestar()     | Ingreso neto en el espacio (bruto $\times \space \phi$)        |
| graficar_distribucion_ingresos()    | Histograma de rentas brutas anuales con k_base superpuesto     |
Todos los métodos aceptan `guardar: bool` y `ruta: str`. Si `guardar=False` llaman a `plt.show()`; si `guardar=True` guardan el PNG en la ruta indicada (modo headless/servidor).

--- 
## 6. Módulo simulacion.py — Procesador de hogares 
### 6.1 `procesar_simulacion_efrd(motor, db_path, tabla_origen, ciclo_id=None)` 
Lee `motor.unidades_convivencia` (ya cargado en memoria) y escribe los resultados individuales en la tabla `resultados_ciudadanos` de `Base_Datos_MACRO.db`. 
**Lógica por hogar:** 
``` 
k_hogar = motor.k_base × phi_total × gamma 
diferencial = renta_total − k_hogar 
si diferencial > 0: 
	x = diferencial / k_hogar 
	tasa = L × (1 − e^(−σ × x)) 
	cuota = diferencial × tasa   → CONTRIBUYENTE 
sino: 
	cuota = diferencial → negativo, es subsidio 
	estado = RECEPTOR o AUDITORÍA 
``` 
**Parámetro `ciclo_id`:** permite ejecuciones históricas múltiples. Si se proporciona, solo se borran las filas del ciclo actual; el histórico de otros ciclos se conserva. 
Si es `None`, se trunca la tabla (ejecución simple). 

**Migración de esquema:** al arrancar comprueba el número de columnas de `resultados_ciudadanos` con `PRAGMA table_info`. Si detecta el esquema antiguo (≠ 10 columnas), lo elimina y lo recrea. Evita errores `sqlite3.OperationalError` en BDs heredadas. 
## 7. Módulo main.py — Orquestador y liquidaciones 
### 7.1 Flujo de ejecución 
``` 
1. Parseo de argumentos CLI (--gop, --modo) 
2. Carga de PIB e IPC desde traductores.py 
3. Instanciación de EFRD_Protocol_v4_1 (calcula k_base, ejecuta protocolos) 4. procesar_simulacion_efrd()    -> tabla resultados_ciudadanos 
4. generar_liquidaciones()       -> Liquidaciones_EFRD.db 
5. EFRD_AnalyticVisualizer       -> 5 gráficas 
``` 
### 7.2 `generar_liquidaciones(path_origen, path_destino)
` 
Agrega `resultados_ciudadanos` por `ref_catastral` y produce la tabla final `liquidaciones_hogares`. 
**Tratamiento semántico de hogares sin renta:** 

| Situación                             | renta_neta_hogar | subsidio_estatal | tipo_efectivo_pct                          |
| ------------------------------------- | ---------------- | ---------------- | ------------------------------------------ |
| Contribuyente $(renta > k_{hogar})$   | $renta-cuota$    | 0                | $\frac{cuota}{bruta}\times 100$            |
| Receptor con $0<renta \leq k_{hogar}$ | $k_hogar$        | $cuota_{hogar}$  | $\frac{cuota}{renta} \cdot 100$ (negativo) |
| Receptor con renta = 0                | $k_hogar$        | $cuota_{hogar}$  | NULL                                       |

El `NULL` en `tipo_efectivo_pct` cuando `renta = 0` es semánticamente correcto: no existe base imponible sobre la que calcular un porcentaje. Un valor `0%` sería engañoso (implicaría que tienen renta y no pagan nada). 
### 7.3 Modo headless 
```bash 
EFRD_HEADLESS=1 python main.py 
``` 
Activa `guardar=True` en todos los métodos gráficos, guardando PNGs en `ejemplos/salida/` en lugar de abrir ventanas. Necesario en servidores sin entorno gráfico o en pipelines automatizados. 

--- 
## 8. Módulo diagnostico.py — Análisis macroeconómico 

Módulo **independiente** del motor. Lee la BD directamente y usa los parámetros del `efrd_config.json` generado en la última ejecución. 
### 8.1 `graficar_diagnostico_comparativo()` 

Figura de 4 paneles que compara la distribución **antes** (salarios brutos) y **después** (salarios netos EFRD) del sistema: 

![[Diagnostico_distrib.png]]

### 8.2 `calcular_analizar_y_graficar_pareto_semilog()` 

Análisis de la cola superior de la distribución de saldos netos: 
- **Alpha de Pareto (α):** estimado por MLE sobre el top `(100 − percentil_cola)%`. Mide la concentración de la riqueza en la cúspide. 
- **Palma Ratio:** masa económica del top `(100 − percentil_cola)%` dividida entre el bottom 40%. > 3.0 indica oligarquía; ≤ 1.2 indica equilibrio. 
- **S80/S20:** ratio entre la masa del quintil superior y la del quintil inferior. 
Interpretación de α: 

| Rango                      | Diagnóstico macroeconómico                                   |
| -------------------------- | ------------------------------------------------------------ |
| $\alpha \gt 2.2$           | Clase media hipertrofiada. $g \gg r$. Sin grandes outliners  |
| $1.5 \leq \alpha \leq 2.2$ | Distribución saludable $r \approx g$                         |
| $1.2 \leq \alpha \lt 1.5$  | Cola pesada. $r \gt g$. Alta concentración en la cúspide     |
| $\alpha \lt 1.2$           | Dominio extremo de mega-ricos. $r \gg g$. Riesgo de colapso. |
Genera también un informe `.txt` en `ejemplos/salida/ingresos_informe_pareto.txt`. 
### 8.3 `graficar_distribucion_saldos()` 

Histograma de frecuencias + boxplot horizontal de los saldos netos reales (filtrando saldos ≤ 0). 
![[Diagnostico_Distribucion_Saldos.png]]

### 8.4 Carga de parámetros 

`_cargar_parametros_sistema(ruta_db)` busca `efrd_config.json` en el mismo directorio que la BD. Si no existe, usa valores por defecto `{k_base: 900, sigma: 1.5, L: 0.60}` con aviso. Esto permite ejecutar `diagnostico.py` de forma autónoma sin necesidad de reinstanciar el motor completo. 

--- 
## 9. Módulo traductores.py — Fuentes de datos externas 

Capa de abstracción entre el motor y las fuentes macroeconómicas externas. Cada función intenta primero la API real (pendiente de implementar) y cae en respaldo auditado si falla. 

| Función                              | Devuelve      | Fuente respaldo     |
| ------------------------------------ | ------------- | ------------------- |
| get_pib_nominal_precios_corrientes() | (año, EUR)    | macro_fallback.json |
| get_IPC_mas_reciente()               | (año, factor) | macro_fallback.json |
| get_renta_mediana()                  | EUR/año       | macro_fallback.json |
Los valores de respaldo se pueden actualizar anualmente editando `datos_referencia/macro_fallback.json` sin tocar el código. 

--- 
## 10. Esquema de bases de datos 
Para información más detallada: ![[conexion/Croquis_base_datos.pdf]]
### 10.1 `Base_Datos_MACRO.db` — tabla `Base_Datos_MACRO
`
Tabla de entrada. Una fila por persona censada. Generada por `conexion/transformador.py`

| Columna       | Tipo         | Descripción                                    |
| ------------- | ------------ | ---------------------------------------------- |
| dni_nie_nif   | str (TEXT)   | Identificador único de la persona              |
| ref_catastral | str (TEXT)   | Referencia de la vivienda (puede ser virtual)  |
| renta_mensual | float (REAL) | Renta mensual declarada en EUR                 |
| phi           | float (REAL) | Aportación de esta persona al $\phi$ del hogar |
| gamma         | float (REAL) | Índice de coste de vida del municipio          |

### 10.2 `Base_Datos_MACRO.db` — tabla `resultados_ciudadanos` 

 Tabla de resultados individuales. Generada por `simulacion.py`. Una fila por hogar (agrupación de `ref_catastral`). 
 
| Columna       | Tipo         | Descripción                                                     |
| ------------- | ------------ | --------------------------------------------------------------- |
| ciclo_id      | str (TEXT)   | Identificador del ciclo de ejecución (NULL en ejecución simple) |
| ref_catastral | str (TEXT)   | Referencia catastral del hogar                                  |
| renta_total   | float (REAL) | Suma de rentas de todos los miembros                            |
| phi_total     | float (REAL) | $\phi$ agregado del hogar                                       |
| gamma         | float (REAL) | $\gamma$ del municipio                                          |
| k_hogar       | float (REAL) | Umbral de dignidad calculado                                    |
| cuota         | float (REAL) | Importe fiscal (>0 si contribuyente, <0 si receptor)            |
| neto          | float (REAL) | Renta neta disponible                                           |
| tipo_efectivo | float (REAL) | Porcentaje efectivo sobre renta                                 |
| estado        | str (TEXT)   | CONTRIBUYENTE, RECEPTOR o AUDITORÍA                             |
### 10.3 `Liquidaciones_EFRD.db` — tabla `liquidaciones_hogares` 

Tabla de salida final. Una fila por hogar. Generada por `main.py`. 

| Columna           | Tipo         | Descripción                                                   |
| ----------------- | ------------ | ------------------------------------------------------------- |
| ref_catastral     | str (TEXT    | Referencia catastral                                          |
| renta_bruta_hogar | float (REAL) | Renta propia del hogar ($\geq$ 0)                             |
| cuota_hogar       | float (REAL) | A ingresar ($\gt 0$) o a recibir ($\lt 0$) en €/mes           |
| renta_neta_hogar  | float (REAL) | Renta disponible tras cuota (0 si $bruta=0$)                  |
| subsidio_estatal  | float (REAL) | Aportación del estado cuando $bruta=0$                        |
| tipo_efectivo_pct | float (REAL) | $\frac{cuota}{bruta}\cdot 100$; NULL si no hay base imponible |
| estado_hogar      | str (TEXT)   | CONTRIBUYENTE o RECEPTOR o AUDITORÍA o NEUTRO                 |
| phi_total         | float (REAL) | Factor de composición familiar del hogar                      |
| gamma             | float (REAL) | Índice de coste de vida del municipio                         |

## 11. Parámetros de configuración 
### Parámetros del motor (configurados en `main.py`) 

| Parámetro | Valor por defecto | Impacto                                                                                                     |
| --------- | ----------------- | ----------------------------------------------------------------------------------------------------------- |
| Alpha     | 0.05              | Fracción del PIB per cápita para k_base. Subir $\alpha$ implica más subsidios y, por ende, más carga fiscal |
| Gini      | 0.33              | Desigualdad estructural. Solo modifica k_base en el arranque                                                |
| Sigma     | 1.5               | Velocidad de progresividad. $\sigma$ alto implica que los contribuyentes de renta media paguen más          |
| Limite_L  | 0.6               | Techo de la tasa efectiva. Nadie paga más del 60% aunque tenga renta infinita                               |
| IPC_Pi    | 1.034             | Factor de inflación. Sube k_base para mantener poder adquisitivo                                            |

### Constantes de `simulacion.py` 

| Constante               | Valor                           | Descripción                                                                |
| ----------------------- | ------------------------------- | -------------------------------------------------------------------------- |
| UMBRAL_GAMMA_SOSPECHOSO | 1.3                             | $\gamma$ por encima del cual se sospecha fraude si la renta es cero        |
| UMBRAL_RENTA_CERO       | 100 €/mes                       | Renta por debajo de la cual se considera declaración cero                  |
| PREFIJOS_REF_VIRTUAL    | VIRTUAL_, SIN_REF, TEST_, MOCK_ | Prefijos de refs. catastrales sintéticas, excluidas del detector de fraude |

### Constantes de `EFRD.py` 

| Constante              | Valor | Descripción                                                      |
| ---------------------- | ----- | ---------------------------------------------------------------- |
| RATIO_MASA_CRITICA_MIN | 0.40  | Mínimo de hogares contribuyentes para sostenibilidad estructural |

---
## 12. Protocolos de emergencia 

El motor ejecuta dos protocolos en secuencia al arrancar. 
### Protocolo de Solvencia 
**Condición de disparo:** `recaudación − subsidios − G_op < 0` 
**Opciones:** 
1. **Deuda pública** — mantiene k_base, asume el déficit vía endeudamiento soberano.
2. **Ajuste fiscal** — reduce k_base al mínimo solvente mediante búsqueda binaria (100 iteraciones). 
**Modos de resolución automática** (argumento `--modo`): 
- `interactivo` → pregunta al operador por consola .
- `deuda` → elige opción 1 automáticamente .
- `ajuste` → elige opción 2 automáticamente .
- `test` → elige opción 2 sin imprimir (para pipelines de test) .
### Protocolo PSD (Protocolo de Suelo de Dignidad) 
**Condición de disparo:** `k_base < k_arope` (suelo por debajo del umbral europeo de pobreza) 

**Condición de bloqueo:** no se puede activar si el Protocolo de Solvencia ya redujo k_base. 

**Comportamiento:** solo se activa en modo `interactivo`. En modos automáticos, la política es conservadora (no se aumenta el gasto sin intervención humana explícita). 

## 13. Ejecución y argumentos CLI 
### `main.py` 
```bash 
python main.py [--gop VALOR_EUR] [--modo {interactivo,deuda,ajuste,test}] 
# Ejemplos: 
python main.py # ejecución interactiva, G_op = 0 
python main.py --gop 5000000000 # con gastos operativos del Estado 
python main.py --modo ajuste # resolución automática de insolvencia 
python main.py --modo test # para pipelines automatizados 

# Modo headless (sin GUI): 
EFRD_HEADLESS=1 python main.py --modo test 
``` 
### `diagnostico.py` 
```bash 
python diagnostico.py [--db RUTA] [--tabla NOMBRE] [--percentil-cola N] [--headless] 
# Ejemplos: 
python diagnostico.py # usa rutas por defecto 
python diagnostico.py --headless # guarda PNGs, no muestra ventanas 
python diagnostico.py --percentil-cola 95 # analiza el top 5% en lugar del top 10% 
python diagnostico.py --db /ruta/custom.db --tabla MiTabla 
``` 
--- 

## 14. FAQs
### ¿Se suma $k_{base}$ con $k_{hogar}$?
No. Hacerlo sería un error de duplicidad muy apreciable que quebraría el sistema en la primera iteración. 
La relación es de jerarquía y transformación, no de suma:
- $k_{base}$ es la constante teórica (la "base" de dignidad). Es lo que le correspondería a un adulto solo en una zona de coste de vida neutro ($\gamma=1.0$).
- $k_{hogar}$ es el $k_{base}$ ya procesado por las circunstancias del ciudadano. Es el umbral final que el motor usa para calcular la cuota $C$

La fórmula que transforma $k_{base}$ en $k_{hogar}$ es: $$k_{hogar}=k_{base}\cdot\phi\cdot\gamma$$
Donde se puede visualizar que tanto $\phi$ (circunstancias familiares del hogar) y $\gamma$ (coste de vida del lugar donde se habita) son directamente proporcionales a $k_{base}$

Entonces, ejemplificando la respuesta: Un sin hogar que gane 0€ se le donará un $k_{hogar}$ correspondiente a sus circunstancias.
## 16. Anexo matemático

En el análisis gráfico que se visualiza en el siguiente [link](https://www.desmos.com/calculator/8nxnfzbpfo?lang=es) se observa que pasado un valor de variable $\sigma$, la gráfica tiene una bajada (la derivada es 0), esto implicaría que alguien acabaría perdiendo más dinero en neto si gana más en bruto pasado un punto. Para esto extraeremos la derivada de $n$, definida como 

$$n=x-(x-k_{hogar})L(1-e^{(-s||\frac{x-k_hogar}{k_{hogar}}|)})$$

### Derivada de $n(x)$:
Y su derivada es definida por la expresión:

$$\frac{dn}{dx}\equiv n'=1-L\left(1-e^{\left(-\sigma |\frac{x-k_hogar}{k_{hogar}}|\right)}\right)-(x-k_{hogar})L \left( \frac{\sigma(x-k_{hogar})}{k_{hogar}|x-k_{hogar}|}e^{\left(-\sigma|\frac{x-k_hogar}{k_{hogar}}|\right)} \right)$$


#### Despejando para $L$:

$$n'\leq0 \therefore 0\geq{1-L\left(1-e^{\left(-\sigma |\frac{x-k_hogar}{k_{hogar}}|\right)}\right)-(x-k_{hogar})L \left( \frac{\sigma(x-k_{hogar})}{k_{hogar}|x-k_{hogar}|}e^{\left(-\sigma|\frac{x-k_hogar}{k_{hogar}}|\right)} \right)}$$

$$\text{ergo,} \space\space\space L\geq {\frac{1}{\left(1-e^{\left(-\sigma |\frac{x-k_hogar}{k_{hogar}}|\right)}\right)-(x-k_{hogar}) \left( \frac{\sigma(x-k_{hogar})}{k_{hogar}|x-k_{hogar}|}e^{\left(-\sigma|\frac{x-k_hogar}{k_{hogar}}|\right)} \right)}} \space\space\space\square$$


## 17. Glosario de términos 

| Término                | Definición                                                                                                                            |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| k_base                 | Sueldo vitalicio base individual. Importe mensual mínimo garantizado.                                                                 |
| k_hogar                | Umbral de dignidad específico del hogar: $k_{base} \cdot \phi \cdot \gamma$                                                           |
| $\phi$ (phi)           | Multiplicador de composición familiar. Escala k_base según el número de miembros y características.                                   |
| $\gamma$ (gamma)       | Índice de coste de vida municipal derivado del catastro.                                                                              |
| $\sigma$ (sigma)       | Velocidad de progresividad de la cuota. Controla cuán rápido sube la tasa hacia el techo L.                                           |
| L                      | Límite asintótico de la tasa efectiva. Garantiza que nadie pierde más del $L\cdot 100$% de su renta.                                  |
| $\alpha$ (alpha)       | Fracción del PIB per cápita destinada a financiar el suelo vitalicio.                                                                 |
| AROPE                  | *At Risk Of Poverty or Exclusion*. Umbral europeo de pobreza: 60% de la renta mediana nacional.                                       |
| Palma Ratio            | Cociente entre la masa económica del top X% y el bottom 40%. Indicador de desigualdad estructural                                     |
| Alpha Pareto           | Exponente de la ley de potencias en la cola de distribución. $\alpha > 2$ = clase media dominante; $\alpha < 1.2$ = oligarquía.       |
| S80/S20                | Ratio entre la renta del quintil superior y el inferior.                                                                              |
| Masa crítica           | Porcentaje mínimo de de contribuyentes necesarios para que el sistema sea autosostenible sin deuda permanente.                        |
| Protocolo PSD          | Protocolo de Suelo de Dignidad. Mecanismo para elevar k_base hasta el umbral AROPE cuando el presupuesto lo permite.                  |
| Modo headless          | Ejecución sin interfaz gráfica. Las figuras se guardan como PNG en lugar de mostrarse en pantalla                                     |
| ciclo_id               | Identificador de ejecución para soporte multicíclo. Permite conservar histórico de varias simulaciones en la misma BD.                |
| Ref. catastral virtual | Referencia sintética (prefijos VIRTUAL_, TEST_, etc. ) usada para hogares sin domicilio catastrable. Excluida del detector de fraude. |

## 18. Téngase en cuenta

Los datos de entrada han de actualizarse anualmente, tales como el índice Gini y el IPC. Además, es importante que el PIB sea lo más reciente posible.

Para visualizar más detalles, entre en 'Documentacion/propuesta técnica.md'
## 19. Véase también
El gráfico que describe este sistema: [link](https://www.desmos.com/calculator/8nxnfzbpfo?lang=es)
## 19. Licencia
Este -ambicioso- proyecto está bajo la licencia **GNU General Public License v3.0 (GPL-3.0)**. Esto garantiza que el algoritmo permanezca abierto, auditable y que cualquier cambio o mejora sea compartida y de libre acceso con la comunidad. Esto garantiza esa "Caja de Cristal", es decir, garantiza que la transparencia se mantenga aún habiendo realizado cambios.
