import rasterio
from rasterio.enums import Resampling
import geopandas as gpd
from shapely.geometry import mapping, shape
import numpy as np
from rasterio.features import shapes
import os
from shapely.geometry import shape
import pandas as pd
import shutil

#imputs
raiz = 'X:/Sigmagis/VERTICAIS/COLABORADORES/Luan_Faria/TESTE_1/'
shp = 'BASE_TALHOES_NDVI_FERRARI_J3_2024.shp'
ervas= 'ERVAS_FERRARI_J3_2024.shp'

# PASTAS
PASTA_SHAPES = os.path.join(raiz, 'Vetores/shape/', shp )
PASTA_IDADE = os.path.join(raiz, 'Vetores/shape/IDADE/')
PASTA_RESAMPLE = os.path.join(raiz, 'Imagens/NDVI/RES/')
SHAPE_ERVAS = os.path.join(raiz, 'Vetores/shape/', ervas)

SAIDA='C:/CLASSIFICACAO/'
RECLASS='C:/CLASSIFICACAO/REC/'
VETORIZADO='C:/CLASSIFICACAO/VETOR/'
INTERSECT='C:/CLASSIFICACAO/INTERSECT/'#imputs
MERGE='C:/CLASSIFICACAO/MERGE/'

os.makedirs(os.path.join(SAIDA, 'REC'), exist_ok=True)
os.makedirs(os.path.join(SAIDA, 'VETOR'), exist_ok=True)
os.makedirs(os.path.join(SAIDA, 'INTERSECT'), exist_ok=True)
os.makedirs(os.path.join(SAIDA, 'MERGE'), exist_ok=True)

#reclassificação
def processo():
    for filename in os.listdir(PASTA_RESAMPLE):
        if filename.endswith('.tif'):
            file = os.path.join(PASTA_RESAMPLE, filename)
            output_file = os.path.join(RECLASS, filename)

            print('\nAbrindo o Raster: ',filename)

            falhas=float(input('Insira valores Falhas: '))
            MediaBaixa=float(input('Insira valores média baixa: '))
            Media=float(input('Insira valores média: '))
            MediaAlta=float(input('Insira valores média alta: '))
            fundo = float(0)

            # falhas=float(0.1)
            # MediaBaixa=float(0.2)
            # Media=float(0.3)
            # MediaAlta=float(0.4)
            
            with rasterio.open(file) as src:
                data = src.read(1)
                
                reclass_data =  np.where(data <= falhas, 1,
                                np.where(data <= MediaBaixa, 2,
                                np.where(data <= Media, 3,
                                np.where(data <= MediaAlta, 4,
                                np.where(data <= 1.0, 5, 6)))))

                profile = src.profile
                profile.update(dtype=rasterio.float32)
                

                with rasterio.open(output_file, "w", **profile) as dst:
                    dst.write(reclass_data, 1)
                print('Reclassificação - OK')

    print("\nVetorizando Raster!")
    #TRANSFORMAR RASTER PARA VETOR
    import warnings
    warnings.filterwarnings("ignore")  #IGNORA OS AVISOS DE ALERTASD

    for reclassificados in os.listdir(RECLASS):
        if reclassificados.endswith('.tif'):
            rec = os.path.join(RECLASS, reclassificados)
            select_file = os.path.join(INTERSECT, 'Intersect_'+reclassificados[8:-4]+'.shp') #o -4 é para tirar o .tif
            select_file_ = os.path.join(VETORIZADO, 'Vetorizado_'+reclassificados[8:-4]+'.shp') #o -4 é para tirar o .tif
            
            with rasterio.open(rec) as src:
                results = ({'properties': {'GRIDCODE': v}, 'geometry': s}
                            for i, (s, v) in enumerate(shapes(src.read(1), transform=src.transform)))
            
                
                gdf = gpd.GeoDataFrame.from_features(list(results),src.crs)
                gdf_ = gdf[gdf['GRIDCODE'] != 6]
                gdf_.to_file(select_file_)
                

            ##INTERSECT ENTRE A IDADE E O VETORIZADO
            for res in os.listdir(PASTA_IDADE):
                if res.endswith('.shp'):
                    if (res==reclassificados[8:-4]+'.shp'):
                        vetor = gpd.read_file(os.path.join(PASTA_IDADE,res))

                        intersect= vetor.overlay(gdf_, how='intersection')
                        intersect.to_file(select_file)
            print("Intersect ",reclassificados,' - OK')
    
    #MERGE
    print('\nREALIZANDO O MERGE ENTRE OS INTERSECTS!')
    gdf_intersect = []

    for inter in os.listdir(INTERSECT):
        if inter.endswith('.shp'):
            gdf_2 = gpd.read_file(os.path.join(INTERSECT,inter))
            gdf_intersect.append(gdf_2)
            
    merge_gdf = gpd.GeoDataFrame(pd.concat(gdf_intersect, ignore_index=True))
    print('\nDISSOLVENDO MERGE!')
    merge_dissolvido = merge_gdf.dissolve(by='GRIDCODE')

    #calcular VALORES DE BIOMASSA!
    print('\nCALCULANDO VALORES DE BIOMASSA!')

    saida_merge = os.path.join(MERGE,'dissolvido_colocar_ervas.shp')
    dissolvido = gpd.GeoDataFrame(merge_dissolvido['geometry'])
    dissolvido['AREA_GIS']=dissolvido.area/10000
    total = dissolvido['AREA_GIS'].sum()
    print('\nAREA TOTAL SHAPE: ',total,'ha')
    dissolvido['BIOMASSA'] =  dissolvido['AREA_GIS'] / total * 100

    #print(dissolvido['BIOMASSA'])

    print('\nVALORES DE BIOMASSA EM % (DESCONSIDERANDO AS ERVAS):',
        '\nBIOMASSA RUIM: ',dissolvido['BIOMASSA'][1]+dissolvido['BIOMASSA'][2],'%',
        '\nBIOMASSA MÉDIA: ',dissolvido['BIOMASSA'][3],'%',
        '\nBIOMASSA BOA: ',dissolvido['BIOMASSA'][4] + dissolvido['BIOMASSA'][5],'%')
  
    dissolvido.to_file(saida_merge)

executa= True
while executa:
    processo()
    opcao = str(input('\nDeseja inserir outros valores? [S/N] ')).upper().strip()
    if opcao == 'N':
        executa = False
        if ervas.endswith('.shp'):
            final = os.path.join(SAIDA,'INTERSECT'+shp[12:])
            shapfile = gpd.read_file(os.path.join(PASTA_SHAPES))
            shapfile['AREA_GIS']=shapfile.area/10000 #CRIANDO AREA GIS

            for di in os.listdir(MERGE):
                if di.endswith('.shp'):
                    dissolv = gpd.read_file(os.path.join(MERGE,di))
                    erva = gpd.read_file(os.path.join(SHAPE_ERVAS))
        
                    print('\nCRIANDO GRIDCODE 6 E ADICIONANDO AO MERGE DISSOLVIDO')
                    ervas_dissolvidas = erva.dissolve() #dissolvendo ervas
                    dif= dissolv.overlay(ervas_dissolvidas, how='difference') #dissolve
                    union = dif.overlay(ervas_dissolvidas, how='union')
                    union['GRIDCODE'][5]=6
                    dissolvido_final = union[['GRIDCODE','geometry']]
        
                    print('\nREALIZANDO INTERSECT ENTRE O SHAPE E O MERGE DISSOLVIDO!')
                    intersect_final= dissolvido_final.overlay(shapfile, how='intersection')
                    intersect_final['AREA_NDVI'] = intersect_final.area/10000
                    intersect_final['GRIDCODE']=intersect_final['GRIDCODE'].astype(int)
            intersect_final.to_file(final)

            #DELETAR PASTAS
            print('\nDeletando pastas!')
            shutil.rmtree(RECLASS)
            shutil.rmtree(VETORIZADO)
            shutil.rmtree(INTERSECT)
            shutil.rmtree(MERGE)
            print('FINALIZADO!!')
        else:
            print('\nNão Possui Shape de Ervas!\n\nCRIANDO AREA GIS NO SHP')
            shapfile = gpd.read_file(os.path.join(PASTA_SHAPES))
            shapfile['AREA_GIS']=shapfile.area/10000 #CRIANDO AREA GIS
            final = os.path.join(SAIDA,'INTERSECT'+shp[12:])
            
            print('\nREALIZANDO INTERSECT ENTRE O SHAPE E O MERGE DISSOLVIDO!')
            
            for d in os.listdir(MERGE):
                if d.endswith('.shp'):
                    dissolvido_ = gpd.read_file(os.path.join(MERGE,d))
                    dissolvido_final = dissolvido_[['GRIDCODE','geometry']]
                    intersect_final= dissolvido_final.overlay(shapfile, how='intersection')
                    intersect_final['AREA_NDVI'] = intersect_final.area/10000
                    intersect_final['GRIDCODE']=intersect_final['GRIDCODE'].astype(int)
            intersect_final.to_file(final)
           
            #DELETAR PASTAS
            print('\nDeletando pastas!')
            shutil.rmtree(RECLASS)
            shutil.rmtree(VETORIZADO)
            shutil.rmtree(INTERSECT)
            shutil.rmtree(MERGE)
            print('FINALIZADO!!')
            