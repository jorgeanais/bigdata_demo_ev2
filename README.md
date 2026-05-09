# bigdata_demo_ev2

Demostración de como utilizar GC (Preparación Evaluación 2)

> Profesor Jorge Anais  
> Big Data

## Contexto

## Instrucciones

### Configuración del Entorno Python

1. Crea un entorno virtual:
   ```bash
   python -m venv venv
   ```
2. Activa el entorno virtual:
   - En Linux/Mac: `source venv/bin/activate`
   - En Windows: `venv\Scripts\activate`
3. Instala las dependencias necesarias:
   ```bash
   pip install -r requirements.txt
   ```
4. Ejecuta el recolector de datos:
   ```bash
   python resources/bus_data_collector.py
   ```

## Resultados esperados

1. **Datos Recolectados**: El script `bus_data_collector.py` generará un archivo Parquet (ej. `data/buses_YYYY-MM-DD.parquet`) que almacena de forma particionada la información de coordenadas y velocidades de los buses.
2. **Exploración de Datos (EDA)**: Se incluye un cuaderno interactivo (`explore_buses_data.ipynb`) que analiza la distribución de velocidades, rutas y operadores.
3. **Scripts de Visualización Espacial y Animación**: En la carpeta `resources/` se incluyeron scripts (`plot_trajectories.py`, `visualize_traffic.py`, `animate_buses.py`) que permiten proyectar coordenadas GPS en mapas reales y generar animaciones temporales del movimiento de los buses.

## Visualizaciones

### 1. Trayectorias de Buses por Operador
Muestra el trazado de los buses coloreados por el operador del servicio, eliminando coordenadas inválidas y usando Web Mercator para sobreponer los datos en un mapa callejero (OpenStreetMap).

![Trayectorias de Buses](images/bus_trajectories.png)

### 2. Zonas de Congestión (Velocidad Promedio Hexbin)
Este mapa agrupa los registros GPS en hexágonos para visualizar las zonas geográficas con menores velocidades promedio.

![Zonas de Congestión Hexbin](images/traffic_hexbin_map.png)

### 3. Animación de Movimiento de Buses
Animación temporal del recorrido de los buses a lo largo del mapa, diferenciados por color según su operador.

![Animación de Buses](resources/bus_animation.gif)
