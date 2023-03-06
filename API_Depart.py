import pandas as pd
import requests
import json
import datetime
import os

nb_trains = 10
token = 'e7b7fedd-71d0-48c6-8cc7-749e22ba8e80'

def removezero(string):
    return 'SNCF:' + str(string)[2:]

def get_day(string):
    string = string[:8]
    return string[6:8]+'-'+string[4:6]+'-'+string[0:4]

def del_day(string):
    return str(string)[9:]

def conv_min(string):
    return int(string[0:2])*60 + int(string[2:4])

def str_tps(str):
    return datetime.datetime.strptime(str, '%H%M%S').time()

def del_par(string):
    index = string.find("(")
    return string[:index]

def get_name(string):
    string = string[10:]
    index_fin = string.find("', 'links'")
    return string[:index_fin]

def get_id(string):
    index_deb = string.find("'id': 'stop_point:")
    string = string[index_deb+18:]
    return string[:13]

df_dic = pd.read_excel('select_gares.xlsx')
dic_gare = df_dic.set_index('alias_libelle_noncontraint').T.to_dict('list')

df_final = pd.DataFrame()

for gare in dic_gare:
    print(gare)
    link = 'https://api.sncf.com/v1/coverage/sncf/stop_areas/stop_area:' + dic_gare[gare][0] + '/departures?count=' + str(nb_trains)
    req = requests.get(link,auth=(token, ''))

    doc = json.loads(req.text)
    row = len(doc['departures'])
    #print(f'Nombre de trains : {row}')

    if row != 0:
        df = pd.DataFrame(doc['departures'])
        df_gare = pd.DataFrame(list(df['display_informations']))
        df_heure = pd.DataFrame(list(df['stop_date_time']))
        df_id = pd.DataFrame(list(df['links']))
        df_id = pd.DataFrame(list(df_id[1]))

        df_heure['jour'] = df_heure['departure_date_time'].apply(get_day)

        supr = df_gare.loc[df_gare['network'] == 'RER'].index
        df_gare = df_gare.drop(supr)
        df_heure = df_heure.drop(supr)

        supr = df_gare.loc[df_gare['network'] == 'TRANSILIEN'].index
        df_gare = df_gare.drop(supr)
        df_heure = df_heure.drop(supr)

        supr = df_gare.loc[df_heure['base_departure_date_time'].isnull()].index
        df_gare = df_gare.drop(supr)
        df_heure = df_heure.drop(supr)

        df_heure['departure_date_time'] = df_heure['departure_date_time'].apply(del_day)
        df_heure['base_departure_date_time'] = df_heure['base_departure_date_time'].apply(del_day)

        df_heure['retard'] = df_heure['departure_date_time'].apply(conv_min) - df_heure['base_departure_date_time'].apply(conv_min)

        df_heure['heure'] = df_heure['departure_date_time'].apply(str_tps)
        df_heure['old_heure'] = df_heure['base_departure_date_time'].apply(str_tps)

        df_gare['direction'] = df_gare['direction'].apply(del_par)

        if len(df_gare) != 0:
            df_gare = df_gare[['direction','network','trip_short_name']]
            df_gare.rename(columns = {'direction':'Destination'}, inplace = True)
            df_gare.rename(columns = {'network':'Train'}, inplace = True)
            df_gare.rename(columns = {'trip_short_name':'Numéro'}, inplace = True)

            df_gare['Jour'] = df_heure['jour']
            df_gare['Départ (réel)'] = df_heure['heure']
            df_gare['Départ (prévu)'] = df_heure['old_heure']
            df_gare['Retard (min)'] = df_heure['retard']
            df_gare['id'] = df_id['id']

        provenance = []
        arrets = []
        causes = []

        for index, row in df_gare.iterrows():
            id = row['id']
            
            if 'RealTime' in id:
                index_id = id.index("RealTime")
                id = id[:index_id-1]

            link_voyage = 'https://api.sncf.com/v1/coverage/sncf/vehicle_journeys/' + id
            req_arret = requests.get(link_voyage ,auth=(token, ''))
            doc_voyage = json.loads(req_arret.text)

            df_arret = pd.DataFrame(doc_voyage['vehicle_journeys'])
            df_arret = pd.DataFrame(list(df_arret['stop_times']))
            df_arret = df_arret.T
            df_arret = pd.DataFrame(list(df_arret[0]))
            df_arret['stop_point_id'] = df_arret['stop_point'].astype('str').apply(get_id)
            df_arret['stop_point'] = df_arret['stop_point'].astype('str').apply(get_name)
            provenance.append(df_arret['stop_point'][0])

            if row['Retard (min)'] != 0:
                df_retard = pd.DataFrame(doc_voyage['disruptions'])
                if 'messages' in df_retard:
                    df_retard = pd.DataFrame(list(df_retard['messages'][0]))
                    causes.append(df_retard.iloc[0]['text'])
                else:
                    causes.append("Retard non expliqué")
            else:
                causes.append("")

            liste_arrets = [list(df_arret['stop_point']),list(df_arret['stop_point_id'])]
            index_gare = liste_arrets[1].index(dic_gare[gare][0])
            
            liste_arrets = liste_arrets[0][index_gare+1:]
            arrets.append(liste_arrets)


        df_gare['Cause'] = causes
        df_gare['Arrêts'] = arrets
        df_gare.insert(0, 'Provenance', provenance)
        if len(df_gare) != 0:
            df_gare = df_gare.drop(['id'], axis=1)

        print(f'Nombre de trains : {len(df_gare)}')
        if len(df_gare) != 0:
            df_final = pd.concat([df_final, df_gare], ignore_index=True)

if os.path.exists('Departure.csv'):
    os.remove('Departure.csv')

df_final.to_csv('Departure.csv', sep=',', index=False, header=True)