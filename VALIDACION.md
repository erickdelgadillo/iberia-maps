# Validación de la versión 0.1.0

- Python 3.12.16 en Linux.
- NumPy 2.5.4, Matplotlib 3.11.2, netCDF4 1.7.5.1.post1, Rasterio 1.5.2.
- `python -m pytest -q`: **16 pruebas superadas**.
- `python -m pip check`: sin dependencias rotas.
- Ejemplos reales de Vigo, Galicia y Canarias exportados a PNG/PDF; revisión visual de la costa, las leyendas, el relieve y los puntos.
- Se comprobó el lanzador `crear_mapa.sh` con la instalación local del paquete.
- La estación central se registra en 42.23483333333333, −8.786333333333333, sin desplazamiento gráfico.

Los datos y las salidas de trabajo no se incluyen en Git. La imagen pequeña del README es una muestra generada por el propio programa, con atribución a los proveedores. La prueba no certifica precisión geodésica de las capas; se conservan sus referencias y limitaciones en DATOS.md.
