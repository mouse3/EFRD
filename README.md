# EFRD (Equilibrio Fiscal Y Resiliencia Distributiva)
El EFRD es un sistema fiscal algorítmico que sustituye los tramos del IRPF por una curva continua. Calcula un Sueldo Vitalicio mínimo de manera automática según el PIB, la inflación, etc. Ajusta la ayuda por carga familiar (OCDE) y garantiza solvencia mediante inecuaciones de déficit cero, eliminando la burocracia política de manera algorítmica.

## Conceptos Clave
El sistema se basa en la **Caja de Cristal**: transparencia total y automatización mediante variables macroeconómicas públicas

| Variable | Definición                        | Rango Operativo                |
| -------- | --------------------------------- | ------------------------------ |
| $Y$      | PIB Nominal (Riqueza Nacional)    | Real (INE)                     |
| $G$      | Coeficiente de Gini (desigualdad) | 0.00 - 1.00                    |
| $\alpha$ | Coeficiente de Bienestar          | 0.30 - 0.50                    |
| $L$      | Límite Fiscal (Techo)             | 0.45 - 0.70, recomendable 0.60 |
| $\pi$    | Factor de Ajuste IPC              | 0.80 - 1.20                    |

### Variables del Sistema.
### Factor Familiar $\phi$ (Escala OCDE Modificada).
El umbral de dignidad $k$ se ajusta según la unidad de convivencia $\phi$:
- **1.0**: Primer adulto.
- **0.5**: Segundo adulto / Familiar extra (sea o no contribuyente).
- **0.3**: Por cada hijo/menor.

## Arquitectura Matemática
#### Sueldo Vitalicio Real ($K_{base}$)
Basado en la Renta de Bienestar de Sen para evitar sesgos de medias aritméticas: $$k_{base}=\alpha \cdot \left( \frac{Y}{N}\cdot(1-G)\right) \cdot \pi$$
#### Cuota Líquida (C)
El dinero que mueve el ciudadano al gob. o viceversa. 
$$C=(B-k_{hogar})\cdot L \cdot (1-e^{-\sigma\cdot|x|})$$
Si $C>0$, el ciudadano hace una transferencia al gobierno, lo que se conoce comúnmente como IRPF.
Y, Si $C<0$, el ciudadano recibe dinero del estado para llegar a la cantidad de $k_{base}$ en bruto.

## Inecuaciones de Seguridad
El motor incluye 3 capas de protección contra el colapso financiero:
1. La **Solvencia**: $\sum C_{pos}\ge \sum |C_neg| + G_{op}$
2. La **Masa Crítica**: Ratio mínimo de contribuyentes activos necesarios.
3. El **Incentivo Laboral**: La derivada de la renta debe ser siempre positiva.

## Pruebas (sección bajo actualizaciones).
Se ha agregado un stress test por medio de las cadenas de Markov, ver el documento 'Analisis_tecnico.md' y 'Markov.ipynb' de la carpeta "Analisis-Cadenas_Markov" para más información.

## Licencia
Este -ambicioso- proyecto está bajo la licencia **GNU General Public License v3.0 (GPL-3.0)**. Esto garantiza que el algoritmo permanezca abierto, auditable y que cualquier cambio o mejora sea compartida y de libre acceso con la comunidad. Esto garantiza esa "Caja de Cristal", es decir, garantiza que la transparencia se mantenga aún habiendo realizado cambios.
