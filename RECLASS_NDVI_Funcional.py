import rasterio
from rasterio.enums import Resampling
import geopandas as gpd
import numpy as np
from rasterio.features import shapes
import os
from shapely.geometry import shape
import pandas as pd
import shutil
from shapely.validation import make_valid

#imputs
raiz = "X:/Sigmagis/Projetos/Usina Santa Terezinha/NDVI/2025/J1/C_SUL/UMU" 
shp = 'BASE_TALHOES_NDVI_UMU_J1_2025.shp'
ervas= 'ERVAS_UMU_J1_2025.shp'


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
DESCOMPRIMIR='C:/CLASSIFICACAO/DESC/'
MERGE_ERVAS='C:/CLASSIFICACAO/MERGE_ERVAS/'


os.makedirs(os.path.join(SAIDA, 'REC'), exist_ok=True)
os.makedirs(os.path.join(SAIDA, 'VETOR'), exist_ok=True)
os.makedirs(os.path.join(SAIDA, 'INTERSECT'), exist_ok=True)
os.makedirs(os.path.join(SAIDA, 'MERGE'), exist_ok=True)
os.makedirs(os.path.join(SAIDA, 'MERGE_ERVAS'), exist_ok=True)
os.makedirs(os.path.join(SAIDA, 'DESC'), exist_ok=True)


#corrigir_geometria(shp)
def corrigir_geometria(geometry):
    if not geometry.is_valid:  # Verifica se a geometria é inválida
        try:
            # Tenta usar o make_valid se disponível
            geometry = make_valid(geometry)
        except Exception:
            # Caso falhe, usa buffer de 0 como fallback
            geometry = geometry.buffer(0)
    return geometry

def descomprimir_raster():
    print('\nDescompactando img!\n')
    for filename in os.listdir(PASTA_RESAMPLE):
            if filename.endswith('.tif'):
                file = os.path.join(PASTA_RESAMPLE, filename)
                output_file = os.path.join(DESCOMPRIMIR, filename)

                with rasterio.open(file) as src:
                    teste = src.read(1)
                    profile = src.profile
                    profile.update(compress='')  # Desativa a compressão LZW
                with rasterio.open(output_file, "w", **profile) as dst:
                    dst.write(teste, 1)


#reclassificação
def processo():
    descomprimir_raster()   
    for filename in os.listdir(PASTA_RESAMPLE):
        if filename.endswith('.tif'):
            file = os.path.join(PASTA_RESAMPLE, filename)
            output_file = os.path.join(RECLASS, filename)

            print('\nAbrindo o Raster: ',filename)

            # falhas=float(input('Insira valores Falhas: '))
            # MediaBaixa=float(input('Insira valores média baixa: '))
            # Media=float(input('Insira valores média: '))
            # MediaAlta=float(input('Insira valores média alta: '))
            # fundo = float(0)

            #Valores para teste
            falhas=float(0.1)
            MediaBaixa=float(0.2)
            Media=float(0.3)
            MediaAlta=float(0.4)  
            
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

    print(dissolvido['BIOMASSA'])

    # print('\nVALORES DE BIOMASSA EM % (DESCONSIDERANDO AS ERVAS):',
    #     '\nBIOMASSA RUIM: ',dissolvido['BIOMASSA'][1]+dissolvido['BIOMASSA'][2],'%',
    #     '\nBIOMASSA MÉDIA: ',dissolvido['BIOMASSA'][3],'%',
    #     '\nBIOMASSA BOA: ',dissolvido['BIOMASSA'][4] + dissolvido['BIOMASSA'][5],'%')
    
    #dissolvido['GRIDCODE']=dissolvido['GRIDCODE'].astype(int)

    dissolvido_salva = dissolvido.reset_index()
    for cc in dissolvido_salva:
        print(cc)
    dissolvido_salva['GRIDCODE']=dissolvido_salva['GRIDCODE'].astype(int)
    dissolvido_salva.to_file(saida_merge)

executa= True
while executa:
    processo()
    opcao = str(input('\nDeseja inserir outros valores? [S/N] ')).upper().strip()
    if opcao == 'N':
        executa = False
        if ervas.endswith('.shp'):
            print("\nPossui Ervas!")
            final = os.path.join(SAIDA,'INTERSECT'+shp[12:])
            saida_erva_dis = os.path.join(MERGE_ERVAS,'ervas_dis.shp')
            merge_com_erva = os.path.join(MERGE_ERVAS,'merge_final.shp')
            shapfile = gpd.read_file(os.path.join(PASTA_SHAPES))
            shapfile["geometry"] = shapfile["geometry"].apply(corrigir_geometria)
            shapfile['AREA_GIS']=shapfile.area/10000 #CRIANDO AREA GIS

            for di in os.listdir(MERGE):
                if di.endswith('.shp'):
                    dissolv = gpd.read_file(os.path.join(MERGE,di))
                    erva = gpd.read_file(os.path.join(SHAPE_ERVAS))

                    erva["geometry"] = erva["geometry"].apply(corrigir_geometria)
                    dissolv["geometry"] = dissolv["geometry"].apply(corrigir_geometria)
        
                    print('\nDissolvendo ervas!\n')
                    ervas_dissolvidas = erva.dissolve() #dissolvendo ervas
                    #ervas_dissolvidas['GRIDCODE'] = 6
                    ervas_dissolvidas.to_file(saida_erva_dis) #estou tentando fazer por parte para saber onde ta dando pau

                    print("Merge entre ervas e shp!")
                    dif= dissolv.overlay(ervas_dissolvidas, how='difference') #dissolve
                    union = dif.overlay(ervas_dissolvidas, how='union')
                    union['GRIDCODE'][5]=6
                    dissolvido_final = union[['GRIDCODE','geometry']]
                    dissolvido_final['GRIDCODE']=dissolvido_final['GRIDCODE'].astype(int)
                    dissolvido_final.to_file(merge_com_erva)
        
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
            shutil.rmtree(MERGE_ERVAS)
            shutil.rmtree(DESCOMPRIMIR)
            print('FINALIZADO!!')
        else:
            print('\nNão Possui Shape de Ervas!\n\nCRIANDO AREA GIS NO SHP')
            shapfile = gpd.read_file(os.path.join(PASTA_SHAPES))
            shapfile["geometry"] = shapfile["geometry"].apply(corrigir_geometria)
            shapfile['AREA_GIS']=shapfile.area/10000 #CRIANDO AREA GIS
            final = os.path.join(SAIDA,'INTERSECT'+shp[12:])
            
            print('\nREALIZANDO INTERSECT ENTRE O SHAPE E O MERGE DISSOLVIDO!')
            
            for d in os.listdir(MERGE):
                if d.endswith('.shp'):
                    dissolvido_ = gpd.read_file(os.path.join(MERGE,d))
                    dissolvido_["geometry"] = dissolvido_["geometry"].apply(corrigir_geometria)
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
            shutil.rmtree(DESCOMPRIMIR)
            shutil.rmtree(MERGE_ERVAS)
            print('FINALIZADO!!')
            