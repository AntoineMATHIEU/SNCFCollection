import pandas as pd
import requests
import json
import datetime

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

# Max 250
nb_trains = 5
token = 'e7b7fedd-71d0-48c6-8cc7-749e22ba8e80'

req_gare = requests.get("https://ressources.data.sncf.com/api/records/1.0/search/?dataset=referentiel-gares-voyageurs&q=&rows=3220&sort=gare_alias_libelle_noncontraint&facet=departement_libellemin&facet=segmentdrg_libelle&facet=gare_agencegc_libelle&facet=gare_regionsncf_libelle&facet=gare_ug_libelle")
doc_gare = json.loads(req_gare.text)
row_gare = len(doc_gare['records'])
df_dic = pd.DataFrame(doc_gare['records'])
df_dic = pd.DataFrame(list(df_dic['fields']))
df_dic = df_dic[['alias_libelle_noncontraint','uic_code']]

df_dic['uic_code'] = df_dic['uic_code'].apply(removezero)

df_dic.convert_dtypes()
dic_gare = df_dic.set_index('alias_libelle_noncontraint').T.to_dict('list')

df = pd.read_csv('liste_gares_choisi.csv')
dic_gare = df_dic.set_index('alias_libelle_noncontraint').T.to_dict('list')

df_final = pd.DataFrame()

for gare in dic_gare:
    print(gare)
    link = 'https://api.sncf.com/v1/coverage/sncf/stop_areas/stop_area:' + dic_gare[gare][0] + '/arrivals?count=' + str(nb_trains)
    req = requests.get(link,auth=(token, ''))

    doc = json.loads(req.text)
    row = len(doc['arrivals'])
    print(f'Nombre de trains : {row}')

    if row !=O:

        df = pd.DataFrame(doc['arrivals'])
        df_gare = pd.DataFrame(list(df['display_informations']))
        df_heure = pd.DataFrame(list(df['stop_date_time']))
        df_id = pd.DataFrame(list(df['links']))
        df_id = pd.DataFrame(list(df_id[1]))

        df_heure['jour'] = df_heure['departure_date_time'].apply(get_day)

        df_heure = df_heure.drop(index=df_heure[df_heure['base_departure_date_time'].isnull()].index)
        df_gare = df_gare.drop(index=df_gare[df_gare['network']=='additional service'].index)

        df_heure['arrival_date_time'] = df_heure['arrival_date_time'].apply(del_day)
        df_heure['base_arrival_date_time'] = df_heure['base_arrival_date_time'].apply(del_day)

        df_heure['retard'] = df_heure['arrival_date_time'].apply(conv_min) - df_heure['base_arrival_date_time'].apply(conv_min)

        df_heure['heure'] = df_heure['arrival_date_time'].apply(str_tps)
        df_heure['old_heure'] = df_heure['base_arrival_date_time'].apply(str_tps)

        df_gare['direction'] = df_gare['direction'].apply(del_par)

        df_gare = df_gare[['direction','network','trip_short_name']]
        df_gare.rename(columns = {'direction':'Destination'}, inplace = True)
        df_gare.rename(columns = {'network':'Train'}, inplace = True)
        df_gare.rename(columns = {'trip_short_name':'Numéro'}, inplace = True)

        df_gare['Jour'] = df_heure['jour']
        df_gare['Arrivée (réelle)'] = df_heure['heure']
        df_gare['Arrivée (prévue)'] = df_heure['old_heure']
        df_gare['Retard (min)'] = df_heure['retard']
        df_gare['id'] = df_id['id']

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

        # On retire les gares que le trains a déjà traversées avant d'arriver à la gare choisie
        # Il existe des gares à Paris qui ont plusieurs noms qui ne sont pas tous indéxés dans le dataset des gares françaises
        # On créé donc une exception pour chacune d'entre elles
        if gare not in liste_arrets:
            if "Paris Gare de Lyon" in liste_arrets:
                index_gare = liste_arrets.index("Paris Gare de Lyon")
            if "Paris - Gare de Lyon - Banlieue" in liste_arrets:
                index_gare = liste_arrets.index("Paris - Gare de Lyon - Banlieue")
            if "Gare du Nord Surface" in liste_arrets:
                index_gare = liste_arrets.index("Gare du Nord Surface")
        else:
            index_gare = liste_arrets.index(gare)
            
        # On ajoute donc que les gares pas encore traversées
        liste_arrets = liste_arrets[index_gare+1:]
        arrets.append(liste_arrets)

    df_gare['Cause'] = causes
    df_gare['Arrêts'] = arrets
    df_gare = df_gare.drop(['id'], axis=1)

    df_final = pd.concat([df_final, df_gare], ignore_index=True)
  
df_gare.to_csv('Arrival.csv', sep=',', index=False, header=True)

