#!/usr/bin/env python
# coding: utf-8

# Ce script permet d'afficher les trains au départ de n'importe quelle gare française.
# 
# La liste des noms des gares française se trouve dans le fichier Excel **liste_gares.xlsx**

# # Code

# ## Import des Modules

# In[53]:


import pandas as pd
import requests
import json
import datetime


# ## Choix de la gare et du nombre de trains affichés

# In[54]:


gare = "Alès"

# Max 250
nb_trains = 20


# Mise en varaible du token de connexion à l'API SNCF V1

# In[55]:


token = 'e7b7fedd-71d0-48c6-8cc7-749e22ba8e80'


# ## Création du dictionnaire des gares françaises

# Requête à l'API SNCF (pas besoin de token ici) afin de récupérer la liste des gares françaises et l'identifiant associé

# In[56]:


req_gare = requests.get("https://ressources.data.sncf.com/api/records/1.0/search/?dataset=referentiel-gares-voyageurs&q=&rows=3220&sort=gare_alias_libelle_noncontraint&facet=departement_libellemin&facet=segmentdrg_libelle&facet=gare_agencegc_libelle&facet=gare_regionsncf_libelle&facet=gare_ug_libelle")
doc_gare = json.loads(req_gare.text)
row_gare = len(doc_gare['records'])
print(f'Nombre de gares : {row_gare}')


# On ne garde que le nom de la gare et l'identifiant

# In[57]:


df_dic = pd.DataFrame(doc_gare['records'])
df_dic = pd.DataFrame(list(df_dic['fields']))
df_dic = df_dic[['alias_libelle_noncontraint','uic_code']]


# On retire les `0` inutiles au début de l'identifiant de gare

# In[58]:


def removezero(string):
    return 'SNCF:' + str(string)[2:]

df_dic['uic_code'] = df_dic['uic_code'].apply(removezero)


# On convertit le dataframe en dictionnaire python

# In[59]:


df_dic.convert_dtypes()
dic_gare = df_dic.set_index('alias_libelle_noncontraint').T.to_dict('list')


# ## Obtention des trains à l'arrivée en gare

# Requête à l'API SNCF afin de récupérer la liste des trains à l'arrivée en gare

# In[60]:


link = 'https://api.sncf.com/v1/coverage/sncf/stop_areas/stop_area:' + dic_gare[gare][0] + '/arrivals?count=' + str(nb_trains)
req = requests.get(link,auth=(token, ''))
#print(link)


# In[61]:


doc = json.loads(req.text)
row = len(doc['arrivals'])
print(f'Nombre de trains : {row}')


# On découpe le résultat de la requête en 3 dataframes distincts :
# 
# - **df_gare** qui donne les informations sur la direction du train, son type (TER, TGV, etc.) et son numéro
# 
# - **df_heure** qui donne des informations sur un éventuel retard du train
# 
# - **df_id** qui contient l'identifiant du voyage, ce qui nous servira à récupérer d'autres données plus tard

# In[62]:


df = pd.DataFrame(doc['arrivals'])
df_gare = pd.DataFrame(list(df['display_informations']))
df_heure = pd.DataFrame(list(df['stop_date_time']))
df_id = pd.DataFrame(list(df['links']))
df_id = pd.DataFrame(list(df_id[1]))


# On récupère le jour de départ du train

# In[63]:


def get_day(string):
    string = string[:8]
    return string[6:8]+'-'+string[4:6]+'-'+string[0:4]

df_heure['jour'] = df_heure['departure_date_time'].apply(get_day)


# On ne garde que les trains en retard

# In[64]:


df_heure = df_heure.drop(index=df_heure[df_heure['base_departure_date_time'].isnull()].index)
df_gare = df_gare.drop(index=df_gare[df_gare['network']=='additional service'].index)


# On récupère l'heure d'arrivée prévue et réelle du train

# In[65]:


def del_day(string):
    return string[9:]

df_heure['arrival_date_time'] = df_heure['arrival_date_time'].apply(del_day)
df_heure['base_arrival_date_time'] = df_heure['base_arrival_date_time'].apply(del_day)


# On calcule le retard du train et on le convertit au format heure de `datetime`

# In[66]:


def conv_min(string):
    return int(string[0:2])*60 + int(string[2:4])

df_heure['retard'] = df_heure['arrival_date_time'].apply(conv_min) - df_heure['base_arrival_date_time'].apply(conv_min)


# In[67]:


def str_tps(str):
    return datetime.datetime.strptime(str, '%H%M%S').time()

df_heure['heure'] = df_heure['arrival_date_time'].apply(str_tps)
df_heure['old_heure'] = df_heure['base_arrival_date_time'].apply(str_tps)


# On retire le nom de la ville ou se situe la gare pour plus de lisibilité.
# 
# _Exemple :_ `Paris Gare de Lyon (Paris)` devient `Paris Gare de Lyon`

# In[68]:


def del_par(string):
    index = string.find("(")
    return string[:index]

df_gare['direction'] = df_gare['direction'].apply(del_par)


# On renome les colonnes du dataframe **df_gare** et on y ajoute :
# 
# - Le jour de départ
# 
# - L'heure d'arrivée réelle
# 
# - L'heure d'arrivée prévue
# 
# - Le retard à l'arrivée en minutes du train
# 
# - L'identifiant du voyage

# In[69]:


df_gare = df_gare[['direction','network','trip_short_name']]
df_gare.rename(columns = {'direction':'Destination'}, inplace = True)
df_gare.rename(columns = {'network':'Train'}, inplace = True)
df_gare.rename(columns = {'trip_short_name':'Numéro'}, inplace = True)

df_gare['Jour'] = df_heure['jour']
df_gare['Arrivée (réelle)'] = df_heure['heure']
df_gare['Arrivée (prévue)'] = df_heure['old_heure']
df_gare['Retard (min)'] = df_heure['retard']
df_gare['id'] = df_id['id']


# ## Obtention des arrêts et de la cause de retard du train

# Création d'une fonction permettant de récupérer uniquement le nom de la gare dans le json et de supprimer les données superflues

# In[70]:


def get_name(string):
    string = string[10:]
    index_fin = string.find("', 'links'")
    return string[:index_fin]


# Pour chaque train, on effectue un requête grâce à l'**id** du voyage afin de récupérer les arrêts et l'éventuelle cause du retard de celui-ci

# In[71]:


arrets = []
causes = []
for index, row in df_gare.iterrows():
    id = row['id']
    
    # Il faut retirer la partie 'RealTime' de l'id pour faire la requête
    if 'RealTime' in id:
        index_id = id.index("RealTime")
        id = id[:index_id-1]
    
    # On effectue la requête
    link_voyage = 'https://api.sncf.com/v1/coverage/sncf/vehicle_journeys/' + id
    req_arret = requests.get(link_voyage ,auth=(token, ''))
    doc_voyage = json.loads(req_arret.text)

    # On récupère la liste des arrêts du train
    df_arret = pd.DataFrame(doc_voyage['vehicle_journeys'])
    df_arret = pd.DataFrame(list(df_arret['stop_times']))
    df_arret = df_arret.T
    df_arret = pd.DataFrame(list(df_arret[0]))
    df_arret['stop_point'] = df_arret['stop_point'].astype('str').apply(get_name)

    # Si le train est en retard, on récupère la cause du retard
    # On renvoie "Retard non expliqué" si la SNCF ne fournit pas plus d'informations sur le retard
    if row['Retard (min)'] != 0:
        df_retard = pd.DataFrame(doc_voyage['disruptions'])
        if 'messages' in df_retard:
            df_retard = pd.DataFrame(list(df_retard['messages'][0]))
            causes.append(df_retard.iloc[0]['text'])
        else:
            causes.append("Retard non expliqué")
    else:
        causes.append("")

    # On ajoute tous les arrêts du train
    liste_arrets = list(df_arret['stop_point'])
    arrets.append(liste_arrets)


# On ajoute la cause du retard ainsi que les arrêts au dataframe **df_gare**
# On retire aussi l'id du voyage qui ne sert plus à rien

# In[72]:


df_gare['Cause'] = causes
df_gare['Arrêts'] = arrets
df_gare = df_gare.drop(['id'], axis=1)


# On affiche le dataframe final

# In[73]:


df_gare


# On exporte le dataframe en fichier _CSV_

# In[74]:


df_gare.to_csv('Arrival.csv', sep=',', index=False, header=True)

