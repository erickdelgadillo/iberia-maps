"""Recortes locales. Nunca interpreta automáticamente un hueco como tierra."""
import json
import math
from pathlib import Path
import numpy as np
from netCDF4 import Dataset


def bounds(cfg):
    m = cfg['mapa']
    return m['oeste'], m['este'], m['sur'], m['norte']


def bathymetry(path, box):
    w, e, s, n = box
    with Dataset(path) as ds:
        for key in ('longitude', 'latitude', 'elevation'):
            if key not in ds.variables:
                raise ValueError(f'El NetCDF necesita la variable {key}.')
        x = np.asarray(ds['longitude'][:]); y = np.asarray(ds['latitude'][:])
        if x.ndim != 1 or y.ndim != 1 or len(x) < 2 or len(y) < 2:
            raise ValueError('Se necesita una malla regular con longitude/latitude de una dimensión.')
        if not np.all(np.diff(x) > 0) or not np.all(np.diff(y) > 0):
            raise ValueError('Las coordenadas NetCDF deben estar ordenadas de menor a mayor.')
        if ds['elevation'].dimensions != ('latitude', 'longitude'):
            raise ValueError('elevation debe tener dimensiones (latitude, longitude).')
        ix = np.where((x >= w - np.diff(x).max()) & (x <= e + np.diff(x).max()))[0]
        iy = np.where((y >= s - np.diff(y).max()) & (y <= n + np.diff(y).max()))[0]
        if len(ix) < 2 or len(iy) < 2:
            raise ValueError('La batimetría no cubre esta zona. Selecciona otro NetCDF.')
        # Límite de memoria para vistas muy amplias a resolución alta.
        stride = max(1, math.ceil(math.sqrt(len(ix) * len(iy) / 2_000_000)))
        z = ds['elevation'][iy[0]:iy[-1]+1:stride, ix[0]:ix[-1]+1:stride]
        z = np.ma.masked_invalid(z); z = np.ma.masked_where(z > 0, z)
        if z.count() == 0:
            raise ValueError('No hay profundidades válidas en la región seleccionada.')
        units = getattr(ds['elevation'], 'units', '')
        if units not in ('m', 'metres', 'meters'):
            raise ValueError(f'Unidades de profundidad no admitidas: {units!r}; se requieren metros.')
        label = getattr(ds['elevation'], 'long_name', '')
        datum = 'LAT' if 'lowest astronomical tide' in label.lower() else ('MSL' if 'mean sea level' in label.lower() else 'referencia no identificada')
        return x[ix[0]:ix[-1]+1:stride], y[iy[0]:iy[-1]+1:stride], z, {
            'archivo': str(path), 'referencia_vertical': datum, 'resolucion_grados': [float(np.diff(x).mean()), float(np.diff(y).mean())],
            'submuestreo_visual': stride, 'cobertura_completa': bool(w >= x[0] - np.diff(x).mean()/2 and e <= x[-1] + np.diff(x).mean()/2 and s >= y[0] - np.diff(y).mean()/2 and n <= y[-1] + np.diff(y).mean()/2),
        }


def coast(path, box):
    w, e, s, n = box
    with Path(path).open(encoding='utf-8') as f:
        obj = json.load(f)
    if obj.get('type') != 'FeatureCollection':
        raise ValueError('La costa debe ser un GeoJSON FeatureCollection en longitud/latitud WGS84.')
    if 'crs' in obj and obj['crs'].get('properties', {}).get('name') not in ('urn:ogc:def:crs:OGC:1.3:CRS84', 'EPSG:4326'):
        raise ValueError('Reproyecta la costa a WGS84 antes de usarla.')
    def lines(g):
        if g['type'] == 'LineString':
            yield g['coordinates']
        elif g['type'] == 'MultiLineString':
            yield from g['coordinates']
        elif g['type'] == 'Polygon':
            yield from g['coordinates']
        elif g['type'] == 'MultiPolygon':
            for poly in g['coordinates']:
                yield from poly
        elif g['type'] == 'GeometryCollection':
            for child in g['geometries']:
                yield from lines(child)
    result = []
    for f in obj['features']:
        if not f.get('geometry'):
            continue
        for line in lines(f['geometry']):
            a = np.asarray(line, dtype=float)
            if a.ndim != 2 or a.shape[1] < 2 or len(a) < 2:
                continue
            a = a[:, :2]
            if not np.isfinite(a).all() or np.max(np.abs(a[:, 0])) > 180 or np.max(np.abs(a[:, 1])) > 90:
                raise ValueError('La costa contiene coordenadas inválidas o proyectadas; se requiere longitud/latitud.')
            if a[:,0].max() >= w and a[:,0].min() <= e and a[:,1].max() >= s and a[:,1].min() <= n:
                result.append(a)
    return result


def terrain(path, box):
    import rasterio
    from rasterio.warp import calculate_default_transform, reproject, Resampling, transform_bounds
    from rasterio.windows import from_bounds, Window
    w, e, s, n = box
    with rasterio.open(path) as src:
        if src.crs is None:
            raise ValueError('El GeoTIFF de relieve no declara su sistema de coordenadas.')
        b = transform_bounds('EPSG:4326', src.crs, w, s, e, n, densify_pts=21)
        win = from_bounds(*b, src.transform).round_offsets().round_lengths()
        try:
            win = win.intersection(Window(0, 0, src.width, src.height))
        except rasterio.errors.WindowError:
            raise ValueError('El relieve no intersecta la zona del mapa.') from None
        scale = min(1, 1600 / max(win.width, win.height))
        h, width = max(1, round(win.height*scale)), max(1, round(win.width*scale))
        arr = src.read(1, window=win, out_shape=(h, width), masked=True).astype(float)
        base = src.window_transform(win)
        scaling = rasterio.Affine.scale(win.width/width, win.height/h)
        src_transform = base @ scaling if hasattr(base, '__matmul__') else base * scaling
        bb = rasterio.transform.array_bounds(h, width, src_transform)
        trans, dst_w, dst_h = calculate_default_transform(src.crs, 'EPSG:4326', width, h, *bb)
        out = np.full((dst_h, dst_w), np.nan)
        reproject(arr.filled(np.nan), out, src_transform=src_transform, src_crs=src.crs, src_nodata=np.nan,
                  dst_transform=trans, dst_crs='EPSG:4326', dst_nodata=np.nan, resampling=Resampling.bilinear)
        # Estos MDT regionales contienen ceros fuera de cobertura/mar.
        # No se usan para inferir costa ni se representa altitud <= 0.
        out = np.ma.masked_where(~np.isfinite(out) | (out <= 0), out)
        xx = trans.c + (np.arange(dst_w)+.5)*trans.a
        yy = trans.f + (np.arange(dst_h)+.5)*trans.e
        return xx, yy, out, {'archivo': str(path), 'crs_origen': str(src.crs), 'cotas_no_representadas': '<= 0 m y valores ausentes'}


def automatic_file(root, layer, box):
    """Selecciona archivos locales que cubran la zona; no descarga ni modifica datos."""
    root = Path(root)
    w,e,s,n = box
    if layer == 'costa':
        candidates = sorted((root/'costa').glob('*.geojson'))
        preferred = root/'costa/costa_pleamar_espana.geojson'
        if preferred.is_file():return preferred
        if len(candidates) == 1:return candidates[0]
        raise ValueError('No encuentro una costa GeoJSON única. Indica datos.costa explícitamente.')
    if layer == 'batimetria':
        choices=[]
        for path in sorted((root/'batimetria').rglob('*.nc')):
            try:
                with Dataset(path) as d:
                    if 'elevation' not in d.variables:continue
                    x=np.asarray(d['longitude'][:]);y=np.asarray(d['latitude'][:])
                    if len(x)<2 or len(y)<2:continue
                    dx=float(np.diff(x).mean());dy=float(np.diff(y).mean())
                    if dx<=0 or dy<=0:continue
                    if w>=x[0]-dx/2 and e<=x[-1]+dx/2 and s>=y[0]-dy/2 and n<=y[-1]+dy/2:
                        choices.append((dx*dy,str(path),path))
            except (OSError, KeyError, ValueError, IndexError):
                continue
        if choices:return min(choices)[2]
        raise ValueError('Ningún NetCDF local cubre todo el marco. Reduce los límites o añade la batimetría de esa región.')
    if layer == 'relieve':
        import rasterio
        from rasterio.warp import transform_bounds
        choices=[]
        for path in sorted((root/'relieve').glob('*.tif')):
            with rasterio.open(path) as src:
                if not src.crs:continue
                a,b,c,d=transform_bounds(src.crs,'EPSG:4326',*src.bounds,densify_pts=21)
                area=max(0,min(e,c)-max(w,a))*max(0,min(n,d)-max(s,b))
                if area>0:choices.append((-area,str(path),path))
        if choices:return min(choices)[2]
        raise ValueError('No hay un GeoTIFF de relieve que intersecte el marco. Añádelo o desactiva datos.relieve.')
    raise ValueError(f'Capa desconocida: {layer}')
