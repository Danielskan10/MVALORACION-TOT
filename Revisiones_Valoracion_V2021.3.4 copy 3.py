# -*- coding: utf-8 -*-
"""
Created on Sun Jan 31 15:14:42 2021

@author: jbaqueros
"""

import csv
import sqlite3
import math
import os

import shutil
import os
# import tkinter
# from tkinter import *
# from tkinter.ttk import *
from datetime import *
import csv
import getpass

#%%
'''
Configuaramos un directorio en donde deberá estar guardado el ejecutable. En 
estos casos será una carpera que se encuentra en el disco local y será la 
misma ruta que cada usuario tiene en J:/VALORACIO...
'''
w_usuario=getpass.getuser()
print("El usuario de esta maquina es: "+w_usuario)
print("--------------"+"\n")
#%%
'''Vamos a definir los usuarios para no estar modificando y 
creando rutas cada vez que un usuario nuevo a usar este archivo. 
'''
def get_usuario(w_usuario):
    '''
    Parameters
    ----------
    w_usuario : TYPE str
        DESCRIPTION.
        Toma el usuario de windows a traves del modulo getpass de python,
        y por medio de la variable w_usuario generada al principio del 
        codigo. Linea 28.
        
        De esta manera generaremos un user_path que tambien será una 
        variable dependiente del usuario de windows y que nos permitira 
        un cambio automatico de las rutas.
        
    Returns
    -------
    None.

    '''
    usuario=w_usuario
    user_path=usuario
    if usuario=="dparrado":
        user_path="DANIELP"
    elif usuario=="dflorian":
        user_path="DENNYSSE"
    elif usuario=="lcarreno":
        user_path="LEYDI CARREÑO"
    elif usuario=="maguilar":
        user_path="Maicol"
    elif usuario=="snunez":
        user_path="SANTIAGO" 
    #print(user_path)
    return user_path
    
get_usuario(w_usuario)
print("--------------"+"\n")
#%%
'''definimos tres rutas que son necesarias: 
    la ruta de bolsa: en donde estan guardados los archivos de infovalmer
    la ruta del codigo: en donde estan guardado el codigo y el archivo especies.
    la ruta de downloads: en donde estan guardados los arcivos que 
    descargamos de porfin
'''

user_path=get_usuario(w_usuario)
ruta_bolsa="C:/VALORACION/VALORACION_ESPECIAL/Bolsa/INFOVALMER/"
print("la ruta de bolsa que vamos a usar es: "+"\n"+ruta_bolsa)
ruta_code="C:/VALORACION/"+user_path+"/Python/VALORACION/"
print("la ruta del usuario donde esta el codigo es: "+"\n"+ruta_code)
ruta_dloads="C:/Users/"+w_usuario+"/Downloads/"
print("la ruta de descargas de porfin es: "+"\n"+ruta_dloads)
print("--------------"+"\n")

#%%

def check_paths():
    print("Comprobando que las rutas necesarias existan...")
    
    try:
        os.stat(ruta_bolsa)
    except:
        os.mkdir(ruta_bolsa)

    try:
        os.stat(ruta_code)
    except:
        os.mkdir(ruta_code)    
        
    print("Verificación de rutas finalizada.")
    print("--------------"+"\n")

check_paths()

#%%
os.chdir(ruta_code)
print("La ruta en la que se encuentra este archivo es: ")
print(os.getcwd())
fecha=date.today()
fecha2= date.today()-timedelta(1)
print("La fecha de hoy es: ")
print(fecha)
print("--------------"+"\n")
#%%
class path_dates:
    
    def fechas_trabajo(self):
        '''
        Serán necesarias dos fechas para realizar la comparacion de los 
        archivos, usualmente serán Hoy y Ayer; o t y t-1.

        Returns
        -------
        None.

        '''
        self.fechaHoy=input("Por favor digite la fecha de hoy (yyyy-mm-dd): ")
        self.fechaAyer=input("Por favor dijite la fecha de ayer (yyyy-mm-dd):")
        
    def getting_date1(self):
        '''    Configura las fechas necesarias para los archivos del dia t...  

        Returns
        -------
        date1 : TYPE: date
            DESCRIPTION.
            Es una variable en formato date que contiene la fecha yyyy-mm-dd
            necesario.            
        f1 : TYPE str
            DESCRIPTION.
            Es una sring que contiene la fecha en yyyymmdd
        f1s : TYPE str
            DESCRIPTION.
            Es una sring que contiene la fecha en mmddyy
        f1ss : TYPE str
            DESCRIPTION.
            Es una sring que contiene la fecha en mmdd

        '''
        date1=self.fechaHoy
        date1=datetime.strptime(date1, "%Y-%m-%d") 
        #trasnform str date1 into a date with hours and minutes
        date1=date(date1.year, date1.month, date1.day ) 
        # trasnform date1 into a date without hours and minutes
        #*********getting day
        if len(str(date1.day))==1:
            dia="0"+str(date1.day)
        else:
            dia=str(date1.day)
        #*********getting month
        if len(str(date1.month))==1:
            mes="0"+str(date1.month)
        else:
            mes=str(date1.month)
        #*********getting year
        ango=str(date1.year)
        f1=ango+mes+dia
        f1s=mes+dia+ango[2:]    
        f1ss=mes+dia
        f1dma=dia+mes+ango[2:]
        # print(date1)
        # print(f1)
        # print(f1s)
        # print(f1ss)
        return date1, f1, f1s, f1ss, f1dma
    
    def getting_date2(self):
        '''    Configura las fechas necesarias para los archivos del dia t-1...  

        Returns
        -------
        date1 : TYPE: date
            DESCRIPTION.
            Es una variable en formato date que contiene la fecha yyyy-mm-dd
            necesario.            
        f2 : TYPE str
            DESCRIPTION.
            Es una sring que contiene la fecha en yyyymmdd
        f2s : TYPE str
            DESCRIPTION.
            Es una sring que contiene la fecha en mmddyy
        f2ss : TYPE str
            DESCRIPTION.
            Es una sring que contiene la fecha en mmdd

        '''
   
        date2=self.fechaAyer
        date2=datetime.strptime(date2, "%Y-%m-%d") 
        #trasnform str date2 into a date wit hours and minutes
        date2=date(date2.year, date2.month, date2.day ) 
        # trasnform date2 into a date without hours and minutes
        #*********getting day
        if len(str(date2.day))==1:
            dia2="0"+str(date2.day)
        else:
            dia2=str(date2.day)
        #*********getting month
        if len(str(date2.month))==1:
            mes2="0"+str(date2.month)
        else:
            mes2=str(date2.month)
        #*********getting year
        ango2=str(date2.year)
        f2=ango2+mes2+dia2
        f2s=mes2+dia2+ango2[2:]
        f2ss=mes2+dia2
        f2dma=dia2+mes2+ango2[2:]
        # print(date2)
        # print(f2)
        # print(f2s)
        # print(f2ss)
        return date2, f2, f2s, f2ss, f2dma

    def setting_path1(self):
        '''
        Configura la ruta en donde se encuentran los archivos de bolsa t

        Returns
        -------
        path1 : TYPE
            DESCRIPTION.

        '''
        f1=self.getting_date1()[1]
        path1=ruta_bolsa+f1+"/"
        # print(path1)
        return path1
    
    def setting_path2(self):
        '''
        Configura la ruta en donde se encuentran los archivos de bolsa t-1

        Returns
        -------
        path2 : TYPE
            DESCRIPTION.

        '''
        f2=self.getting_date2()[1]
        path2=ruta_bolsa+f2+"/"
        # print(path2)
        return path2
    
#%%
    
    def clean_tables(self):
        conn=sqlite3.connect("Revisiones2021.3.4.db")
        c=conn.cursor()
        #FOR DATE1
        c.execute("DELETE FROM SP_T")
        c.execute('DELETE FROM SW_T')
        c.execute('DELETE FROM MX_T')
        c.execute('DELETE FROM MX_RV_T')
        c.execute('DELETE FROM SV_T')
        c.execute('DELETE FROM SB_T')
        c.execute('DELETE FROM TIT_PART_T')
        c.execute('DELETE FROM IND_RF_RV_T')
        c.execute('DELETE FROM SK_596_T')
        c.execute('DELETE FROM SK_596_T')
        c.execute('DELETE FROM SK_583_T')
        c.execute('DELETE FROM ESPECIES')
        c.execute('DELETE FROM NOTAS_ESTRUCTURADAS_T')
        #FOR DATE2
        c.execute('DELETE FROM SP_Y')
        c.execute('DELETE FROM SW_Y')
        c.execute('DELETE FROM MX_Y')
        c.execute('DELETE FROM MX_RV_Y')
        c.execute('DELETE FROM SV_Y')
        c.execute('DELETE FROM SB_Y')
        c.execute('DELETE FROM TIT_PART_Y')
        c.execute('DELETE FROM IND_RF_RV_Y')
        c.execute('DELETE FROM SK_596_Y')
        c.execute('DELETE FROM SK_583_Y')
        c.execute('DELETE FROM NOTAS_ESTRUCTURADAS_Y')
        
        c.execute('DROP TABLE IF EXISTS  V_SP_T')
        c.execute('DROP TABLE IF EXISTS  V_SP_Y')
        c.execute('DROP TABLE IF EXISTS PRECIOS')
        c.execute('DROP TABLE IF EXISTS SP_TOTAL')
        c.execute('DROP TABLE IF EXISTS SW_TOTAL')
        c.execute('DROP TABLE IF EXISTS MX_TOTAL')
        c.execute('DROP TABLE IF EXISTS MX_RV_TOTAL')
        c.execute('DROP TABLE IF EXISTS IND_TOTAL')
        c.execute('DROP TABLE IF EXISTS N_ESTR_TOTAL')
        c.execute('DROP TABLE IF EXISTS TIT_PART_TOTAL')
        c.execute('DROP TABLE IF EXISTS REV_TOTAL_PREV')
        c.execute('DROP TABLE IF EXISTS REV_TOTAL')


        c.execute('DROP TABLE IF EXISTS REVISION')
        c.execute('DROP TABLE IF EXISTS NEW_596 ')
        c.execute('DROP TABLE IF EXISTS REV_TOTAL ')
        c.execute('DROP TABLE IF EXISTS INT_DIV ')
        c.execute('DROP TABLE IF EXISTS COMP_VENT ')
        c.execute('DROP TABLE IF EXISTS INC_RET_CAPITAL')
        c.execute('DROP TABLE IF EXISTS INC_RET_CAPITAL_II')
        c.execute('DROP TABLE IF EXISTS VAL_TASA_CASH')
        c.execute('DROP TABLE IF EXISTS VAL_TASA_CASH_II')
        c.execute('DROP TABLE IF EXISTS BASE_VALORACION')
        c.execute('DROP TABLE IF EXISTS REVISION_DEF')
        c.execute('DROP TABLE IF EXISTS REVISION_DEF_CAUSACION')
        c.execute('DROP TABLE IF EXISTS VALORACION_TIR')

        print("All tables and views were cleaned")

        conn.commit()
        conn.close()
        
    def archivos_1(self):
        '''
        Este metodo lo que hace es seleccionar todos los archivos de la
        fecha t para hacer el respectivo cargue a una base de datos que
        que ya ha sido creada.
        
        Los archivos necesarios para la fecha t son:

        SPmmddyy.001
        SWmmddyy.001
        MXmmddyy_RV.txt
        MXmmddyy.txt
        SVmmddyy.001
        SBmmddyy.001

        yyyymmdd.csv --> Consulta Renta Fija.
        RVmmdd.csv --> Consulta Renta Variable.
        596yyyymmdd.csv --> Informes Titulos.
        583yyyymmdd.csv --> Informes Opercaciones. 

        Especies.csv --> Es un archivo auxiliar para identicar titulos.
        

        Returns
        -------
        None.

        '''
        
        conn=sqlite3.connect("Revisiones2021.3.4.db")
        c=conn.cursor()
        print("Process for date 1 iniciated...")
        f1=self.getting_date1()[1]
        f1s=self.getting_date1()[2]
        f1ss=self.getting_date1()[3]
        f1dma=self.getting_date1()[4]
        source=self.setting_path1()
    
        #****************************************PRECIOS
        sps=source+"SP"+f1s+".001"
        spr=source+"Precios_T_"+f1s+".csv"
        print(sps)
        with open(sps,"r") as f:
            d=f.readlines()
            with open(spr,"w", newline="") as csvfile:
                spamwriter = csv.writer(csvfile, delimiter=';', quoting=csv.QUOTE_MINIMAL)
                for line in d:
                    if line[51:53].startswith("20"):
                        spamwriter.writerow((line[0:7],line[7:20],line[20:32],line[51:59],line[59:67],line[67:75],line[75:77],line[77:81],line[81:84],line[86:89],line[96:105],line[122:129],line[179:187]))
        #****INSERT INFO TO DATA BASE
        with open(spr, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                c.execute("INSERT INTO SP_T VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
        print("SP-->process ended")
    
    
    
        #****************************************ACCIONES
        sws=source+"SW"+f1s+".001"
        swr=source+"Rv_local_T_"+f1s+".csv"
        print(sws)
        with open(sws,"r") as f:
            d=f.readlines()
            with open(swr,"w", newline="") as csvfile:
                spamwriter = csv.writer(csvfile, delimiter=';', quoting=csv.QUOTE_MINIMAL)
                for line in d:
                    if line[19:21].startswith("20"):
                        spamwriter.writerow((line[0:6],line[6:7],line[7:19],line[19:29],line[29:30],line[30:48],line[48:49]))
        #****INSERT INFO TO DATA BASE
        with open(swr, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                c.execute("INSERT INTO SW_T VALUES (?,?,?,?,?,?,?)", row)                
        print("SW-->process ended")
    
        #****************************************TITULOS PARTICIPATIVOS_T
        tps=source+"titulos_participativos_valoracion_"+f1+".txt"
        tpr=source+"titulos_participativos_valoracion_"+f1+".csv"
        print(tps)
        with open(tps,"r") as f:
            d=f.readlines()
            with open(tpr,"w", newline="") as csvfile:
                spamwriter = csv.writer(csvfile, delimiter=';', quoting=csv.QUOTE_MINIMAL)
                for line in d:
                    spamwriter.writerow((line[0:6],line[6:7],line[7:19],line[19:29],line[29:]))
        #****INSERT INFO TO DATA BASE
        with open(tpr, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                c.execute("INSERT INTO TIT_PART_T VALUES (?,?,?,?,?)", row)    
        print("TIT_PART_T-->process ended")

        #****************************************MX_RV
        mx_rvs=source+"MX"+f1s+"_RV.txt"
        mx_rvr=source+"MX_RV_T_"+f1s+".csv"
        print(mx_rvs)
        with open(mx_rvs,"r",newline="") as f:
            d=csv.reader(f)
            with open(mx_rvr,"w", newline="") as csvfile:
                spamwriter = csv.writer(csvfile, delimiter=';',quotechar='|', quoting=csv.QUOTE_MINIMAL)
                for line in d:
                    if line[0].startswith("20"):
                        spamwriter.writerow(line)
        #****INSERT INFO TO DATA BASE
        with open(mx_rvr, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                c.execute("INSERT INTO MX_RV_T VALUES (?,?,?,?,?,?,?,?)", row)
        print("MX_RV-->process ended")
    
        #****************************************MX
        mx_s=source+"MX"+f1s+".txt"
        mx_r=source+"MX_T_"+f1s+".csv"
        print(mx_s)
        with open(mx_s,"r",newline="") as f:
            d=csv.reader(f)
            with open(mx_r,"w", newline="") as csvfile:
                spamwriter = csv.writer(csvfile, delimiter=';',quotechar='|', quoting=csv.QUOTE_MINIMAL)
                for line in d:
                    if line[0].startswith("20"):
                        spamwriter.writerow(line)
        #****INSERT INFO TO DATA BASE
        with open(mx_r, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                c.execute("INSERT INTO MX_T VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
        print("MX-->process ended")
    
        #****************************************TASAS
        svs=source+"SV"+f1s+".001"
        svr=source+"Tasas_T_"+f1s+".csv"
        print(svs)
        with open(svs,"r") as f:
            d=f.readlines()
            with open(svr,"w", newline="") as csvfile:
                spamwriter = csv.writer(csvfile, delimiter=';', quoting=csv.QUOTE_MINIMAL)
                for line in d:
                    if line[6:8].startswith("20"):
                        spamwriter.writerow((line[0:5],line[5:6],line[6:14],line[14:18],line[18:33]))
        #****INSERT INFO TO DATA BASE
        with open(svr, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                c.execute("INSERT INTO SV_T VALUES (?,?,?,?,?)", row)
        print("SV-->process ended")
    
        #****************************************BETAS
        sbs=source+"SB"+f1s+".001"
        sbr=source+"Betas_T_"+f1s+".csv"
        print(sbs)
        with open(sbs,"r") as f:
            d=f.readlines()
            with open(sbr,"w", newline="") as csvfile:
                spamwriter = csv.writer(csvfile, delimiter=';', quoting=csv.QUOTE_MINIMAL)
                for line in d:
                    if line[6:8].startswith("20"):
                        spamwriter.writerow((line[0:5],line[5:6],line[6:14],line[14:20],line[20:31],line[31:42],line[42:53],line[53:64]))
        #****INSERT INFO TO DATA BASE
        with open(sbr, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                c.execute("INSERT INTO SB_T VALUES (?,?,?,?,?,?,?,?)", row)
        print("SB-->process ended")
    
    
        #****************************************INDICADORES RF
        ind_fs=ruta_dloads+f1+".csv"
        with open(ind_fs, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                row1=[x.strip(' ') for x in row]
                c.execute("INSERT INTO IND_RF_RV_T VALUES (?,?,?,?,?,?,?,?,?)", row1)
        print("RF_T-->process ended")
    
        #****************************************INDICADORES RV
        ind_vs=ruta_dloads+"RV"+f1ss+".csv"
        with open(ind_vs, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                row1=[x.strip(' ') for x in row]
                c.execute("INSERT INTO IND_RF_RV_T VALUES (?,?,?,?,?,?,?,?,?)", row1)
        print("RV_T-->process ended")
    
    
        #****************************************SK TITULOS 596
        inf_596_s=ruta_dloads+"596"+f1+".csv"
        with open(inf_596_s, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                if row[0].startswith("Neg") or row[0].startswith("NoN"):
                    row1=[x.strip(' ') for x in row] # to elimitate leading and ending white spaces
                    #row1=[x.replace(' ','') for x in row] #to eliminate all spaces
                    row2=[x.replace(',','') for x in row1]
                    c.execute("INSERT INTO SK_596_T VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row2)
        print("SKTIT596 Today-->process ended")
    
        #****************************************SK OPERACIONES 583
        inf_583_s=ruta_dloads+"583"+f1+".csv"
        with open(inf_583_s, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                if row[0].startswith("Ent") or row[0].startswith("Sal"):
                    row1=[x.strip(' ') for x in row] # to elimitate leading and ending white spaces
                    #row1=[x.replace(' ','') for x in row] #to eliminate all spaces
                    row2=[x.replace(',','') for x in row1] # to elimitate comas for numbers
                    c.execute("INSERT INTO SK_583_T VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row2)
        print("SK583 Today-->process ended")

       #****************************************NOTAS_ESTRUCTURADAS_T
        try:
            nestr_s=source+"800148514_Skan_NE"+f1dma+".csv"
            with open(nestr_s, 'r', newline='') as cvsfile:
                temporal=csv.reader(cvsfile,delimiter=",")
                for row in temporal:
                    if row[0].startswith("TIPO MERCADO"):
                        pass
                    else:
                        row1=[x.strip(' ') for x in row] # to elimitate leading and ending white spaces
                        #row1=[x.replace(' ','') for x in row] #to eliminate all spaces
                        row2=[x.replace(',','') for x in row1]
                        c.execute("INSERT INTO NOTAS_ESTRUCTURADAS_T VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row2)
            print("Notas_Estructuradas Today-->process ended")
        except:
            print('*****ALERTA*****ALERTA*****ALERTA*****ALERTA*****')
            print('No se econtró el archivo Notas_Estructuradas_T para realizar el cargue')
    
        inf_especies=ruta_code+"Especies.csv"
        with open(inf_especies, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                row1=[x.strip(' ') for x in row] # to elimitate leading and ending white spaces
                #row1=[x.replace(' ','') for x in row] #to eliminate all spaces
                c.execute("INSERT INTO ESPECIES VALUES (?,?)", row1)
        print("Especies loaded-->process ended")

  
        print("load files for day one finished")
    
        conn.commit()
        conn.close()
    
    #*************************************************************************************************************************************************DATE2 FILES
    def archivos_2(self):
        '''
        Este metodo lo que hace es seleccionar todos los archivos de la
        fecha t para hacer el respectivo cargue a una base de datos que
        que ya ha sido creada.
        
        Los archivos necesarios para la fecha t-1 son:

        SPmmddyy.001
        SWmmddyy.001
        MXmmddyy_RV.txt
        MXmmddyy.txt
        SVmmddyy.001
        SBmmddyy.001

        yyyymmdd.csv --> Consulta Renta Fija.
        RVmmdd.csv --> Consulta Renta Variable.
        596yyyymmdd.csv --> Informes Titulos.
        583yyyymmdd.csv --> Informes Opercaciones. 

        Returns
        -------
        None.

        '''
        conn=sqlite3.connect("Revisiones2021.3.4.db")
        c=conn.cursor()
        print("Process for date 2 iniciated...")
        f2=self.getting_date2()[1]
        f2s=self.getting_date2()[2]
        f2ss=self.getting_date2()[3]
        f2dma=self.getting_date2()[4]
        source2=self.setting_path2()
        
        #****************************************PRECIOS
        sps=source2+"SP"+f2s+".001"
        spr=source2+"Precios_T_"+f2s+".csv"
        print(sps)
        with open(sps,"r") as f:
            d=f.readlines()
            with open(spr,"w", newline="") as csvfile:
                spamwriter = csv.writer(csvfile, delimiter=';', quoting=csv.QUOTE_MINIMAL)
                for line in d:
                    if line[51:53].startswith("20"):
                        spamwriter.writerow((line[0:7],line[7:20],line[20:32],line[51:59],line[59:67],line[67:75],line[75:77],line[77:81],line[81:84],line[86:89],line[96:105],line[122:129],line[179:187]))
        #****INSERT INFO TO DATA BASE
        with open(spr, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                c.execute("INSERT INTO SP_Y VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
        print("SP-->process ended")
    
        #****************************************ACCIONES
        sws=source2+"SW"+f2s+".001"
        swr=source2+"Rv_local_T_"+f2s+".csv"
        print(sws)
        with open(sws,"r") as f:
            d=f.readlines()
            with open(swr,"w", newline="") as csvfile:
                spamwriter = csv.writer(csvfile, delimiter=';', quoting=csv.QUOTE_MINIMAL)
                for line in d:
                    if line[19:21].startswith("20"):
                        spamwriter.writerow((line[0:6],line[6:7],line[7:19],line[19:29],line[29:30],line[30:48],line[48:49]))
        #****INSERT INFO TO DATA BASE
        with open(swr, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                c.execute("INSERT INTO SW_Y VALUES (?,?,?,?,?,?,?)", row)    
        print("SW-->process ended")
    
        #****************************************TITULOS PARTICIPATIVOS_Y
        tps=source2+"titulos_participativos_valoracion_"+f2+".txt"
        tpr=source2+"titulos_participativos_valoracion_"+f2+".csv"
        print(tps)
        with open(tps,"r") as f:
            d=f.readlines()
            with open(tpr,"w", newline="") as csvfile:
                spamwriter = csv.writer(csvfile, delimiter=';', quoting=csv.QUOTE_MINIMAL)
                for line in d:
                    spamwriter.writerow((line[0:6],line[6:7],line[7:19],line[19:29],line[29:]))
        #****INSERT INFO TO DATA BASE
        with open(tpr, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                c.execute("INSERT INTO TIT_PART_Y VALUES (?,?,?,?,?)", row)    
        print("TIT_PART_Y-->process ended")


        #****************************************MX_RV
        mx_rvs=source2+"MX"+f2s+"_RV.txt"
        mx_rvr=source2+"MX_RV_T_"+f2s+".csv"
        print(mx_rvs)
        with open(mx_rvs,"r",newline="") as f:
            d=csv.reader(f)
            with open(mx_rvr,"w", newline="") as csvfile:
                spamwriter = csv.writer(csvfile, delimiter=';',quotechar='|', quoting=csv.QUOTE_MINIMAL)
                for line in d:
                    if line[0].startswith("20"):
                        spamwriter.writerow(line)
        #****INSERT INFO TO DATA BASE
        with open(mx_rvr, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                c.execute("INSERT INTO MX_RV_Y VALUES (?,?,?,?,?,?,?,?)", row)
        print("MX_RV-->process ended")
    
        #****************************************MX
        mx_s=source2+"MX"+f2s+".txt"
        mx_r=source2+"MX_T_"+f2s+".csv"
        print(mx_s)
        with open(mx_s,"r",newline="") as f:
            d=csv.reader(f)
            with open(mx_r,"w", newline="") as csvfile:
                spamwriter = csv.writer(csvfile, delimiter=';',quotechar='|', quoting=csv.QUOTE_MINIMAL)
                for line in d:
                    if line[0].startswith("20"):
                        spamwriter.writerow(line)
        #****INSERT INFO TO DATA BASE
        with open(mx_r, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                c.execute("INSERT INTO MX_Y VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
        print("MX-->process ended")
    
        #****************************************TASAS
        svs=source2+"SV"+f2s+".001"
        svr=source2+"Tasas_T_"+f2s+".csv"
        print(svs)
        with open(svs,"r") as f:
            d=f.readlines()
            with open(svr,"w", newline="") as csvfile:
                spamwriter = csv.writer(csvfile, delimiter=';', quoting=csv.QUOTE_MINIMAL)
                for line in d:
                    if line[6:8].startswith("20"):
                        spamwriter.writerow((line[0:5],line[5:6],line[6:14],line[14:18],line[18:33]))
        #****INSERT INFO TO DATA BASE
        with open(svr, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                c.execute("INSERT INTO SV_Y VALUES (?,?,?,?,?)", row)
        print("SV-->process ended")
    
        #****************************************BETAS
        sbs=source2+"SB"+f2s+".001"
        sbr=source2+"Betas_T_"+f2s+".csv"
        print(sbs)
        with open(sbs,"r") as f:
            d=f.readlines()
            with open(sbr,"w", newline="") as csvfile:
                spamwriter = csv.writer(csvfile, delimiter=';', quoting=csv.QUOTE_MINIMAL)
                for line in d:
                    if line[6:8].startswith("20"):
                        spamwriter.writerow((line[0:5],line[5:6],line[6:14],line[14:20],line[20:31],line[31:42],line[42:53],line[53:64]))
        #****INSERT INFO TO DATA BASE
        with open(sbr, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                c.execute("INSERT INTO SB_Y VALUES (?,?,?,?,?,?,?,?)", row)
        print("SB-->process ended")
    
        #****************************************INDICADORES RF
        ind_fs=ruta_dloads+f2+".csv"
        with open(ind_fs, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                row1=[x.strip(' ') for x in row]
                c.execute("INSERT INTO IND_RF_RV_Y VALUES (?,?,?,?,?,?,?,?,?)", row1)
        print("RF_Y-->process ended")
    
        #****************************************INDICADORES RV
        ind_vs=ruta_dloads+"RV"+f2ss+".csv"
        with open(ind_vs, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                row1=[x.strip(' ') for x in row]
                c.execute("INSERT INTO IND_RF_RV_Y VALUES (?,?,?,?,?,?,?,?,?)", row1)
        print("RV_Y-->process ended")
    
        #****************************************SK TITULOS 596
    
        inf_596_s=ruta_dloads+"596"+f2+".csv"
        with open(inf_596_s, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                if row[0].startswith("Neg") or row[0].startswith("NoN"):
                    row1=[x.strip(' ') for x in row] # to elimitate leading and ending white spaces
                    #row1=[x.replace(' ','') for x in row] #to eliminate all spaces
                    row2=[x.replace(',','') for x in row1]
                    c.execute("INSERT INTO SK_596_Y VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row2)
        print("SKTIT596 Yesterday-->process ended")
    
        #****************************************SK OPERACIONES 583
    
        inf_583_s=ruta_dloads+"583"+f2+".csv"
        with open(inf_583_s, 'r', newline='') as cvsfile:
            temporal=csv.reader(cvsfile,delimiter=";")
            for row in temporal:
                if row[0].startswith("Ent") or row[0].startswith("Sal"):
                    row1=[x.strip(' ') for x in row] # to elimitate leading and ending white spaces
                    #row1=[x.replace(' ','') for x in row] #to eliminate all spaces
                    row2=[x.replace(',','') for x in row1] # to elimitate comas for numbers
                    c.execute("INSERT INTO SK_583_Y VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row2)
        print("SK583 Yesterday-->process ended")

       #****************************************NOTAS_ESTRUCTURADAS_Y
        try:
            nestr_s=source2+"800148514_Skan_NE"+f2dma+".csv"
            with open(nestr_s, 'r', newline='') as cvsfile:
                temporal=csv.reader(cvsfile,delimiter=",")
                for row in temporal:
                    if row[0].startswith("TIPO MERCADO"):
                        pass
                    else:
                        row1=[x.strip(' ') for x in row] # to elimitate leading and ending white spaces
                        #row1=[x.replace(' ','') for x in row] #to eliminate all spaces
                        row2=[x.replace(',','') for x in row1]
                        c.execute("INSERT INTO NOTAS_ESTRUCTURADAS_Y VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row2)
            print("Notas_Estructuradas yesterday-->process ended")
        except:
            print('*****ALERTA*****ALERTA*****ALERTA*****ALERTA*****')
            print('No se econtró el archivo Notas_Estructuradas_Y para realizar el cargue')

        print("load files for day two finished")
    
        conn.commit()
        conn.close()
#%%
    def revision_total(self):
        '''
        Genera a partir de los archivos cargados un archivo de revision de 
        bolsa. Consolidando la informacion para SP, SW, MX_RV, MX, Luclue
        de RF y RV. De los dias t y t-1

        Returns
        -------
        None.

        '''
        date1=self.getting_date1()[0]
        f1=self.getting_date1()[1]
        conn=sqlite3.connect("Revisiones2021.3.4.db")
        c=conn.cursor()

        print("process revision total started")

        print("creating TABLE  V_SP_T")
        c.execute("""
            CREATE TABLE  V_SP_T AS
            SELECT (A.NEMO||A.ISIN||A.EMISION||A.VCTO||A.TASA)AS KEY1, A.ISIN, A.NEMO, A.EMISION, A.VCTO, A.P_SUCIO
            FROM SP_T AS A""")

        print("creating TABLE V_SP_Y")        
        c.execute("""
            CREATE TABLE V_SP_Y AS
            SELECT (B.NEMO||B.ISIN||B.EMISION||B.VCTO||B.TASA)AS KEY1, B.ISIN, B.NEMO, B.EMISION, B.VCTO, B.P_SUCIO
            FROM SP_Y AS B""")

        print("creating TABLE PRECIOS")
        c.execute("""
            CREATE TABLE PRECIOS AS 
            SELECT A.ISIN, A.NEMO, A.EMISION, A.VCTO, A.P_SUCIO AS PRECIO_T, B.P_SUCIO AS PRECIO_Y
            FROM V_SP_T AS A
            LEFT JOIN V_SP_Y AS B ON A.KEY1=B.KEY1""")
            #-------------------------------------------------------------------------------------------------PRECIOS
        print("creating TABLE SP_TOTAL")
        c.execute("""
            CREATE TABLE SP_TOTAL AS 
            SELECT ISIN, PRECIO_T, PRECIO_Y,'SP' AS FILE FROM PRECIOS WHERE ISIN!='            '""")
            #-------------------------------------------------------------------------------------------------ACCIONES
        print("creating TABLE SW_TOTAL")
        c.execute("""
            CREATE TABLE SW_TOTAL AS 
            SELECT A.ISIN, A.PRECIO AS PRECIO_T, B.PRECIO AS PRECIO_Y, 'SW' AS FILE
            FROM SW_T AS A
            LEFT JOIN SW_Y AS B ON A.ISIN=B.ISIN""")
            #-------------------------------------------------------------------------------------------------RF INTERNACIONAL
        print("creating TABLE MX_TOTAL")
        c.execute("""
            CREATE TABLE MX_TOTAL AS 
            SELECT A.ISIN, A.P_SUCIO AS PRECIO_T, B.P_SUCIO AS PRECIO_Y, 'MX' AS FILE
            FROM MX_T AS A
            LEFT JOIN MX_Y AS B ON A.ISIN=B.ISIN""")
            #-------------------------------------------------------------------------------------------------RV INTERNACIONAL
        print("creating TABLE MX_RV_TOTAL")
        c.execute("""
            CREATE TABLE MX_RV_TOTAL AS 
            SELECT A.ISIN, A.PRECIO AS PRECIO_T, B.PRECIO AS PRECIO_Y, 'MX_RV' AS FILE
            FROM MX_RV_T AS A
            LEFT JOIN MX_RV_Y AS B ON A.ISIN=B.ISIN""")

            #-------------------------------------------------------------------------------------------------NOTAS_ESTRUCTURDAS
        print("creating TABLE N_ESTR_TOTAL")
        c.execute("""
            CREATE TABLE N_ESTR_TOTAL AS 
            SELECT DISTINCT A.ISIN AS ISIN, A.PRECIO AS PRECIO_T, B.PRECIO AS PRECIO_Y, 'N_ESTR' AS FILE
            FROM NOTAS_ESTRUCTURADAS_T AS A
            LEFT JOIN NOTAS_ESTRUCTURADAS_Y AS B ON A.ISIN=B.ISIN""")

        #-------------------------------------------------------------------------------------------------TITULOS_PARTICIPATIVOS
        print("creating TABLE TIT_PART_TOTAL")
        c.execute("""
            CREATE TABLE TIT_PART_TOTAL AS
            SELECT (B.LLAVE)ISIN, (A.PRECIO)PRECIO_T, (C.PRECIO)PRECIO_Y, ("TIT_PART")FILE 
            FROM TIT_PART_T AS A
            LEFT JOIN SK_596_T AS B ON TRIM(A.ISIN)=TRIM(B.ISIN)
            LEFT JOIN TIT_PART_Y AS C ON TRIM(A.ISIN)=TRIM(C.ISIN)
            WHERE B.LLAVE IS NOT NULL
            GROUP BY B.LLAVE""")

        #-------------------------------------------------------------------------------------------------RF Y RV INDICADORES
        print("creating TABLE IND_TOTAL")
        c.execute("""
            CREATE TABLE IND_TOTAL AS 
            SELECT DISTINCT A.INDICADOR AS ISIN, A.PRECIO AS PRECIO_T, B.PRECIO AS PRECIO_Y, 'IND' AS FILE
            FROM IND_RF_RV_T AS A
            LEFT JOIN IND_RF_RV_Y AS B ON A.INDICADOR=B.INDICADOR
            WHERE A.INDICADOR NOT IN (SELECT DISTINCT ISIN FROM TIT_PART_TOTAL)""")
        #-------------------------------------------------------------------------------------------------CONSULTA PARA CREAR TABLA REV_TOTAL_PREV
        print("creating TABLE REV_TOTAL_PREV ")
        c.execute("""CREATE TABLE REV_TOTAL_PREV AS
            SELECT * FROM SP_TOTAL
            UNION ALL
            SELECT * FROM SW_TOTAL
            UNION ALL
            SELECT * FROM MX_TOTAL
            UNION ALL
            SELECT * FROM MX_RV_TOTAL
            UNION ALL
            SELECT * FROM IND_TOTAL
            UNION ALL
            SELECT * FROM TIT_PART_TOTAL
            UNION ALL
            SELECT * FROM N_ESTR_TOTAL""")
        #-------------------------------------------------------------------------------------------------CONSULTA PARA CREAR TABLA REV_TOTAL        
        print("creating TABLE REV_TOTAL ")
        c.execute("""CREATE TABLE REV_TOTAL AS
            SELECT * 
            FROM REV_TOTAL_PREV
            GROUP BY ISIN, PRECIO_T, PRECIO_Y""")
        
        conn.commit()
        conn.close()
        print("process revision total ended")
        
#%%
    def base_valoracion(self):
        '''
        Crea las tablas necesarias para calcular el valor de mercado tanto 
        en la fecha t como la fecha t-1
        
        Creando finalmente una ultima tabla que se llama REVISION_DEF.
        Con la informacion contenida en esta tabla podremos realizar las
        revisiones manuales y revisiones de causaciones. 

        Returns
        -------
        None.

        '''
        date1=self.getting_date1()[0]
        f1=self.getting_date1()[1]
        conn=sqlite3.connect("Revisiones2021.3.4.db")
        c=conn.cursor()
        

        #-------------------------------------------------------------------------------------------------TABLE: REVISION********************************************** SINCE HERE NO INCLUDED YET
        c.execute("""
            CREATE TABLE REVISION AS
            SELECT RTRIM(ISIN)ISIN, PRECIO_T, PRECIO_Y, FILE, 
            ROUND(((PRECIO_T-PRECIO_Y)/PRECIO_Y),8)AS 'CHANGE_%'
            FROM REV_TOTAL""")

        #-------------------------------------------------------------------------------------------------TABLE: 596 MODIFIED AS NEW_596
        '''
        En este execute el archivo une toda la informacion relevante a los 596
        con fecha t y t-1 y tambien consolida la info con el tabla de revision; 
        la cual a su vez contiens todos los inidicadores que usamos de los 
        archivo de infovalmer y de los luclue que descargamos. 
        '''
        c.execute("""
            CREATE TABLE NEW_596 AS
            SELECT A.ESPECIE, A.TITULO, A.EMISION, A.F_VCTO, A.VLR_MER_OR, 
            A.VLR_NOMINAL AS 'NOMINAL_T',--B.VLR_NOMINAL AS 'NOMINAL_Y', 
            (CASE 
            WHEN B.VLR_NOMINAL IS NULL AND A.F_COMPRA!=? THEN A.VLR_NOMINAL
            ELSE B.VLR_NOMINAL      
            END) AS 'NOMINAL_Y',
            A.VLR_COMPRA ,A.FACIAL, A.MET, A.F_COMPRA, A.MONEDA, 
            A.VLR_MER_ AS 'VLR_MER_T', B.VLR_MER_ AS 'VLR_MER_Y', 
            A.LLAVE   , A.POR,
            (CASE WHEN A.MONEDA='$' THEN 1 ELSE C.PRECIO_T END)MONEDA_T, 
            (CASE WHEN A.MONEDA='$' THEN 1 ELSE C.PRECIO_Y END)MONEDA_Y,
            (CASE
            WHEN A.ESPECIE LIKE 'AOR ALVOPETRO ENERGY%' OR A.ESPECIE LIKE 
            'AOR GOOGLE US' OR A.ESPECIE LIKE 'AOR Google US Clase C' 
            OR A.ESPECIE LIKE 'AOR REPSOL%' OR A.ESPECIE LIKE 'AOR AAPL US%' 
            OR A.ESPECIE LIKE 'AOR GPRK US%' AND A.MONEDA<>'$'
            THEN A.ISIN -- ACCIONES CON MONEDA DIFERENTE PESO
            WHEN A.ESPECIE LIKE 'AOR ACH%' OR A.ESPECIE LIKE 'AOR OM SAFPC%' 
            OR A.ESPECIE LIKE 'AOR Servibanca%' OR A.ESPECIE 
            LIKE 'Acc. Sk. Sg Vid Lote%' AND A.NEMOTECNICOBOL='' 
            THEN A.LLAVE --3 CASOS ESPECIALES PARA ACCIONES
            WHEN A.ESPECIE LIKE 'APR%' OR A.ESPECIE LIKE 'AOR%' 
            OR A.ESPECIE LIKE 'HCOLSEL%' OR A.ESPECIE LIKE 'ICOLCAP%' 
            AND A.MONEDA='$' THEN A.NEMOTECNICOBOL -- ACCIONES LOCALES
            WHEN A.LLAVE LIKE 'ZAATG' OR A.ESPECIE LIKE 'Tribeca%' OR 
            A.ESPECIE LIKE "FCPE Inversor Comp%" OR A.ESPECIE LIKE 
            "FCPE Altra II%" OR A.ESPECIE LIKE "FC Privado Aureos%" 
            OR A.ESPECIE LIKE "FCP Altra II%" 
            THEN A.LLAVE --ESTRATEGIAS INMOBILIARIAS y OTROS
            WHEN A.ESPECIE LIKE 'CDT%' OR A.ESPECIE LIKE 'Yankee%' 
            OR A.ESPECIE LIKE 'ETF%' OR A.ESPECIE LIKE 'Bono%' 
            OR A.ESPECIE LIKE 'Treasury%' OR A.ESPECIE LIKE 'FM%' 
            OR A.ESPECIE LIKE 'Papel Cial%'
            OR A.ESPECIE LIKE 'Subordina%' OR A.ESPECIE LIKE 'TES%' 
            OR A.ESPECIE LIKE 'TD%' OR A.ESPECIE LIKE 'Bon%' 
            OR A.ESPECIE LIKE 'Bon%' OR A.ESPECIE LIKE 'Sub%' 
            OR A.ESPECIE LIKE 'Struc%' OR A.ESPECIE LIKE 'TIL no Hipotecar%' 
            OR A.ESPECIE LIKE 'TIPS%' OR A.ESPECIE LIKE 'TItular Hipoteca%' 
            OR A.ESPECIE LIKE 'Tidis' OR A.ESPECIE LIKE 'Tit%'OR A.ESPECIE 
            LIKE 'T-Bills%' THEN A.ISIN -- RENTA FIJA LOCAL-INTERNACIONAL
            WHEN A.ESPECIE LIKE 'FCP%' OR A.ESPECIE LIKE 'FCPE%' 
            OR A.ESPECIE LIKE 'FIC%' OR A.ESPECIE LIKE 'CC%' 
            OR A.ESPECIE LIKE 'CCA%' OR A.ESPECIE LIKE 'CCC%'
            OR A.ESPECIE LIKE '%FONPET%' OR A.ESPECIE LIKE 'P SPC%' 
            OR A.ESPECIE LIKE 'Fondo Invers Colec%' OR A.ESPECIE 
            LIKE 'DFI AV Pep%' OR A.ESPECIE LIKE 'DFI BODEGA%' 
            OR A.ESPECIE LIKE 'DFI Centro%' 
            OR A.ESPECIE LIKE 'DFI EDIFIC%' OR A.ESPECIE LIKE 'DFI Edif P%' 
            OR A.ESPECIE LIKE 'DFI Santaf%' OR A.ESPECIE 
            LIKE 'DFI Torre    Edificio T%' OR A.ESPECIE LIKE 'FONDOCRENA%' 
            OR A.ESPECIE LIKE 'Fid AK 79/%' OR A.ESPECIE LIKE 'Fid CC PAC%' 
            OR A.ESPECIE LIKE 'DFI Torre%' OR A.ESPECIE LIKE 'Edificio%' 
            OR A.ESPECIE LIKE 'Colateral%' 
            THEN A.MONEDA 
            --FONDOS DE CAPITAL PRIVADO,CARTERAS COLECTIVAS/FONDOS DE INVERSION COLECTIVA Y OTROS
            WHEN A.ESPECIE LIKE 'ADR%' THEN A.ISIN --ADR'S
            WHEN A.ESPECIE LIKE 'Credito%' THEN A.LLAVE
            WHEN A.ESPECIE LIKE 'Cash%' OR A.ESPECIE LIKE 'GBP BNY%' 
            THEN 'CASH' -- CASH
            WHEN A.ESPECIE LIKE 'Cta Ah%' OR A.ESPECIE LIKE 'CtaAho%' 
            OR A.ESPECIE LIKE 'Cta BcoDav%' THEN 
            'CTA_AHORROS' --CTAS DE AHORROS
            WHEN A.TASA LIKE 'ÑAAGI' AND A.TASA LIKE 'ÑABGI' 
            AND A.TASA LIKE 'ÑBEGI' THEN 'FORWARDS' -- FORWARDS
            WHEN A.TASA='/AAFE' AND A.TASA='/AAI9' AND A.TASA='/AA0A' 
            THEN 'DERECHOS FIDUCIARIOS' 
            --PARA DERECHOS FIDUCIARIOS EN JT Y HO
            WHEN A.TASA='8AAGK' AND A.TASA='8ACGK' AND A.TASA='8ABGK' 
            AND A.POR='HO-L' THEN 'EDIFICIOS OLD MUTUAL' 
            -- SON LOS INMUEBLES QUE PERTENECEN A OLD MUTUAL. 
            END)KEYA

            FROM SK_596_T AS A
            LEFT JOIN SK_596_Y B ON A.TITULO=B.TITULO
            LEFT JOIN REVISION C ON A.MONEDA=C.ISIN
            WHERE A.NEMOTECNICOBOL!='TRM/PESO' AND 
            A.NEMOTECNICOBOL!='USD/EUP' AND A.NEMOTECNICOBOL!='TRM/MXN' AND A.NEMOTECNICOBOL!='USD/GBP'""", (f1,))
        '''
        Aca estamos modificando la tasa facial para que podamos operarla con las cuentas de ahorro. 
        '''
        c.execute('''
            UPDATE NEW_596
            SET FACIAL=REPLACE(FACIAL,'-Nomi','')''')
        c.execute('''
            UPDATE NEW_596
            SET FACIAL=REPLACE(FACIAL,'-Nom','')''')
        c.execute('''
            UPDATE NEW_596
            SET FACIAL=REPLACE(FACIAL,'-Efec','')''')
        c.execute('''
            UPDATE NEW_596
            SET FACIAL=REPLACE(FACIAL,'-Efe','')''')

        #------------------------------------------------------------------------------------------------- TABLE: INTERESES Y DIVIDENDOS -- PRECIO COMPRA Y VENTA
        c.execute("""
            CREATE TABLE INT_DIV AS
            SELECT CONSEC, TRANSACCION, SUM(VRRECIBIDO)AS VRRECIBIDO
            FROM SK_583_T
            WHERE TRANSACCION='Cobro Dividendos' OR 
            TRANSACCION='Cobro Intereses'
            OR TRANSACCION='Reintegro Capital'
            GROUP BY CONSEC""")

        c.execute("""
            CREATE TABLE COMP_VENT AS
            SELECT CONSEC, TRANSACCION, ESPECIE, PRECIOOPE
            FROM SK_583_T
            WHERE TRANSACCION='Compra' OR TRANSACCION='Venta'""")
        
        c.execute("""
            CREATE TABLE INC_RET_CAPITAL AS
            SELECT CONSEC, TRANSACCION, TIPOOPER, MONED, VALOPERACIÓN, PRECIOOPE,
            (CASE
            WHEN TRANSACCION='Retiro Capital' THEN -VRRECIBIDO
            WHEN TRANSACCION='Incremento Capital' THEN VRRECIBIDO
            END)VRRECIBIDO
            FROM SK_583_T
            WHERE TRANSACCION='Retiro Capital' OR TRANSACCION='Incremento Capital'""")

        c.execute("""
            CREATE TABLE INC_RET_CAPITAL_II AS
            SELECT DISTINCT CONSEC, TRANSACCION, SUM(VRRECIBIDO) AS NETO 
            FROM INC_RET_CAPITAL 
            GROUP BY CONSEC""")

        c.execute("""
            CREATE TABLE VAL_TASA_CASH AS
            SELECT A.*, B.PRECIO_T, B.PRECIO_Y , 
            (CASE
            WHEN A.TRANSACCION='Incremento Capital' THEN ((A.VALOPERACIÓN*B.PRECIO_Y)-VRRECIBIDO)
            WHEN A.TRANSACCION='Retiro Capital' THEN (-(A.VALOPERACIÓN*B.PRECIO_Y)-VRRECIBIDO)
            END)AS VAL_X_TASA
            FROM INC_RET_CAPITAL AS A
            LEFT JOIN REV_TOTAL AS B ON A.MONED=B.ISIN
            WHERE (A.TRANSACCION='Incremento Capital' OR A.TRANSACCION='Retiro Capital') AND A.TIPOOPER='Cash'""")

        c.execute("""
            CREATE TABLE VAL_TASA_CASH_II AS
            SELECT DISTINCT CONSEC, TRANSACCION, SUM(VAL_X_TASA) AS T_VALxTASA 
            FROM VAL_TASA_CASH 
            GROUP BY CONSEC""")
        #------------------------------------------------------------------------------------------------- TABLE: BASE VALORACION

        c.execute("""
            CREATE TABLE BASE_VALORACION AS
            SELECT A.ESPECIE, A.TITULO, A.EMISION, A.F_VCTO, 
            A.VLR_MER_OR, A.NOMINAL_T, A.NOMINAL_Y, A.VLR_COMPRA,
            A.FACIAL, A.F_COMPRA, A.MET, A.MONEDA, A.VLR_MER_T, 
            (CASE
            WHEN A.F_COMPRA=? THEN A.VLR_COMPRA
            ELSE A.VLR_MER_Y
            END)VLR_MER_Y,
            A.POR, A.MONEDA_T, A.MONEDA_Y, A.KEYA, 
            B.PRECIO_T, B.PRECIO_Y, B.'CHANGE_%', B.FILE, 
            F.PRECIOOPE AS 'PRE_C_V', D.VRRECIBIDO AS 'INT_DIV',
            G.NETO AS 'INCR_RET', H.T_VALxTASA, A.LLAVE, E.TIPO
            FROM NEW_596 AS A
            LEFT JOIN REVISION AS B ON A.KEYA=B.ISIN
            LEFT JOIN INT_DIV AS D ON A.TITULO=D.CONSEC
            LEFT JOIN ESPECIES AS E ON A.LLAVE=E.LLAVE
            LEFT JOIN COMP_VENT AS F ON A.TITULO=F.CONSEC
            LEFT JOIN INC_RET_CAPITAL_II AS G ON A.TITULO=G.CONSEC
            LEFT JOIN VAL_TASA_CASH_II AS H ON A.TITULO=H.CONSEC""", (f1,))

        print('Table BASE_VALORACION was created')

        #------------------------------------------------------------------------------------------------- TABLE: REVISION DEF
        c.execute("""
            CREATE TABLE REVISION_DEF AS
            SELECT *,
            (CASE 
            WHEN (LLAVE='ERBP9' AND POR='92R') THEN (106697493950000.00*0.000001)
            WHEN LLAVE='2ACAC' THEN (NOMINAL_T*180138.96)
            WHEN LLAVE='2FIU1' THEN (NOMINAL_T*9687.340000)
            WHEN LLAVE='8LTGK' THEN 1054949999.63
            WHEN LLAVE='2BVHA' THEN (VLR_MER_OR*18368.206568)
            WHEN LLAVE='FVBQA' THEN (VLR_MER_OR*13593.114169)
            WHEN LLAVE='JZCJ3' THEN (VLR_MER_OR *1.064920* MONEDA_T)
            WHEN LLAVE='JZAXO' THEN (VLR_MER_OR *1.673050* MONEDA_T)
            WHEN LLAVE='JZAVN' THEN (VLR_MER_OR *1.082659* MONEDA_T)
            WHEN LLAVE='JHCKT' THEN (VLR_MER_OR *0.938460* MONEDA_T)
            WHEN LLAVE='JGDKT' THEN (VLR_MER_OR *1.160131* MONEDA_T)
            WHEN LLAVE='JZAKT' THEN (VLR_MER_OR *1.076858* MONEDA_T)
            WHEN LLAVE='JHPKT' THEN (VLR_MER_OR *0.958241* MONEDA_T)
            WHEN LLAVE='JZAPJ' THEN (VLR_MER_OR *0.816438* MONEDA_T)
            WHEN LLAVE='JZDP6' THEN (VLR_MER_OR *0.845205* MONEDA_T)
            WHEN LLAVE='JHM0Y' THEN (VLR_MER_OR *0.978898* MONEDA_T)
            WHEN LLAVE='JZAQK' THEN (VLR_MER_OR *1.041950* MONEDA_T)
            WHEN LLAVE='JZAOK' THEN (VLR_MER_OR *1.183056* MONEDA_T)
            WHEN LLAVE='JHHJ2' THEN (VLR_MER_OR *0.899836* MONEDA_T)
            WHEN LLAVE='JHIJ4' THEN (VLR_MER_OR *1.082530* MONEDA_T)
            WHEN LLAVE='JZA1X' THEN (VLR_MER_OR *1.024280* MONEDA_T)
            WHEN LLAVE='JZBJQ' THEN (VLR_MER_OR *1.000409* MONEDA_T)
            WHEN LLAVE='JHDJQ' THEN (VLR_MER_OR *0.946999* MONEDA_T)
            WHEN LLAVE='JZANQ' THEN (VLR_MER_OR *0.984023* MONEDA_T)
            WHEN LLAVE='JZEXO' THEN (VLR_MER_OR *1.638932* MONEDA_T)
            WHEN LLAVE='JZAKE' THEN (VLR_MER_OR *0.943544* MONEDA_T)
            WHEN LLAVE='JZAY0' THEN (VLR_MER_OR *1.173927* MONEDA_T)
            WHEN LLAVE='JZASS' THEN (VLR_MER_OR *1.008909* MONEDA_T)
            WHEN LLAVE='JHKK0' THEN (VLR_MER_OR *0.976514* MONEDA_T)
            WHEN LLAVE='JZAVX' THEN (VLR_MER_OR *0.981900* MONEDA_T)
            WHEN LLAVE='JHS6\' THEN (VLR_MER_OR *0.885150* MONEDA_T)
            WHEN LLAVE='JZAVW' THEN (VLR_MER_OR *1.080053* MONEDA_T)
            WHEN LLAVE='JZFVW' THEN (VLR_MER_OR *1.079829* MONEDA_T)
            WHEN TIPO='FCPE' OR TIPO="DFI" OR TIPO='FONDOS DE PENSION' 
            THEN (VLR_MER_OR * MONEDA_T)
            WHEN TIPO='FM' THEN (VLR_MER_OR * MONEDA_T * PRECIO_T)
            WHEN TIPO='FIC' OR TIPO='FCP' THEN (VLR_MER_OR * PRECIO_T)
            WHEN TIPO='CASH' OR TIPO='CTA AHORROS' OR TIPO='COLATERAL' 
            THEN (NOMINAL_T * MONEDA_T)
            WHEN TIPO='ADR' OR TIPO='ETF' OR TIPO='ACCION INTERNACIONAL' 
            THEN (NOMINAL_T * MONEDA_T * PRECIO_T)
            WHEN TIPO='BONO INTERNACIONAL' OR TIPO='BONO UVR' OR 
            TIPO='CDT UVR' OR TIPO='SUBORDINADO INTERNACIONAL' OR 
            TIPO='SUBORDINADO UVR' OR TIPO='TES UVR' 
            OR TIPO='TIPS' OR TIPO='TREASURY' OR TIPO='YANKEE' OR 
            TIPO="TBILL" OR TIPO="TD" OR TIPO="NESTR" 
            THEN (NOMINAL_T * MONEDA_T * (PRECIO_T/100))
            WHEN TIPO='ACCION' OR TIPO='ESTRATEGIAS'  
            THEN (NOMINAL_T * PRECIO_T)
            WHEN TIPO='BONO' OR TIPO='CDT' OR TIPO='STRUCTURADO' 
            OR TIPO='SUBORDINADO' OR TIPO='TES PESOS' 
            OR TIPO='TITULARIZADORA' OR TIPO='PAPEL COMERCIAL' 
            THEN (NOMINAL_T * (PRECIO_T/100))
            WHEN TIPO='FONDOCRENA' THEN (VLR_MER_OR*PRECIO_T)
            WHEN TIPO='ANTICIPO' OR TIPO='FIDEICOMISO' 
            OR TIPO='LOTE'  THEN VLR_MER_T
            WHEN TIPO='CREDITO' THEN VLR_MER_T
            END)VLR_MERCADO_T,
            (CASE 
            WHEN F_COMPRA=? THEN VLR_MER_Y
            WHEN (LLAVE='ERBP9' AND POR='92R') THEN (106697493950000.00*0.000001)
            WHEN LLAVE='2ACAC' THEN (NOMINAL_Y*180138.96)
            WHEN LLAVE='JZCJ3' THEN (VLR_MER_OR *1.064920* MONEDA_Y)
            WHEN LLAVE='JZAXO' THEN (VLR_MER_OR *1.673050* MONEDA_Y)
            WHEN LLAVE='JZAVN' THEN (VLR_MER_OR *1.082659* MONEDA_Y)
            WHEN LLAVE='JHCKT' THEN (VLR_MER_OR *0.938460* MONEDA_Y)
            WHEN LLAVE='JGDKT' THEN (VLR_MER_OR *1.160131* MONEDA_Y)
            WHEN LLAVE='JZAKT' THEN (VLR_MER_OR *1.076858* MONEDA_Y)
            WHEN LLAVE='JHPKT' THEN (VLR_MER_OR *0.958241* MONEDA_Y)
            WHEN LLAVE='JZAPJ' THEN (VLR_MER_OR *0.816438* MONEDA_Y)
            WHEN LLAVE='JZDP6' THEN (VLR_MER_OR *0.845205* MONEDA_Y)
            WHEN LLAVE='JHM0Y' THEN (VLR_MER_OR *0.978898* MONEDA_Y)
            WHEN LLAVE='JZAQK' THEN (VLR_MER_OR *1.041950* MONEDA_Y)
            WHEN LLAVE='JZAOK' THEN (VLR_MER_OR *1.183056* MONEDA_Y)
            WHEN LLAVE='JHHJ2' THEN (VLR_MER_OR *0.899836* MONEDA_Y)
            WHEN LLAVE='JHIJ4' THEN (VLR_MER_OR *1.082530* MONEDA_Y)
            WHEN LLAVE='JZA1X' THEN (VLR_MER_OR *1.072365* MONEDA_Y)
            WHEN LLAVE='JZBJQ' THEN (VLR_MER_OR *1.000409* MONEDA_Y)
            WHEN LLAVE='JHDJQ' THEN (VLR_MER_OR *0.946999* MONEDA_Y) 
            WHEN LLAVE='JZANQ' THEN (VLR_MER_OR *0.984023* MONEDA_Y)
            WHEN LLAVE='JZEXO' THEN (VLR_MER_OR *1.638932* MONEDA_Y)
            WHEN LLAVE='JZAKE' THEN (VLR_MER_OR *0.943544* MONEDA_Y)
            WHEN LLAVE='JZAY0' THEN (VLR_MER_OR *1.173927* MONEDA_Y)
            WHEN LLAVE='JZASS' THEN (VLR_MER_OR *1.008909* MONEDA_Y)
            WHEN LLAVE='JHKK0' THEN (VLR_MER_OR *0.976514* MONEDA_Y)
            WHEN LLAVE='JZAVX' THEN (VLR_MER_OR *0.981900* MONEDA_Y)
            WHEN LLAVE='JZAVW' THEN (VLR_MER_OR *1.080053* MONEDA_Y)
            WHEN LLAVE='JZFVW' THEN (VLR_MER_OR *1.079829* MONEDA_Y)
            WHEN LLAVE='2FIU1' THEN (NOMINAL_Y*9687.340000)
            WHEN LLAVE='8LTGK' THEN 1054949999.63
            WHEN LLAVE='2BVHA' THEN (VLR_MER_OR*18368.206568)
            WHEN LLAVE='FVBQA' THEN (VLR_MER_OR*13593.114169)
            WHEN TIPO='FCPE' OR TIPO="DFI" OR TIPO='FONDOS DE PENSION' 
            THEN (VLR_MER_OR * MONEDA_Y)
            WHEN TIPO='FM' THEN (VLR_MER_OR * MONEDA_Y * PRECIO_Y)
            WHEN TIPO='FIC' OR TIPO='FCP' THEN (VLR_MER_OR * PRECIO_Y)
            WHEN TIPO='CASH' OR TIPO='CTA AHORROS' OR TIPO='COLATERAL' 
            THEN (NOMINAL_Y * MONEDA_Y)
            WHEN TIPO='ADR' OR TIPO='ETF' OR TIPO='ACCION INTERNACIONAL' 
            THEN (NOMINAL_Y * MONEDA_Y * PRECIO_Y)
            WHEN TIPO='BONO INTERNACIONAL' OR TIPO='BONO UVR' 
            OR TIPO='CDT UVR' OR TIPO='SUBORDINADO INTERNACIONAL' 
            OR TIPO='SUBORDINADO UVR' OR TIPO='TES UVR' 
            OR TIPO='TIPS' OR TIPO='TREASURY' OR TIPO='YANKEE' 
            OR TIPO="TBILL" OR TIPO="TD" OR TIPO="NESTR" 
            THEN (NOMINAL_Y * MONEDA_Y * (PRECIO_Y/100))
            WHEN TIPO='ACCION' OR TIPO='ESTRATEGIAS' 
            THEN (NOMINAL_Y * PRECIO_Y)
            WHEN TIPO='BONO' OR TIPO='CDT' OR TIPO='STRUCTURADO' 
            OR TIPO='SUBORDINADO' OR TIPO='TES PESOS' 
            OR TIPO='TITULARIZADORA' OR TIPO='PAPEL COMERCIAL' 
            THEN (NOMINAL_Y * (PRECIO_Y/100))
            WHEN TIPO='FONDOCRENA' THEN (VLR_MER_OR*PRECIO_Y)
            WHEN TIPO='ANTICIPO' OR TIPO='FIDEICOMISO' 
            OR TIPO='LOTE'  THEN VLR_MER_Y
            WHEN TIPO='CREDITO' THEN VLR_MER_Y
            END)VLR_MERCADO_Y
            FROM BASE_VALORACION""",(f1,))
        
        print('Table REVISION_DEF was created')

        #------------------------------------------------------------------------------------------------- TABLE: REVISION DEF CAUSACION

        c.execute("""
            CREATE TABLE REVISION_DEF_CAUSACION AS
            SELECT *, 
            (CASE 
            WHEN TIPO='CASH' THEN (NOMINAL_T*(MONEDA_T-MONEDA_Y))+IFNULL(T_VALxTASA,0)
            WHEN TIPO='CTA AHORROS' THEN (NOMINAL_T*((FACIAL/100)/365))
            ELSE (VLR_MERCADO_T-IFNULL(VLR_MERCADO_Y,0)+IFNULL(REVISION_DEF.INT_DIV,0))
            END)CAUSACION
            FROM REVISION_DEF""")
            
        print('Table REVISION_DEF_CAUSACION was created')

        conn.commit()
        conn.close()

        print('process base de valoracion ended')

#%%

    def consulta_bd(self):
        '''
        En este metodo o función realizaremos las consultas a la base 
        de datos. Estas consultas tambien pueden ser  realizadas desde
        cualquier gestor de base de datos

        Returns
        -------
        None.

        '''
        date1=self.getting_date1()[0]
        conn=sqlite3.connect("Revisiones2021.3.4.db")
        c=conn.cursor()

        #------------------------------------------------------------------------------------------------- CREA INFORME DE REVISION
        c.execute("""
            SELECT * FROM REVISION_DEF_CAUSACION
            """)

        consulta=c.fetchall()

        file="Informe_Revision"+str(date1)+".csv"

        with open(file, 'w', newline='') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter=';',quotechar='|', quoting=csv.QUOTE_MINIMAL)
            for row in consulta:
                spamwriter.writerow(row)

        print('Informe_Revision was created')


        #------------------------------------------------------------------------------------------------- TABLE: VALORACION_TIR

        c.execute("""
            CREATE TABLE VALORACION_TIR AS
            SELECT ESPECIE,TITULO,F_COMPRA,ISIN, NEMOTECNICOBOL,EMISION,F_VCTO,MOD,FACIAL
            FROM SK_596_T
            WHERE MET='TC'
            """)

        print('Table VALORACION_TIR was created')

        #------------------------------------------------------------------------------------------------- CREA INFORME DE REVISION
        c.execute("""
            SELECT * FROM VALORACION_TIR
            """)

        consulta=c.fetchall()

        file="Valoracion_TIR"+str(date1)+".csv"

        with open(file, 'w', newline='') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter=';',quotechar='|', quoting=csv.QUOTE_MINIMAL)
            for row in consulta:
                spamwriter.writerow(row)

        print('Informe Valoracion_TIR was created')

        #------------------------------------------------------------------------------------------------- CREA CONSULTA VARIACIONES TOTALES
        c.execute("""
            SELECT * FROM REVISION
            """)

        consulta=c.fetchall()

        file="Var_Bolsa_"+str(date1)+".csv"

        with open(file, 'w', newline='') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter=';',quotechar='|', quoting=csv.QUOTE_MINIMAL)
            for row in consulta:
                spamwriter.writerow(row)

        print('Informe Var_Bolsa was created')

        conn.commit()
        conn.close()

        print('PROCESS TOTALLY FINISHED')


#%%

f=path_dates()
f.fechas_trabajo()
f.getting_date1()
f.getting_date2()
f.setting_path1()
f.setting_path2()
f.clean_tables()
f.archivos_1()
f.archivos_2()
f.revision_total()
f.base_valoracion()
f.consulta_bd()
        
    
    

