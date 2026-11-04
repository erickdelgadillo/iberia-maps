"""Dibujo compartido por el mapa principal y el acercamiento."""
import hashlib
import io
import json
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter, MaxNLocator
from . import __version__
from .data import bounds, bathymetry, coast, terrain


def create(cfg):
    box = bounds(cfg)
    style = cfg.get('estilo', {})
    sea = LinearSegmentedColormap.from_list('iberia_sea', style.get('azules', ['#08306b', '#2171b5', '#bdd7ee']))
    land = LinearSegmentedColormap.from_list('iberia_land', ['#e4e8c8', '#98ad70', '#af926e', '#f4efe5'])
    loaded = {}; provenance = {}; notes = []
    data = cfg['datos']
    if data.get('batimetria'):
        x, y, z, meta = bathymetry(data['batimetria'], box)
        loaded['sea'] = (x, y, z); provenance['batimetria'] = meta
        if not meta['cobertura_completa']:
            notes.append('La batimetría solo cubre parte del marco solicitado.')
    if data.get('costa'):
        loaded['coast'] = coast(data['costa'], box)
        provenance['costa'] = {'archivo': str(data['costa']), 'segmentos_intersectados': len(loaded['coast'])}
        if not loaded['coast']:
            notes.append('No se encontraron segmentos de costa en el marco.')
    if data.get('relieve'):
        x, y, z, meta = terrain(data['relieve'], box)
        loaded['land'] = (x, y, z); provenance['relieve'] = meta
        if not z.count():
            notes.append('No hay altitudes terrestres positivas en el recorte.')
    if not loaded:
        raise ValueError('Selecciona al menos una capa en [datos].')
    fig, ax = plt.subplots(figsize=(11, 7.5))
    fig.subplots_adjust(left=.10, right=.80, bottom=.17, top=.91)
    depth = float(style.get('profundidad_max', 150))
    height = float(style.get('altitud_max', 2200))
    step = float(style.get('isobatas_cada', 20))
    def panel(a, extent, labels=True):
        a.set_facecolor('#d5d5d5')
        handles = {}
        if 'land' in loaded:
            x,y,z = loaded['land']
            handles['land'] = a.pcolormesh(x,y,z,cmap=land,vmin=0,vmax=height,shading='auto',rasterized=True,zorder=1)
        if 'sea' in loaded:
            x,y,z = loaded['sea']
            handles['sea'] = a.pcolormesh(x,y,z,cmap=sea,vmin=-depth,vmax=0,shading='auto',rasterized=True,zorder=2)
            if style.get('isobatas', True):
                # Recortar las curvas a la vista para que la etiqueta pueda aparecer en un zoom.
                ix = np.where((x>=extent[0]-.01)&(x<=extent[1]+.01))[0]
                iy = np.where((y>=extent[2]-.01)&(y<=extent[3]+.01))[0]
                if len(ix)>1 and len(iy)>1:
                    zz=z[np.ix_(iy,ix)]
                    if zz.count():
                        levels=np.sort(-step*np.arange(1,int(depth/step)+1))
                        levels=levels[(levels>zz.min())&(levels<zz.max())]
                        if len(levels)>100:
                            raise ValueError('Demasiadas isóbatas: aumenta estilo.isobatas_cada.')
                        if len(levels):
                            cs=a.contour(x[ix],y[iy],zz,levels=levels,colors='#526a7a',linewidths=.5,linestyles='solid',zorder=3)
                            a.clabel(cs,fmt='%g',fontsize=7,colors='black')
        for line in loaded.get('coast', []):
            a.plot(line[:,0],line[:,1],color='#202a30',lw=.6,zorder=4)
        a.set_xlim(extent[:2]); a.set_ylim(extent[2:])
        a.set_aspect(1/np.cos(np.deg2rad((extent[2]+extent[3])/2)))
        for st in cfg['estaciones']:
            if extent[0]<=st['lon']<=extent[1] and extent[2]<=st['lat']<=extent[3]:
                a.plot(st['lon'],st['lat'],marker='x',ms=8,mew=1.8,color=style.get('color_puntos','#b62025'),linestyle='none',zorder=6)
                if labels and style.get('etiquetas', True):
                    a.annotate(st['nombre'],(st['lon'],st['lat']),xytext=(7,7),textcoords='offset points',fontsize=8,
                               bbox=dict(facecolor='white',edgecolor='none',alpha=.8),zorder=7)
        return handles
    try:
        handles=panel(ax,box)
        ax.set_title(cfg['mapa'].get('titulo','Mapa de muestreo'),fontsize=17,fontweight='bold',pad=12)
        ax.set_xlabel('Longitud');ax.set_ylabel('Latitud')
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{abs(v):.2f}° {"O" if v<0 else "E"}'))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{abs(v):.2f}° {"S" if v<0 else "N"}'))
        for j,key in enumerate([k for k in ('sea','land') if k in handles]):
            cax=fig.add_axes([.84+j*.075,.26,.018,.48])
            label=('Fondo (m, '+provenance['batimetria']['referencia_vertical']+')') if key=='sea' else 'Altitud (m)'
            dual = 'sea' in handles and 'land' in handles
            colorbar=fig.colorbar(handles[key],cax=cax,label='' if dual else label)
            if dual:
                cax.set_title(('Fondo\n(m, '+provenance['batimetria']['referencia_vertical']+')') if key=='sea' else 'Altitud\n(m)',fontsize=8,pad=10)
            if key=='sea':
                ticks=MaxNLocator(nbins=6,steps=[1,2,2.5,5,10]).tick_values(-depth,0)
                ticks=ticks[(ticks>=-depth)&(ticks<=0)]
                colorbar.set_ticks(np.unique(np.r_[-depth,ticks,0]))
        inset=cfg.get('acercamiento',{})
        if inset.get('activar',False):
            st=next(st for st in cfg['estaciones'] if st['nombre']==inset['estacion'])
            half=float(inset.get('ancho_km',4))/2
            dx=half/(111.32*np.cos(np.deg2rad(st['lat'])));dy=half/111.32
            ib=(st['lon']-dx,st['lon']+dx,st['lat']-dy,st['lat']+dy)
            ib=(max(box[0],ib[0]),min(box[1],ib[1]),max(box[2],ib[2]),min(box[3],ib[3]))
            ax.add_patch(Rectangle((ib[0],ib[2]),ib[1]-ib[0],ib[3]-ib[2],fill=False,edgecolor='black',lw=1.2,zorder=8))
            ia=ax.inset_axes([.57,.025,.41,.42]);panel(ia,ib,False);ia.set_xticks([]);ia.set_yticks([])
            ia.set_title(st['nombre'],fontsize=8,pad=3)
            for spine in ia.spines.values():spine.set_linewidth(1.3)
        if style.get('escala',True):
            lat=box[2]+(box[3]-box[2])*.04
            width_km=(box[1]-box[0])*111.32*np.cos(np.deg2rad(lat))
            target=width_km*.12
            exponent=10**np.floor(np.log10(target))
            length=max(v*exponent for v in (1,2,5,10) if v*exponent<=target)
            dx=length/(111.32*np.cos(np.deg2rad(lat)));lon=box[0]+(box[1]-box[0])*.04
            ax.plot([lon,lon+dx],[lat,lat],color='black',lw=2,zorder=8)
            ax.text(lon+dx/2,lat-(box[3]-box[2])*.025,f'{length:g} km',ha='center',fontsize=8,zorder=8,
                    bbox=dict(facecolor='white',edgecolor='none',alpha=.7,pad=1))
        footer=' · '.join(label for key,label in [('coast','Costa: IHM'),('sea','Batimetría: EMODnet'),('land','Relieve: IGN/CNIG')] if key in loaded)
        fig.text(.1,.065,footer,fontsize=7,color='#555555')
        fig.text(.1,.045,'Gris: zonas sin capa representada. El relieve se muestra solo para cotas > 0 m.',fontsize=7,color='#555555')
        cfg['_out'].mkdir(parents=True,exist_ok=True)
        stem=cfg.get('salida',{}).get('nombre','mapa');outputs=[]
        # Preparar ambos formatos antes de reemplazar las salidas existentes.
        prepared=[]
        for ext in ('png','pdf'):
            path=cfg['_out']/f'{stem}.{ext}';temp=path.with_suffix('.'+ext+'.part')
            fig.savefig(temp,format=ext,dpi=cfg.get('salida',{}).get('ppp',300),facecolor='white')
            prepared.append((temp,path))
        for temp,path in prepared:
            temp.replace(path);outputs.append(path)
        for meta in provenance.values():
            source=Path(meta['archivo'])
            digest=hashlib.sha256()
            with source.open('rb') as handle:
                for chunk in iter(lambda: handle.read(1024*1024), b''):
                    digest.update(chunk)
            meta['sha256']=digest.hexdigest()
            meta['bytes']=source.stat().st_size
        record={'programa':'iberia-maps','version':__version__,'fecha_utc':datetime.now(timezone.utc).isoformat(),
                'configuracion_sha256':hashlib.sha256(cfg['_path'].read_bytes()).hexdigest(),
                'limites':list(box),'estaciones':cfg['estaciones'],'capas':provenance,'notas':notes,
                'acercamiento':inset,'salidas':[str(p) for p in outputs]}
        meta=cfg['_out']/f'{stem}.json';meta.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        return outputs+[meta], notes
    finally:
        plt.close(fig)
