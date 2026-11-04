"""Comando iberia-maps."""
import argparse
from pathlib import Path
import sys
from . import __version__


def main(argv=None):
    parser=argparse.ArgumentParser(description='Crea un mapa PNG/PDF a partir de un archivo TOML con límites y estaciones.')
    parser.add_argument('configuracion',type=Path,help='Ejemplo: ejemplos/vigo.toml')
    parser.add_argument('--comprobar',action='store_true',help='Comprueba configuración y capas sin generar imágenes.')
    parser.add_argument('--version',action='version',version=__version__)
    args=parser.parse_args(argv)
    try:
        from .config import load
        cfg=load(args.configuracion)
        if args.comprobar:
            from .data import bathymetry, coast, terrain, bounds
            box=bounds(cfg)
            for name,reader in [('batimetria',bathymetry),('costa',coast),('relieve',terrain)]:
                if cfg['datos'].get(name):
                    value=reader(cfg['datos'][name],box)
                    print(f'✓ {name}: leído correctamente')
                    if name=='batimetria' and not value[-1]['cobertura_completa']:
                        print('Aviso: el marco supera la cobertura de la batimetría.')
            print(f'✓ {len(cfg["estaciones"])} estación(es); coordenadas válidas')
            return 0
        from .render import create
        files,notes=create(cfg)
        for note in notes:print('Aviso:',note)
        for path in files:print('Creado:',path)
        return 0
    except (ValueError,OSError,KeyError,TypeError,ImportError) as error:
        print(f'No se pudo crear el mapa: {error}',file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
