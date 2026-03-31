**Sistema de Equilibrio Fiscal y Redistribución Dinámica**

## 1. Naturaleza del Sistema (¿Qué es?)

El Protocolo EFRD v3.2 es el "Sistema Operativo" de la Hacienda Pública del siglo XXI. Sustituye el actual modelo de IRPF por tramos y subsidios burocráticos por una **función matemática continua y automatizada**.

Su objetivo principal es separar la soberanía política (que decide los objetivos de bienestar) de la ejecución técnica (que garantiza la solvencia matemática del Estado). El sistema asegura que ningún ciudadano caiga por debajo del umbral de la pobreza real, que siempre haya incentivo para trabajar y que el Estado jamás asuma compromisos financieros que no pueda pagar.

---

## 2. El Panel de Control: Variables y Rangos Operativos

El sistema es una "caja de cristal". No hay variables ocultas. Se divide estrictamente en datos de la economía real (auditables) y palancas políticas (decididas en el Parlamento).

### A. Datos de Realidad (No manipulables por el Gobierno)

- **$Y$ (Renta Nacional Nominal):** La riqueza total producida (PIB).
    
- **$N$ (Población Activa/Beneficiaria):** El divisor demográfico.
    
- **$G$ (Coeficiente de Gini) [Rango histórico 0.30 - 0.35]:** Mide la desigualdad. Evita que el sistema calcule el bienestar basándose en medias aritméticas engañosas infladas por rentas ultra-altas.
    
- **$\pi$ (Ajuste de Precios/IPC) [Rango 0.80 - 1.20]:** Protege el poder adquisitivo frente a la inflación.
    
- **$B$ (Base Imponible):** Ingresos brutos del hogar detectados por la AEAT.
    

### B. Palancas Políticas (El Debate Parlamentario)

- **$\alpha$ (Coeficiente de Bienestar) [Rango 0.30 - 0.50]:** Porcentaje de la riqueza nacional que la sociedad decide garantizar como "suelo" mínimo a cada ciudadano.
    
- **$L$ (Límite Fiscal) [Rango 0.45 - 0.65]:** El techo asintótico. El porcentaje máximo de impuestos que un ciudadano pagará, por infinitos que sean sus ingresos, para evitar la confiscatoriedad.
    
- **$\sigma$ (Progresividad) [Rango 0.50 - 1.20]:** La velocidad a la que la clase media y alta alcanza el límite $L$.
    

---

## 3. El Motor de Cálculo (Las Ecuaciones Principales)

El algoritmo ejecuta tres pasos secuenciales para cada unidad de convivencia:

### Paso 1: El Sueldo Vitalicio Base ($k_{base}$)

Define el umbral de dignidad individual adaptado a la economía real y distribuida:

$$k_{base} = \alpha \cdot \left( \frac{Y}{N} \cdot (1 - G) \right) \cdot \pi$$

_Lógica: Si el PIB ($Y$) cae, el suelo baja para proteger al Estado. Si la desigualdad ($G$) sube, el suelo se ajusta a la renta de la mayoría. Si hay inflación ($\pi$), el suelo sube para que la gente pueda seguir comiendo._

### Paso 2: El Ajuste por Unidad Familiar ($k_{hogar}$)

El sistema agrupa los ingresos del hogar ($B_{total}$) y calcula su necesidad real basándose en las **Escalas de Equivalencia de la OCDE**, que miden las economías de escala (compartir alquiler, luz, etc.):

$$k_{hogar} = k_{base} \cdot \phi$$

Donde $\phi$ es la suma de los miembros:

- **1.0** para el primer adulto (sustentador principal).
    
- **0.5** para el segundo adulto (cónyuge o familiar conviviendo).
    
- **0.3** por cada menor a cargo.
    
    _Ejemplo: Una pareja con un hijo tiene un $\phi = 1.8$. Su "suelo protegido" es casi el doble que el de un soltero, premiando y protegiendo la estabilidad familiar, independientemente de si ambos padres trabajan._
    

### Paso 3: La Cuota Líquida de Transferencia ($C$)

El cruce definitivo entre lo que la familia ingresa ($B_{total}$) y lo que necesita ($k_{hogar}$):

$$C = (B_{total} - k_{hogar}) \cdot L \cdot (1 - e^{-\sigma \cdot \left| \frac{B_{total} - k_{hogar}}{k_{hogar}} \right|})$$

- **Si $C$ es negativo:** La familia está por debajo de su suelo. El Estado les transfiere automáticamente la diferencia. (Sustituye al IMV y al paro, sin burocracia).
    
- **Si $C$ es positivo:** La familia supera su suelo. Pagan impuestos de forma progresiva, frenando suavemente al acercarse al límite $L$.
    

---

## 4. Las Válvulas de Seguridad (Blindaje Sistémico)

El EFRD v3.2 incluye sensores matemáticos que impiden la quiebra del país y el fraude:

1. **Condición de Solvencia (Déficit Cero Garantizado):**
    
    $$\sum C_{pos} \ge \sum |C_{neg}| + G_{op}$$
    
    _El sistema audita que la suma de los impuestos recaudados cubra siempre los subsidios entregados y el gasto operativo del Estado ($G_{op}$). Si no cuadra, exige un ajuste del parámetro $\sigma$ o $\alpha$._
    
2. **Garantía de Incentivo Laboral (La Derivada Positiva):**
    
    $$\frac{d(B_{total} - C)}{dB_{total}} > 0$$
    
    _Matemáticamente, prohíbe los "saltos de tramo". Ganar un euro bruto extra siempre, en el 100% de los casos, significa tener más dinero neto en el bolsillo._