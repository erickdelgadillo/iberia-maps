import json
from pathlib import Path
import numpy as np
import pytest
from netCDF4 import Dataset
from iberia_maps.config import coordinate, load
from iberia_maps.data import bathymetry, terrain
from iberia_maps.cli import main


def test_coordinates_match_published_station():
    assert coordinate('42° 14.09′ N','lat') == pytest.approx(42.23483333333333)
    assert coordinate('8° 47.18′ W','lon') == pytest.approx(-8.786333333333333)
    assert coordinate('42º 12\' 7.081" n','lat') == pytest.approx(42.20196694444445)
    assert coordinate('8º 47\' 53.830" O','lon') == pytest.approx(-8.79828611111111)
    assert coordinate('-8,7863333333','lon') == pytest.approx(-8.7863333333)
    assert coordinate('0° 30′ W','lon') == -.5


@pytest.mark.parametrize('value,axis', [('42° 65′ N','lat'), ('42 N','lon'), ('-42 N','lat'), ('nan','lon'), (float('nan'),'lat'), ('181','lon'), ('42foo','lat'), ('42.5 3 N','lat'), ('42 3.5 4 N','lat')])
def test_invalid_coordinates_are_rejected(value,axis):
    with pytest.raises(ValueError):coordinate(value,axis)


@pytest.fixture
def fixture_map(tmp_path):
    with Dataset(tmp_path/'sea.nc','w') as d:
        d.createDimension('latitude',12);d.createDimension('longitude',15)
        d.createVariable('latitude','f8',('latitude',))[:]=np.linspace(42,43,12)
        d.createVariable('longitude','f8',('longitude',))[:]=np.linspace(-9,-8,15)
        z=d.createVariable('elevation','f4',('latitude','longitude'),fill_value=-9999)
        z[:]=np.tile(np.linspace(-100,10,15),(12,1));z.units='m';z.long_name='Elevation relative to Lowest Astronomical Tide datum'
    (tmp_path/'coast.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{},'geometry':{'type':'LineString','coordinates':[[-8.1,42],[-8.1,43]]}}]}))
    config=tmp_path/'mapa.toml'
    config.write_text('''[mapa]
oeste=-8.9
este=-8.05
sur=42.1
norte=42.9
[datos]
batimetria="sea.nc"
costa="coast.geojson"
[[estaciones]]
nombre="Central"
lat=42.5
lon=-8.5
[acercamiento]
activar=true
estacion="Central"
ancho_km=4
[salida]
carpeta="resultados"
ppp=100
''')
    return config


def test_end_to_end_exports_and_records_exact_coordinates(fixture_map):
    assert main([str(fixture_map)])==0
    out=fixture_map.parent/'resultados'
    for ext in ['png','pdf']:assert (out/f'mapa.{ext}').stat().st_size>1000
    record=json.loads((out/'mapa.json').read_text())
    assert record['estaciones']==[{'nombre':'Central','lat':42.5,'lon':-8.5}]
    assert record['acercamiento']['activar'] is True
    assert record['capas']['batimetria']['referencia_vertical']=='LAT'


def test_csv_and_paths_are_relative_to_configuration(fixture_map,monkeypatch,tmp_path):
    (tmp_path/'puntos.csv').write_text('nombre,lat,lon\nCSV,42.6,-8.4\n')
    with fixture_map.open('a') as f:f.write('\n[puntos]\ncsv="puntos.csv"\n')
    monkeypatch.chdir('/')
    cfg=load(fixture_map)
    assert len(cfg['estaciones'])==2
    assert cfg['datos']['batimetria']==tmp_path/'sea.nc'


def test_outside_station_and_wrong_inset_fail(fixture_map):
    original=fixture_map.read_text()
    fixture_map.write_text(original.replace('lat=42.5','lat=45.0'))
    assert main([str(fixture_map)])==2
    fixture_map.write_text(original.replace('estacion="Central"','estacion="No existe"'))
    assert main([str(fixture_map)])==2


def test_bathymetry_coverage_and_missing_region(fixture_map):
    cfg=load(fixture_map)
    *_,meta=bathymetry(cfg['datos']['batimetria'],(-9.5,-8,42,43))
    assert meta['cobertura_completa'] is False
    with pytest.raises(ValueError,match='no cubre'):bathymetry(cfg['datos']['batimetria'],(1,2,35,36))


def test_projected_terrain_is_reprojected_and_nodata_masked(tmp_path):
    import rasterio
    from rasterio.transform import from_origin
    f=tmp_path/'land.tif';a=np.full((30,30),250,dtype='int16');a[:5,:]=-32768
    with rasterio.open(f,'w',driver='GTiff',width=30,height=30,count=1,dtype='int16',crs='EPSG:25829',transform=from_origin(500000,4700000,200,200),nodata=-32768) as d:d.write(a,1)
    x,y,z,meta=terrain(f,(-9.1,-8.8,42.3,42.6))
    assert x.min()>-10 and x.max()<-8
    assert y.min()>42 and y.max()<43
    assert z.count()>0 and float(z.min())==pytest.approx(250)
    assert np.ma.getmaskarray(z).any()
    assert meta['crs_origen']=='EPSG:25829'


def test_auto_selects_finest_complete_bathymetry(fixture_map):
    from iberia_maps.data import automatic_file
    import shutil
    root=fixture_map.parent/'datasets';(root/'batimetria').mkdir(parents=True)
    shutil.copy2(fixture_map.parent/'sea.nc',root/'batimetria/region.nc')
    with Dataset(root/'batimetria/coarse.nc','w') as d:
        d.createDimension('latitude',3);d.createDimension('longitude',3)
        d.createVariable('latitude','f8',('latitude',))[:]=[42,42.5,43]
        d.createVariable('longitude','f8',('longitude',))[:]=[-9,-8.5,-8]
        d.createVariable('elevation','f4',('latitude','longitude'))[:]=-50
    assert automatic_file(root,'batimetria',(-8.9,-8.1,42.1,42.9)).name=='region.nc'
    with pytest.raises(ValueError,match='Ningún NetCDF'):automatic_file(root,'batimetria',(-10,-8,42,43))
