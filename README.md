### Tácticas implementadas

## 5. Resultados esperados

| Métrica | Valor esperado | Relación con el ASR |
|---------|---------------|---------------------|
| **Tasa de éxito** | 100% | El ASR exige explícitamente un 100% de éxito en todas las peticiones realizadas. |
| **Tasa de errores** | 0% | Cualquier error HTTP representa un incumplimiento directo del ASR. |
| **Tiempo de respuesta promedio** | Entre 4 ms y 200 ms | El tiempo incluye posibles reintentos ocasionales; el rango refleja el comportamiento esperado del backoff exponencial en condiciones normales de fallo (10%). |
| **Agnósticismo (AWS vs GCP)** | Tasa de éxito idéntica en ambos proveedores | El ASR exige captura agnóstica: si el Patrón Strategy funciona correctamente, el resultado no debe variar entre proveedor AWS y GCP. |
