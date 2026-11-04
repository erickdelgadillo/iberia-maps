# Datos locales y cobertura

El programa no modifica los archivos fuente. Las rutas de los ejemplos suponen el paquete `iberia-maps-data` en una carpeta hermana del repositorio.

| Archivo del paquete | Uso y cobertura |
| --- | --- |
| `batimetria/vigo_resolucion_original_LAT.nc` | Vigo y entorno, aproximadamente −9.022…−8.553°, 42.084…42.385°. Malla original EMODnet 1/16 de minuto de arco. |
| `batimetria/base_peninsula_baleares_ceuta_melilla_4x_LAT.nc` | Marco −10.5…5°, 34…45°. Malla submuestreada a 1/4 de minuto de arco; no toda la ZEE. |
| `batimetria/base_canarias_4x_LAT.nc` | Marco −19…−12.5°, 26.5…30.5°, misma malla general. |
| `costa/costa_pleamar_espana.geojson` | Costa nacional de pleamar del IHM: 39.448 segmentos. |
| `relieve/peninsula_baleares_ceuta_melilla_MDT200_remuestreado.tif` | Fuente MDT200, remuestreada por el servidor en grados a aproximadamente 280–315 m E-O y 305 m N-S. |
| `relieve/canarias_MDT200.tif` | MDT200 de Canarias en EPSG:4083, malla de 200 m. |

Estas coberturas pueden tener huecos. La malla de la batimetría no equivale a precisión de un levantamiento. El relieve español no garantiza cubrir Portugal o Francia.

## Obtener o ampliar las capas

- [EMODnet Bathymetry](https://emodnet.ec.europa.eu/en/bathymetry): escoger datos de elevación/profundidad en NetCDF, no una imagen de colores. [Formulario de recorte de la malla 2024](https://erddap.emodnet.eu/erddap/griddap/bathymetry_dtm_2024.html). El servicio usado en los ejemplos declara LAT.
- [Línea de costa IHM/CNIG](https://centrodedescargas.cnig.es/CentroDescargas/linea-costa): se puede convertir a GeoJSON WGS84 en QGIS, conservando las partes del Shapefile y sus metadatos.
- [Modelos digitales del terreno IGN/CNIG](https://centrodedescargas.cnig.es/CentroDescargas/modelos-digitales-elevaciones): MDT25 o MDT05 por zonas para más detalle terrestre. Escoger MDT, no MDS, si se quiere el terreno.
- [MBAR del IHM](https://cdihm.cnig.es/CentroDescargasIHM/home): datos de detalle según cobertura; exige cuenta. BAG no es una entrada directa de esta versión y debe convertirse previamente.

Descarga solo la zona necesaria, conserva los metadatos y configura la ruta correspondiente. Para Canarias selecciona sus archivos de batimetría y relieve, no los peninsulares.

## Compatibilidad científica

- Las coordenadas de estaciones se interpretan como geográficas WGS84 (EPSG:4326). Transforma previamente coordenadas UTM u otros datums.
- La costa y el raster marino se dibujan por separado: no se ajustan los puntos ni se inventan profundidades para rellenar huecos.
- LAT y altitud terrestre no son un único datum vertical. Esta versión muestra las capas con escalas separadas; no produce un modelo topobatimétrico fusionado.
- El código y los datos tienen condiciones de reutilización distintas. Conservar las condiciones de cada proveedor y las atribuciones IGN/CNIG, IHM y EMODnet; no asumir una licencia única para todos los archivos.

No se incluye el paquete grande de datos en este repositorio ni se publica aquí material del artículo o de la tesis.
