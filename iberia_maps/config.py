"""Configuración TOML y coordenadas geográficas sin cambiar su posición."""
from pathlib import Path
import csv
import math
import re
import tomllib


def coordinate(value, axis):
    """Decimal o DMS. N/S para latitud; E/W/O para longitud."""
    limit = 90 if axis == 'lat' else 180
    if isinstance(value, bool):
        raise ValueError('Una coordenada debe ser un número o texto geográfico.')
    if isinstance(value, (float, int)):
        result = float(value)
    else:
        text = str(value).strip().upper().replace('−', '-')
        if not text:
            raise ValueError('Coordenada vacía.')
        match = re.fullmatch(r'(.+?)\s*([NSEWO])?', text)
        if not match:
            raise ValueError(f'Coordenada no válida: {value}')
        body, hemisphere = match.groups()
        if hemisphere and hemisphere not in ('NS' if axis == 'lat' else 'EWO'):
            raise ValueError(f'Hemisferio incorrecto para {axis}: {value}')
        parts = re.findall(r'[+-]?\d+(?:[.,]\d+)?', body)
        rest = re.sub(r'[+-]?\d+(?:[.,]\d+)?', '', body)
        if not 1 <= len(parts) <= 3 or re.search(r'''[^\s°º′'″":]''', rest):
            raise ValueError(f'Coordenada no válida: {value}')
        nums = [float(n.replace(',', '.')) for n in parts]
        if any(not 0 <= n < 60 for n in nums[1:]):
            raise ValueError(f'Minutos y segundos deben estar entre 0 y 60: {value}')
        if len(nums) > 1 and not nums[0].is_integer():
            raise ValueError('Con minutos, los grados deben ser enteros.')
        if len(nums) > 2 and not nums[1].is_integer():
            raise ValueError('Con segundos, los minutos deben ser enteros.')
        negative = parts[0].startswith('-')
        if hemisphere and negative and hemisphere in 'NE':
            raise ValueError(f'Signo y hemisferio contradictorios: {value}')
        result = abs(nums[0]) + (nums[1] / 60 if len(nums) > 1 else 0) + (nums[2] / 3600 if len(nums) > 2 else 0)
        if hemisphere in ('S', 'W', 'O') or (negative and not hemisphere):
            result = -result
    if not math.isfinite(result) or abs(result) > limit:
        raise ValueError(f'{axis} fuera de rango: {value}')
    return result


def load(path):
    path = Path(path).resolve()
    with path.open('rb') as f:
        cfg = tomllib.load(f)
    cfg['_path'] = path
    for key in ('mapa', 'datos'):
        if key not in cfg:
            raise ValueError(f'Falta la sección [{key}].')
    m = cfg['mapa']
    for key, axis in [('oeste', 'lon'), ('este', 'lon'), ('sur', 'lat'), ('norte', 'lat')]:
        if key not in m:
            raise ValueError(f'Falta mapa.{key}.')
        m[key] = coordinate(m[key], axis)
    if not m['oeste'] < m['este'] or not m['sur'] < m['norte']:
        raise ValueError('Los límites deben cumplir oeste < este y sur < norte.')
    if max(abs(m['sur']), abs(m['norte'])) > 85:
        raise ValueError('Esta herramienta está diseñada para latitudes entre −85 y 85 grados.')
    root = (path.parent / cfg['datos'].get('carpeta', '../../iberia-maps-data')).resolve()
    for key in ('batimetria', 'costa', 'relieve'):
        value = cfg['datos'].get(key)
        if value == 'auto':
            from .data import automatic_file
            cfg['datos'][key] = automatic_file(root, key, (m['oeste'],m['este'],m['sur'],m['norte']))
        elif value:
            cfg['datos'][key] = (path.parent / value).resolve()
        if cfg['datos'].get(key) and not cfg['datos'][key].is_file():
            raise ValueError(f'No encuentro datos.{key}: {cfg["datos"][key]}')
    if not any(cfg['datos'].get(k) for k in ('batimetria', 'costa', 'relieve')):
        raise ValueError('Selecciona al menos una capa en [datos].')
    stations = cfg.get('estaciones', [])
    if cfg.get('puntos', {}).get('csv'):
        with (path.parent / cfg['puntos']['csv']).open(encoding='utf-8-sig', newline='') as f:
            stations = stations + list(csv.DictReader(f))
    names = set()
    for st in stations:
        if not all(k in st for k in ('nombre', 'lat', 'lon')) or not str(st['nombre']).strip():
            raise ValueError('Cada estación necesita nombre, lat y lon.')
        if st['nombre'] in names:
            raise ValueError(f'Nombre de estación repetido: {st["nombre"]}')
        names.add(st['nombre'])
        st['lat'] = coordinate(st['lat'], 'lat')
        st['lon'] = coordinate(st['lon'], 'lon')
        if not m['oeste'] <= st['lon'] <= m['este'] or not m['sur'] <= st['lat'] <= m['norte']:
            raise ValueError(f'La estación {st["nombre"]} queda fuera del mapa.')
    cfg['estaciones'] = stations
    inset = cfg.get('acercamiento', {})
    if inset.get('activar', False):
        if not stations:
            raise ValueError('El acercamiento necesita al menos una estación.')
        target = inset.get('estacion', stations[0]['nombre'])
        if target not in names:
            raise ValueError(f'Estación del acercamiento desconocida: {target}')
        inset['estacion'] = target
        if not 0 < float(inset.get('ancho_km', 4)) <= 100:
            raise ValueError('acercamiento.ancho_km debe estar entre 0 y 100 km.')
    out = cfg.setdefault('salida', {})
    cfg['_out'] = (path.parent / out.get('carpeta', 'salidas')).resolve()
    stem = out.get('nombre', 'mapa')
    if not re.fullmatch(r'[\w-]+', stem):
        raise ValueError('salida.nombre solo admite letras, números, guiones y guiones bajos.')
    if not isinstance(out.get('ppp', 300), int) or not 72 <= out.get('ppp', 300) <= 600:
        raise ValueError('salida.ppp debe ser un entero entre 72 y 600.')
    style = cfg.setdefault('estilo', {})
    for key in ('profundidad_max', 'altitud_max', 'isobatas_cada'):
        if key in style and (not math.isfinite(float(style[key])) or float(style[key]) <= 0):
            raise ValueError(f'estilo.{key} debe ser positivo y finito.')
    if m['norte'] - m['sur'] > 30 or m['este'] - m['oeste'] > 40:
        raise ValueError('La región es demasiado grande para una exportación local; divídela en zonas.')
    return cfg
