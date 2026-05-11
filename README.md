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

### Descarga de Datos

Debido a que los datos de prueba son muy grandes para alojarlos directamente en GitHub, hemos preparado un script para descargarlos desde Dropbox.

Ejecuta el siguiente comando para descargar los archivos Parquet de los días 08, 09 y 10 de Mayo dentro de la carpeta `data/`:
```bash
python resources/download_data.py
```
*(Alternativa: Puedes descargar los archivos manualmente y guardarlos en la carpeta `data/` con sus nombres respectivos:*
* *[Datos del 2026-05-08](https://www.dropbox.com/scl/fi/qn1g0s829dol4zu6p5gfh/buses_2026-05-08.parquet?rlkey=1q64fcvqrx6bkbzypqh0ywnro&st=rtfbkfzt&dl=0)*
* *[Datos del 2026-05-09](https://www.dropbox.com/scl/fi/wpebtr0gxkzulfv2xlqd0/buses_2026-05-09.parquet?rlkey=p4vnwwrhs5pwt0eovk4f0ebpe&st=19sjym4s&dl=0)*
* *[Datos del 2026-05-10](https://www.dropbox.com/scl/fi/jnqofxndeesqx2v1c7cua/buses_2026-05-10.parquet?rlkey=lt9ycse4o3i0hsqbxz8acqrnn&st=wbgoe6ty&dl=0))*

### (Opcional) Recolectar tus propios datos

Si deseas recolectar nuevos datos en tiempo real, puedes ejecutar el recolector de datos:
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
