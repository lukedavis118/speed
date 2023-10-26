# -*- coding: utf-8 -*-
"""
Created on Fri Jun  2 11:37:06 2023

@author: luke_
"""
from seleniumwire import webdriver
import requests
import pandas as pd
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
import json
from seleniumwire.utils import decode
from bs4 import BeautifulSoup
import geopy.distance as gd
import numpy as np
import datetime as dt
import undetected_chromedriver as uc
from webdriver_manager.chrome import ChromeDriverManager




def getToken(username,password):
    print('Attempting to login...')
    login_url = 'https://truckstop.force.com/Signin'
    url = 'https://main.truckstop.com/app/search/loads'
    
    
    
    # latestchromedriver = ChromeDriverManager().install()
    # #set options
    # chrome_options = uc.ChromeOptions()

    driver = uc.Chrome()#driver_executable_path=latestchromedriver, options=chrome_options)

    

    # chrome_options = uc.ChromeOptions()
    # driver = uc.Chrome(
    #     options=chrome_options,
    # )    
    driver.get(login_url)
    element = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
    
    username_field = driver.find_element('name','username')
    username_field.send_keys(username)
    
    password_field = driver.find_element('name','password')
    password_field.send_keys(password)
    
    loginButton = driver.find_element(By.CLASS_NAME,'loginBtn')
    loginButton.click()
    tokenURL = False
    while tokenURL == False:
        websiteID = driver.current_url
        if 'https://main.truckstop.com/?id=' in websiteID:
            tokenURL = True
        else:
            tokenURL = False
                      
    token = websiteID.replace('https://main.truckstop.com/?id=', 'https://v5-auth.truckstop.com/auth/token/')
    token = token.replace('&source=truckstop.my.site.com%2f&event=refresh', '')
    
    print('Successfully Retrieved Token!')
    driver.close
    return token

def truckstopLogin(session,username,password):
    print('Attempting to login...')
    login_url = 'https://truckstop.force.com/Signin'
    url = 'https://main.truckstop.com/app/search/loads'
            
    # Create the POST payload to login, but some values will be empty for now
    loginPayload={
        "AJAXREQUEST": "_viewRoot",
        "j_id0:j_id5": "j_id0:j_id5",
        "j_id0:j_id5:hiddenUsername": username,
        "j_id0:j_id5:hiddenPassword": password,
        "com.salesforce.visualforce.ViewState": "",
        "com.salesforce.visualforce.ViewStateVersion": "",
        "com.salesforce.visualforce.ViewStateMAC": "",
        "j_id0:j_id5:j_id6": "j_id0:j_id5:j_id6"
    }
    
    # Get the login page to pull certain info from it    
    page = session.get(login_url)
    html = BeautifulSoup(page.content,'html.parser')
        
    # Fill in the missing values inside loginPayload
    loginPayload["com.salesforce.visualforce.ViewState"] = html.find(
        attrs={'name': 'com.salesforce.visualforce.ViewState'})['value']
    
    loginPayload["com.salesforce.visualforce.ViewStateVersion"] = html.find(
        attrs={'name': 'com.salesforce.visualforce.ViewStateVersion'})['value']
    
    loginPayload["com.salesforce.visualforce.ViewStateMAC"] = html.find(
        attrs={'name': 'com.salesforce.visualforce.ViewStateMAC'})['value']
    
    # Perform the actual login within the session
    session.post(login_url, data=loginPayload,allow_redirects=True)

    return session

def getDieselPrice(driver):
    print("Retrieving today's average diesel price.")
    try:
        driver.get('https://gasprices.aaa.com/state-gas-price-averages/')
        table = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "tbody")))
        allStates = table.text.split('\n')
        diesel = float([row.split(' $') for row in allStates if 'Alabama' in row][0][-1])
    except:
        print("Diesel price not found. Defaulting to $4.00.")
        diesel = 4.0
    return diesel

def getCoordinates():
    import pickle
    with open('./coords.pickle','rb') as f:
        coords = pickle.load(f)
    return coords

def getTruckstopLoads(session,inputs,token):
    #countURL = 'https://loadsearch-graphql-api-prod.truckstop.com/v1/graphql?loadSearchCountQuery'
    #queryURL = 'https://loadsearch-graphql-api-prod.truckstop.com/v1/graphql?loadSearchDefaultSortQuery'
        
    print('Retreiving the total number of loads...')
    
    timeAvailable = min((inputs['date_end'] - inputs['date_start']).total_seconds()/3600,12)
    searchRadius = (timeAvailable-inputs['loadTime']) * inputs['avgSpeed'] / 2
    
    # Get the unique auth token to be used in other requests
    auth = json.loads(session.get(token).content.decode())['accessToken']
    
    # Add the token to a standard headers json
    authHeaders = {
        "Authorization": "Bearer " + auth,
        "Content-Length": "954",
        "Content-Type": "application/json"
    }

    # Build the payload to get the total load count
    countPayload = {
        "operationName": "loadSearchCountQuery",
        "query": "query loadSearchCountQuery($origin_radius: numeric!, $destination_radius: numeric!, $carrier_id: uuid!, $gl_carrier_user_id: String!, $equipment_ids: _int4!, $dh_origin_lat: numeric!, $dh_origin_lon: numeric!, $dh_destination_lat: numeric!, $dh_destination_lon: numeric!, $pickup_date_begin: timestamp!, $pickup_date_end: timestamp!) {\n  get_load_count_v2(\n    args: {origin_radius: $origin_radius, destination_radius: $destination_radius, carrier_id: $carrier_id, gl_carrier_user_id: $gl_carrier_user_id, equipment_ids: $equipment_ids, dh_origin_lat: $dh_origin_lat, dh_origin_lon: $dh_origin_lon, dh_destination_lat: $dh_destination_lat, dh_destination_lon: $dh_destination_lon, pickup_date_begin: $pickup_date_begin, pickup_date_end: $pickup_date_end}\n  ) {\n    count\n    __typename\n  }\n}\n",
        "variables": {
            "carrier_id": "DD1A4336-40B7-EB11-AAEA-065441B9C395",
            "destination_radius": searchRadius,
            "dh_destination_lat": inputs['endCoords'][0],
            "dh_destination_lon": inputs['endCoords'][1],
            "dh_origin_lat": inputs['startCoords'][0],
            "dh_origin_lon": inputs['startCoords'][1],
            "equipment_ids": "{12,15,16,17,18,48,59,60,61,62,63,65,67,68,69,76,78}",
            "gl_carrier_user_id": "0054X00000ENLQKQA5",
            "origin_radius": searchRadius,
            "pickup_date_begin": inputs['date_start'].strftime('%Y-%m-%d'),
            "pickup_date_end": (inputs['date_end']+dt.timedelta(days=1)).strftime('%Y-%m-%d')
        }
    }
    
    # Get the actual count now
    res = session.post('https://loadsearch-graphql-api-prod.truckstop.com/v1/graphql?loadSearchCountQuery',headers=authHeaders,json=countPayload)
    count = json.loads(res.text)['data']['get_load_count_v2'][0]['count']

    print('Retreiving each load available...')
    # Build the payload to get the list of loads
    loadsPayload = {
         "operationName":"loadSearchDefaultSortQuery",
        "variables": {
            "carrier_id": "DD1A4336-40B7-EB11-AAEA-065441B9C395",
            "destination_radius": searchRadius,
            "dh_destination_lat": inputs['endCoords'][0],
            "dh_destination_lon": inputs['endCoords'][1],
            "dh_origin_lat": inputs['startCoords'][0],
            "dh_origin_lon": inputs['startCoords'][1],
            "equipment_ids": "{12,15,16,17,18,48,59,60,61,62,63,65,67,68,69,76,78}",
            "gl_carrier_user_id": "0054X00000ENLQKQA5",
            "origin_radius": searchRadius,
            "pickup_date_begin": inputs['date_start'].strftime('%Y-%m-%d'),
            "pickup_date_end": (inputs['date_end']+dt.timedelta(days=1)).strftime('%Y-%m-%d'),
             "limit_num":100,
             "offset_num":0
         },
         "query":"query loadSearchDefaultSortQuery($origin_radius: numeric!, $destination_radius: numeric!, $carrier_id: uuid!, $gl_carrier_user_id: String!, $equipment_ids: _int4!, $dh_origin_lat: numeric!, $dh_origin_lon: numeric!, $dh_destination_lat: numeric!, $dh_destination_lon: numeric!, $pickup_date_begin: timestamp!, $pickup_date_end: timestamp!, $limit_num: numeric!, $offset_num: numeric!) {\n  get_loads_with_extra_data_v8_sort_by_default(\n    args: {origin_radius: $origin_radius, destination_radius: $destination_radius, carrier_id: $carrier_id, gl_carrier_user_id: $gl_carrier_user_id, equipment_ids: $equipment_ids, dh_origin_lat: $dh_origin_lat, dh_origin_lon: $dh_origin_lon, dh_destination_lat: $dh_destination_lat, dh_destination_lon: $dh_destination_lon, pickup_date_begin: $pickup_date_begin, pickup_date_end: $pickup_date_end, limit_num: $limit_num, offset_num: $offset_num}\n  ) {\n    ...GridLoadSearchFields\n    __typename\n  }\n}\n\nfragment GridLoadSearchFields on loads_grid_v2 {\n  id\n  loadStateId\n  phone\n  legacyLoadId\n  modeId\n  modeCode\n  originState\n  originCity\n  originCityState\n  originEarlyTime\n  originLateTime\n  originDeadhead\n  destinationState\n  destinationCity\n  destinationCityState\n  destinationDeadhead\n  tripDistance\n  dimensionsLength\n  dimensionsWeight\n  equipmentCode\n  postedRate\n  createdOn\n  updatedOn\n  isBookItNow\n  loadTrackingRequired\n  canBookItNow\n  allInRate\n  rpm\n  accountName\n  experienceFactor\n  daysToPay\n  bondTypeId\n  payEnabled\n  daysToPayInteger\n  equipmentOptions\n  __typename\n}\n"
     }
    
    # Get the first list of loads
    res = session.post('https://loadsearch-graphql-api-prod.truckstop.com/v1/graphql?loadSearchCountQuery', headers=authHeaders, json=loadsPayload)
    q = json.loads(res.text)
    data = q[list(q)[0]][list(q[list(q)[0]])[0]]
    
    # Continue getting additional loads until they match the count
    while len(data) < count:
        print("Adding to data...")
        # add length of data to the query and request again
        loadsPayload['variables']['offset_num'] = len(data)
        q = json.loads(session.post('https://loadsearch-graphql-api-prod.truckstop.com/v1/graphql?loadSearchCountQuery', headers=authHeaders, json=loadsPayload).text)
        data = data + q[list(q)[0]][list(q[list(q)[0]])[0]]
        
    return data

def getTruckstopLoads2(session,inputs2,token):
    #countURL = 'https://loadsearch-graphql-api-prod.truckstop.com/v1/graphql?loadSearchCountQuery'
    #queryURL = 'https://loadsearch-graphql-api-prod.truckstop.com/v1/graphql?loadSearchDefaultSortQuery'
        
    print('Retreiving the total number of loads...')
    
    timeAvailable = min((inputs2['date_end'] - inputs2['date_start']).total_seconds()/3600,12)
    searchRadius = (timeAvailable-inputs2['loadTime']) * inputs2['avgSpeed'] / 2
    
    # Get the unique auth token to be used in other requests
    auth = json.loads(session.get(token).content.decode())['accessToken']
    
    # Add the token to a standard headers json
    authHeaders = {
        "Authorization": "Bearer " + auth,
        "Content-Length": "954",
        "Content-Type": "application/json"
    }

    # Build the payload to get the total load count
    countPayload = {
        "operationName": "loadSearchCountQuery",
        "query": "query loadSearchCountQuery($origin_radius: numeric!, $destination_radius: numeric!, $carrier_id: uuid!, $gl_carrier_user_id: String!, $equipment_ids: _int4!, $dh_origin_lat: numeric!, $dh_origin_lon: numeric!, $dh_destination_lat: numeric!, $dh_destination_lon: numeric!, $pickup_date_begin: timestamp!, $pickup_date_end: timestamp!) {\n  get_load_count_v2(\n    args: {origin_radius: $origin_radius, destination_radius: $destination_radius, carrier_id: $carrier_id, gl_carrier_user_id: $gl_carrier_user_id, equipment_ids: $equipment_ids, dh_origin_lat: $dh_origin_lat, dh_origin_lon: $dh_origin_lon, dh_destination_lat: $dh_destination_lat, dh_destination_lon: $dh_destination_lon, pickup_date_begin: $pickup_date_begin, pickup_date_end: $pickup_date_end}\n  ) {\n    count\n    __typename\n  }\n}\n",
        "variables": {
            "carrier_id": "DD1A4336-40B7-EB11-AAEA-065441B9C395",
            "destination_radius": searchRadius,
            "dh_destination_lat": inputs2['endCoords'][0],
            "dh_destination_lon": inputs2['endCoords'][1],
            "dh_origin_lat": inputs2['startCoords'][0],
            "dh_origin_lon": inputs2['startCoords'][1],
            "equipment_ids": "{12,15,16,17,18,48,59,60,61,62,63,65,67,68,69,76,78}",
            "gl_carrier_user_id": "0054X00000ENLQKQA5",
            "origin_radius": searchRadius,
            "pickup_date_begin": inputs2['date_start'].strftime('%Y-%m-%d'),
            "pickup_date_end": (inputs2['date_end']+dt.timedelta(days=1)).strftime('%Y-%m-%d')
        }
    }
    
    # Get the actual count now
    res = session.post('https://loadsearch-graphql-api-prod.truckstop.com/v1/graphql?loadSearchCountQuery',headers=authHeaders,json=countPayload)
    count = json.loads(res.text)['data']['get_load_count_v2'][0]['count']

    print('Retreiving each load available...')
    # Build the payload to get the list of loads
    loadsPayload = {
         "operationName":"loadSearchDefaultSortQuery",
        "variables": {
            "carrier_id": "DD1A4336-40B7-EB11-AAEA-065441B9C395",
            "destination_radius": searchRadius,
            "dh_destination_lat": inputs2['endCoords'][0],
            "dh_destination_lon": inputs2['endCoords'][1],
            "dh_origin_lat": inputs2['startCoords'][0],
            "dh_origin_lon": inputs2['startCoords'][1],
            "equipment_ids": "{12,15,16,17,18,48,59,60,61,62,63,65,67,68,69,76,78}",
            "gl_carrier_user_id": "0054X00000ENLQKQA5",
            "origin_radius": searchRadius,
            "pickup_date_begin": inputs2['date_start'].strftime('%Y-%m-%d'),
            "pickup_date_end": (inputs2['date_end']+dt.timedelta(days=1)).strftime('%Y-%m-%d'),
             "limit_num":100,
             "offset_num":0
         },
         "query":"query loadSearchDefaultSortQuery($origin_radius: numeric!, $destination_radius: numeric!, $carrier_id: uuid!, $gl_carrier_user_id: String!, $equipment_ids: _int4!, $dh_origin_lat: numeric!, $dh_origin_lon: numeric!, $dh_destination_lat: numeric!, $dh_destination_lon: numeric!, $pickup_date_begin: timestamp!, $pickup_date_end: timestamp!, $limit_num: numeric!, $offset_num: numeric!) {\n  get_loads_with_extra_data_v8_sort_by_default(\n    args: {origin_radius: $origin_radius, destination_radius: $destination_radius, carrier_id: $carrier_id, gl_carrier_user_id: $gl_carrier_user_id, equipment_ids: $equipment_ids, dh_origin_lat: $dh_origin_lat, dh_origin_lon: $dh_origin_lon, dh_destination_lat: $dh_destination_lat, dh_destination_lon: $dh_destination_lon, pickup_date_begin: $pickup_date_begin, pickup_date_end: $pickup_date_end, limit_num: $limit_num, offset_num: $offset_num}\n  ) {\n    ...GridLoadSearchFields\n    __typename\n  }\n}\n\nfragment GridLoadSearchFields on loads_grid_v2 {\n  id\n  loadStateId\n  phone\n  legacyLoadId\n  modeId\n  modeCode\n  originState\n  originCity\n  originCityState\n  originEarlyTime\n  originLateTime\n  originDeadhead\n  destinationState\n  destinationCity\n  destinationCityState\n  destinationDeadhead\n  tripDistance\n  dimensionsLength\n  dimensionsWeight\n  equipmentCode\n  postedRate\n  createdOn\n  updatedOn\n  isBookItNow\n  loadTrackingRequired\n  canBookItNow\n  allInRate\n  rpm\n  accountName\n  experienceFactor\n  daysToPay\n  bondTypeId\n  payEnabled\n  daysToPayInteger\n  equipmentOptions\n  __typename\n}\n"
     }
    
    # Get the first list of loads
    res = session.post('https://loadsearch-graphql-api-prod.truckstop.com/v1/graphql?loadSearchCountQuery', headers=authHeaders, json=loadsPayload)
    q = json.loads(res.text)
    data = q[list(q)[0]][list(q[list(q)[0]])[0]]
    
    # Continue getting additional loads until they match the count
    while len(data) < count:
        print("Adding to data...")
        # add length of data to the query and request again
        loadsPayload['variables']['offset_num'] = len(data)
        q = json.loads(session.post('https://loadsearch-graphql-api-prod.truckstop.com/v1/graphql?loadSearchCountQuery', headers=authHeaders, json=loadsPayload).text)
        data = data + q[list(q)[0]][list(q[list(q)[0]])[0]]
        
    return data


def getNewCoordinates(df,coords,inputs):
    #print('Getting coordinates for all cities...')
    cities = list(set(list(df['originCityState']) + list(df['destinationCityState'])))
    from geopy.geocoders import Nominatim
    geolocator = Nominatim(user_agent='my_name')
    
    # if the coords for the startLoad city are not stored, get them
    if (inputs['startWithLoad']) and (inputs['startLoadCity'] not in coords.keys()):
        try:
            loc = geolocator.geocode(inputs['startLoadCity'])
            coords[inputs['startLoadCity']] = [loc.latitude,loc.longitude]
        except:
            print('***********************************************')
            print('Could not find coordinates for the startLoad city {}'.format(inputs['startLoadCity']))
            strCoords = input('Please input coords for this city as "lat, lon": \n')
            coords[inputs['startLoadCity']] = [float(strCoords.split(',')[0]),float(strCoords.split(',')[1])]
                
    for city in cities:
        if city not in coords.keys():
            try:
                loc = geolocator.geocode(city)
                coords[city] = [loc.latitude,loc.longitude]
            except:
                print('***********************************************')
                print('Could not find {}'.format(city))
                strCoords = input('Please input coords for this city as "lat, lon": \n')
                
                try:
                    coords[city] = [float(strCoords.split(',')[0]),float(strCoords.split(',')[1])]
                except:
                    # remove the rows with this city
                    df = df[df['originCityState'] != city]
                    df = df[df['destinationCityState'] != city]
    
    df.reset_index(drop=True,inplace=True)    
    
    #save the new coords variable
    import pickle
    with open('./coords.pickle','wb') as f:
        pickle.dump(coords,f,protocol=pickle.HIGHEST_PROTOCOL)

    return df,coords

def getNextPossibleLegs(df,coords,inputs,itinerary):
    # filter out any that can't be loaded and return home in timeLeft
    tempLoads = df.copy()
    currentTime = itinerary[-1]['endTime'] if len(itinerary)>0 else inputs['date_start']
    timeLeft = (inputs['date_end'] - currentTime).seconds/3600
    # print('Time Left: {}'.format(timeLeft))
    
    currentCoords = itinerary[-1]['destinationCoords'] if len(itinerary)>0 else inputs['startCoords']
    
    # IMPORTANT: delete any loads that are already in the itinerary
    ids = [row['id'] for row in itinerary]
    tempLoads = tempLoads[~tempLoads['id'].isin(ids)]
    
    #calculate new deadhead for each load
    tempLoads['originalOriginDeadhead'] = (tempLoads['originDeadhead']).copy()
    tempLoads['originDeadhead'] = [max((gd.geodesic(currentCoords,coords[loc]).miles)*1.15,20) for loc in tempLoads['originCityState']]
    
    # filter out any impossible to do loads
    tempLoads['minTime'] = [((tempLoads.iloc[ii]['originDeadhead']+tempLoads.iloc[ii]['destinationDeadhead']+tempLoads.iloc[ii]['tripDistance'])/inputs['avgSpeed']+inputs['loadTime']+inputs['unloadTime']) for ii in range(len(tempLoads))]
    tempLoads['nextDayTime'] = 0
    
    if inputs['canDeliverNextDay']:
        minTime = []
        nextDay = []
        for ii in range(len(tempLoads)):
            if tempLoads.iloc[ii]['minTime']>timeLeft:
                minTime.append((tempLoads.iloc[ii]['originDeadhead']+tempLoads.iloc[ii]['originalOriginDeadhead'])/inputs['avgSpeed']+inputs['loadTime'])
                nextDay.append(tempLoads.iloc[ii]['destinationDeadhead']/inputs['avgSpeed']+inputs['unloadTime'])

            else:
                minTime.append(tempLoads.iloc[ii]['minTime'])
                nextDay.append(0) 
            
        tempLoads['minTime'] = minTime
        tempLoads['nextDayTime'] = nextDay
        
    # filter out any loads that take too long
    tempLoads = tempLoads[tempLoads['minTime'] < timeLeft]
    tempLoads = tempLoads[tempLoads['nextDayTime'] < 5]
    
    tempLoads['loadTime'] = inputs['loadTime']
    tempLoads['unloadTime'] = inputs['unloadTime']
    
    tempLoads['nextDayDelivery'] = [True if check>0 else False for check in tempLoads['nextDayTime']]
    tempLoads['totalDistance'] = [tempLoads.iloc[ii]['originDeadhead']+tempLoads.iloc[ii]['tripDistance']+tempLoads.iloc[ii]['destinationDeadhead'] if tempLoads.iloc[ii]['nextDayDelivery'] == False else tempLoads.iloc[ii]['originDeadhead']+tempLoads.iloc[ii]['originalOriginDeadhead']+tempLoads.iloc[ii]['destinationDeadhead'] for ii in range(len(tempLoads))]
    #tempLoads['totalDistance'] = (tempLoads['minTime']-tempLoads['loadTime'])*inputs['avgSpeed'] + (tempLoads['nextDayTime']-tempLoads['unloadTime'])*inputs['avgSpeed']
    tempLoads['realRPM'] = tempLoads['postedRate']/tempLoads['totalDistance']
    
    tempLoads['startTime'] = currentTime
    tempLoads['endTime'] = [currentTime + dt.timedelta(hours=(tempLoads.iloc[ii]['totalDistance']/inputs['avgSpeed']+inputs['loadTime']+inputs['unloadTime'])) if tempLoads.iloc[ii]['nextDayTime']==0 else currentTime+dt.timedelta(hours=((tempLoads.iloc[ii]['originDeadhead']+tempLoads.iloc[ii]['originalOriginDeadhead'])/inputs['avgSpeed']+inputs['loadTime'])) for ii in range(len(tempLoads))]
    tempLoads['originCoords'] = [coords[loc] for loc in tempLoads['originCityState']]
    tempLoads['destinationCoords'] = [coords[loc] for loc in tempLoads['destinationCityState']]
    
    tempLoads['netRate'] = tempLoads['postedRate']-(tempLoads['totalDistance']*(inputs['diesel']/inputs['MPG_load']+inputs['maintCostPerMile']))
    tempLoads['netRatePerHour'] = tempLoads['netRate']/(tempLoads['minTime']+tempLoads['nextDayTime'])

    
    tempLoads = tempLoads.sort_values(by=['netRatePerHour'],ascending=False)
    tempLoads.reset_index(drop=True,inplace=True)
        
    possibleLoads = tempLoads.to_dict('records')
    return possibleLoads

def getNextPossibleLegs2(df,coords,inputs2,itinerary):
    # filter out any that can't be loaded and return home in timeLeft
    tempLoads = df.copy()
    currentTime = itinerary[-1]['endTime'] if len(itinerary)>0 else inputs2['date_start']
    timeLeft = (inputs2['date_end'] - currentTime).seconds/3600
    # print('Time Left: {}'.format(timeLeft))
    
    currentCoords = itinerary[-1]['destinationCoords'] if len(itinerary)>0 else inputs2['startCoords']
    
    # IMPORTANT: delete any loads that are already in the itinerary
    ids = [row['id'] for row in itinerary]
    tempLoads = tempLoads[~tempLoads['id'].isin(ids)]
    
    #calculate new deadhead for each load
    tempLoads['originalOriginDeadhead'] = (tempLoads['originDeadhead']).copy()
    tempLoads['originDeadhead'] = [max((gd.geodesic(currentCoords,coords[loc]).miles)*1.15,20) for loc in tempLoads['originCityState']]
    
    # filter out any impossible to do loads
    tempLoads['minTime'] = [((tempLoads.iloc[ii]['originDeadhead']+tempLoads.iloc[ii]['destinationDeadhead']+tempLoads.iloc[ii]['tripDistance'])/inputs2['avgSpeed']+inputs2['loadTime']+inputs2['unloadTime']) for ii in range(len(tempLoads))]
    tempLoads['nextDayTime'] = 0
    
    if inputs2['canDeliverNextDay']:
        minTime = []
        nextDay = []
        for ii in range(len(tempLoads)):
            if tempLoads.iloc[ii]['minTime']>timeLeft:
                minTime.append((tempLoads.iloc[ii]['originDeadhead']+tempLoads.iloc[ii]['originalOriginDeadhead'])/inputs2['avgSpeed']+inputs2['loadTime'])
                nextDay.append(tempLoads.iloc[ii]['destinationDeadhead']/inputs2['avgSpeed']+inputs2['unloadTime'])

            else:
                minTime.append(tempLoads.iloc[ii]['minTime'])
                nextDay.append(0) 
            
        tempLoads['minTime'] = minTime
        tempLoads['nextDayTime'] = nextDay
        
    # filter out any loads that take too long
    tempLoads = tempLoads[tempLoads['minTime'] < timeLeft]
    tempLoads = tempLoads[tempLoads['nextDayTime'] < 5]
    
    tempLoads['loadTime'] = inputs2['loadTime']
    tempLoads['unloadTime'] = inputs2['unloadTime']
    
    tempLoads['nextDayDelivery'] = [True if check>0 else False for check in tempLoads['nextDayTime']]
    tempLoads['totalDistance'] = [tempLoads.iloc[ii]['originDeadhead']+tempLoads.iloc[ii]['tripDistance']+tempLoads.iloc[ii]['destinationDeadhead'] if tempLoads.iloc[ii]['nextDayDelivery'] == False else tempLoads.iloc[ii]['originDeadhead']+tempLoads.iloc[ii]['originalOriginDeadhead']+tempLoads.iloc[ii]['destinationDeadhead'] for ii in range(len(tempLoads))]
    #tempLoads['totalDistance'] = (tempLoads['minTime']-tempLoads['loadTime'])*inputs['avgSpeed'] + (tempLoads['nextDayTime']-tempLoads['unloadTime'])*inputs['avgSpeed']
    tempLoads['realRPM'] = tempLoads['postedRate']/tempLoads['totalDistance']
    
    tempLoads['startTime'] = currentTime
    tempLoads['endTime'] = [currentTime + dt.timedelta(hours=(tempLoads.iloc[ii]['totalDistance']/inputs2['avgSpeed']+inputs2['loadTime']+inputs2['unloadTime'])) if tempLoads.iloc[ii]['nextDayTime']==0 else currentTime+dt.timedelta(hours=((tempLoads.iloc[ii]['originDeadhead']+tempLoads.iloc[ii]['originalOriginDeadhead'])/inputs2['avgSpeed']+inputs2['loadTime'])) for ii in range(len(tempLoads))]
    tempLoads['originCoords'] = [coords[loc] for loc in tempLoads['originCityState']]
    tempLoads['destinationCoords'] = [coords[loc] for loc in tempLoads['destinationCityState']]
    
    tempLoads['netRate'] = tempLoads['postedRate']-(tempLoads['totalDistance']*(inputs2['diesel']/inputs2['MPG_load']+inputs2['maintCostPerMile']))
    tempLoads['netRatePerHour'] = tempLoads['netRate']/(tempLoads['minTime']+tempLoads['nextDayTime'])

    
    tempLoads = tempLoads.sort_values(by=['netRatePerHour'],ascending=False)
    tempLoads.reset_index(drop=True,inplace=True)
        
    possibleLoads = tempLoads.to_dict('records')
    return possibleLoads

def loadToItinerary(dfRow):
    newItinerary = {
        'id': dfRow['id'],
        'phone': dfRow['phone'],
        'origin': dfRow['originCityState'],
        'destination': dfRow['destinationCityState'],
        'originCoords': dfRow['originCoords'],
        'destinationCoords': dfRow['destinationCoords'],
        'originDeadhead': dfRow['originDeadhead'],
        'originalOriginDeadhead': dfRow['originalOriginDeadhead'],
        'destinationDeadhead': dfRow['destinationDeadhead'],
        'tripDistance': dfRow['tripDistance'],
        'postedRate': dfRow['postedRate'],
        'rpm': dfRow['rpm'],
        'accountName': dfRow['accountName'],
        'daysToPay': dfRow['daysToPayInteger'],
        'realRPM': dfRow['realRPM'],
        'startTime': dfRow['startTime'],
        'endTime': dfRow['endTime'],
        'loadTime': dfRow['loadTime'],
        'unloadTime': dfRow['unloadTime'],
        'nextDayDelivery': dfRow['nextDayDelivery'],
        'netRate': dfRow['netRate'],
        'netRatePerHour': dfRow['netRatePerHour']
    }
    return newItinerary


def continueTripSearch(df,coords,inputs,itinerary,finalTrips,possibleLoads):
    # create a new trip for the fist 25 possible trips
    for row in possibleLoads:
        newItinerary = itinerary + [loadToItinerary(row)]
        finalTrips.append({
            'itinerary': newItinerary
        })
        
        if not row['nextDayDelivery']:
            moreLoads = getNextPossibleLegs(df,coords,inputs,newItinerary)
            if len(moreLoads)>0:
                finalTrips = continueTripSearch(df,coords,inputs,newItinerary,finalTrips,moreLoads)
    return finalTrips

def getTripStats(client,finalTrips,inputs):
    # loop through trip itineraries and get key values
    params = {'coordinates': [],
          'profile': 'driving-car',
          'instructions': 'true',
          'format_out': 'geojson',
          'units': 'mi',
          'radiuses':[5000]}
    
    results = []
    cc = 0
    for trip in finalTrips:
        cc += 1
        print('Processing {} out of {}'.format(cc,len(finalTrips)))
        path = []
        if not inputs['startWithLoad']: 
            path.append(inputs['startCoords'][::-1])
        for row in trip['itinerary']:
            path.append(row['originCoords'][::-1])
            if row['nextDayDelivery']:
                path.append(inputs['endCoords'][::-1])
                path.append(row['destinationCoords'][::-1])
            else:
                path.append(row['destinationCoords'][::-1])
                
        if not row['nextDayDelivery']:
            path.append(inputs['endCoords'][::-1])
                    
        params['coordinates'] = path
        time.sleep(1.5)
        route = client.directions(**params)['features'][0]['properties']
        
        tripDF = pd.DataFrame(trip['itinerary'])
        trip['totalRate'] = tripDF['postedRate'].sum()
        
        trip['totalTime'] = route['summary']['duration']/3600 + tripDF['loadTime'].sum()+tripDF['unloadTime'].sum()
        trip['calcTime'] = trip['totalTime'] - route['segments'][0]['duration']/3600 if inputs['startWithLoad'] else trip['totalTime']
        trip['nextDayDelivery'] = row['nextDayDelivery']
        trip['nextDayTime'] = (route['segments'][-1]['duration']/3600 + tripDF['unloadTime'].iloc[-1] if row['nextDayDelivery'] else 0)
        trip['thisDayTime'] = trip['totalTime'] - trip['calcTime']
        trip['startDayTime'] = inputs['date_start']
        trip['endDayTime'] = inputs['date_start'] + dt.timedelta(hours=trip['thisDayTime'])
        trip['timeSegments'] = route['segments']
        
        # update the start/end times with new ones
        seg = [item['duration']/3600 for item in route['segments']]
        # if not inputs['startWithLoad']: 

        segcount = 0
        if inputs['startWithLoad']:
            
            for ii in range(len(trip['itinerary'])):
                 
                path.append(row['originCoords'][::-1])
                if row['nextDayDelivery']:
                    path.append(inputs['endCoords'][::-1])
                    path.append(row['destinationCoords'][::-1])
                else:
                    path.append(row['destinationCoords'][::-1])
                
        if not row['nextDayDelivery']:
            path.append(inputs['endCoords'][::-1])
        
        trip['totalDistance'] = route['summary']['distance']
        trip['calcDistance'] = (trip['totalDistance'] - route['segments'][1]['distance']) if inputs['startWithLoad'] else (trip['totalDistance'])
        trip['maintenanceCost'] = trip['calcDistance']*inputs['maintCostPerMile']
        
        loadedMilesList = route['segments'][::2] if inputs['startWithLoad'] else route['segments'][1::2]
        if row['nextDayDelivery']: loadedMilesList.append(route['segments'][-1])
        loadedMiles = sum([item['distance'] for item in loadedMilesList])
        calcLoadedMiles = (loadedMiles - loadedMilesList[0]['distance']) if inputs['startWithLoad'] else (loadedMiles)
        
        
        trip['gasCost'] = (calcLoadedMiles/inputs['MPG_load'] + (trip['calcDistance']-calcLoadedMiles)/inputs['MPG_empty'])*inputs['diesel']
        trip['netRate'] = trip['totalRate'] - trip['maintenanceCost'] - trip['gasCost']
        trip['netRatePerHour'] = trip['netRate']/trip['calcTime']
        
        # trip['itinerary'] = tripDF
        
        results.append(trip)
        
    return results

def getTripStats2(client,extendedTripItinerary,inputs2):
    # loop through trip itineraries and get key values
    params = {'coordinates': [],
          'profile': 'driving-car',
          'instructions': 'true',
          'format_out': 'geojson',
          'units': 'mi',
          'radiuses':[5000]}
    
    results = []
    cc = 0
    for trip in extendedTripItinerary:
        cc += 1
        print('Processing {} out of {}'.format(cc,len(extendedTripItinerary)))
        path = []
        if not inputs2['startWithLoad']: 
            path.append(inputs2['startCoords'][::-1])
        for row in trip['itinerary']:
            path.append(row['originCoords'][::-1])
            if row['nextDayDelivery']:
                path.append(inputs2['endCoords'][::-1])
                path.append(row['destinationCoords'][::-1])
            else:
                path.append(row['destinationCoords'][::-1])
                
        if not row['nextDayDelivery']:
            path.append(inputs2['endCoords'][::-1])
                    
        params['coordinates'] = path
        time.sleep(1.5)
        route = client.directions(**params)['features'][0]['properties']
        
        tripDF = pd.DataFrame(trip['itinerary'])
        trip['totalRate'] = tripDF['postedRate'].sum()
        
        trip['totalTime'] = route['summary']['duration']/3600 + tripDF['loadTime'].sum()+tripDF['unloadTime'].sum()
        trip['calcTime'] = trip['totalTime'] - route['segments'][0]['duration']/3600 if inputs2['startWithLoad'] else trip['totalTime']
        trip['nextDayDelivery'] = row['nextDayDelivery']
        trip['nextDayTime'] = (route['segments'][-1]['duration']/3600 + tripDF['unloadTime'].iloc[-1] if row['nextDayDelivery'] else 0)
        trip['thisDayTime'] = trip['totalTime'] - trip['calcTime']
        trip['startDayTime'] = inputs2['date_start']
        trip['endDayTime'] = inputs2['date_start'] + dt.timedelta(hours=trip['thisDayTime'])
        trip['timeSegments'] = route['segments']
        
        # update the start/end times with new ones
        seg = [item['duration']/3600 for item in route['segments']]
        # if not inputs['startWithLoad']: 

        segcount = 0
        if inputs2['startWithLoad']:
            
            for ii in range(len(trip['itinerary'])):
                 
                path.append(row['originCoords'][::-1])
                if row['nextDayDelivery']:
                    path.append(inputs2['endCoords'][::-1])
                    path.append(row['destinationCoords'][::-1])
                else:
                    path.append(row['destinationCoords'][::-1])
                
        if not row['nextDayDelivery']:
            path.append(inputs2['endCoords'][::-1])
        
        trip['totalDistance'] = route['summary']['distance']
        trip['calcDistance'] = (trip['totalDistance'] - route['segments'][1]['distance']) if inputs2['startWithLoad'] else (trip['totalDistance'])
        trip['maintenanceCost'] = trip['calcDistance']*inputs2['maintCostPerMile']
        
        loadedMilesList = route['segments'][::2] if inputs2['startWithLoad'] else route['segments'][1::2]
        if row['nextDayDelivery']: loadedMilesList.append(route['segments'][-1])
        loadedMiles = sum([item['distance'] for item in loadedMilesList])
        calcLoadedMiles = (loadedMiles - loadedMilesList[0]['distance']) if inputs2['startWithLoad'] else (loadedMiles)
        
        
        trip['gasCost'] = (calcLoadedMiles/inputs2['MPG_load'] + (trip['calcDistance']-calcLoadedMiles)/inputs2['MPG_empty'])*inputs2['diesel']
    
        trip['netRate'] = trip['totalRate'] - trip['maintenanceCost'] - trip['gasCost']
        trip['netRatePerHour'] = trip['netRate']/trip['calcTime']
        
        # trip['itinerary'] = tripDF
        
        results.append(trip)
        
    return results

def getTripStatsFast(finalTrips,inputs):
    # loop through trip itineraries and get key values
    params = {'coordinates': [],
          'profile': 'driving-car',
          'instructions': 'true',
          'format_out': 'geojson',
          'units': 'mi',
          'radiuses':[5000]}
    
    results = []
    cc = 0
    for trip in finalTrips:
        cc += 1
        print('Processing {} out of {}'.format(cc,len(finalTrips)))
        path = []
        if not inputs['startWithLoad']: 
            path.append(inputs['startCoords'][::-1])
        for row in trip['itinerary']:
            path.append(row['originCoords'][::-1])
            if row['nextDayDelivery']:
                path.append(inputs['endCoords'][::-1])
                path.append(row['destinationCoords'][::-1])
            else:
                path.append(row['destinationCoords'][::-1])
                
        if not row['nextDayDelivery']:
            path.append(inputs['endCoords'][::-1])
                    
        params['coordinates'] = path
        #time.sleep(1.5)
        #route = client.directions(**params)['features'][0]['properties']
        
        defineRoute = len(path)
        # Create your dictionary class
        class my_dictionary(dict):
         
          # __init__ function
          def __init__(self):
            self = dict()
         
          # Function to add key:value
          def add(self, key, value):
            self[key] = value
        
        if inputs['startWithLoad']:
            # Main Function
            segment1 = my_dictionary()
             
            segment1.add('distance', trip['itinerary'][0]['tripDistance'])
            segment1.add('duration', segment1['distance']/inputs['avgSpeed']*3600) 
            
            segment2 = my_dictionary()
             
            segment2.add('distance', trip['itinerary'][1]['originDeadhead'])
            segment2.add('duration', segment2['distance']/inputs['avgSpeed']*3600)
            
            segment3 = my_dictionary()
             
            segment3.add('distance', trip['itinerary'][1]['originalOriginDeadhead']*1.15)
            segment3.add('duration', segment3['distance']/inputs['avgSpeed']*3600)
            
            segment4 = my_dictionary()
             
            segment4.add('distance', trip['itinerary'][1]['destinationDeadhead']*1.15)
            segment4.add('duration', segment4['distance']/inputs['avgSpeed']*3600)
            
            calcSegments = []
            calcSegments.append(segment1)
            calcSegments.append(segment2)
            calcSegments.append(segment3)
            calcSegments.append(segment4)
            
            calcSummary = my_dictionary()
             
            calcSummary.add('distance', segment2['distance']+segment3['distance']+segment4['distance'])
            calcSummary.add('duration', segment1['duration'] + segment2['duration']+segment3['duration']+segment4['duration'])
                            
            # calcSummary.add('distance', trip['itinerary'][0]['tripDistance'] + trip['itinerary'][1]['originDeadhead'] + trip['itinerary'][1]['originalOriginDeadhead'] + trip['itinerary'][1]['destinationDeadhead'])
            # calcSummary.add('duration', (trip['itinerary'][0]['tripDistance'] + trip['itinerary'][1]['originDeadhead'] + trip['itinerary'][1]['originalOriginDeadhead'] + trip['itinerary'][1]['destinationDeadhead'])/inputs['avgSpeed']*3600)
    
            # Main Function
            route = my_dictionary()
             
            route.add('segments', calcSegments)
            route.add('summary', calcSummary)
        else:
            if defineRoute < 5:
                if trip['itinerary'][0]['nextDayDelivery']==True:
                    # Main Function
                    segment1 = my_dictionary()
                     
                    segment1.add('distance', trip['itinerary'][0]['originDeadhead'])
                    segment1.add('duration', segment1['distance']/inputs['avgSpeed']*3600) 
                    
                    segment2 = my_dictionary()
                     
                    segment2.add('distance', trip['itinerary'][0]['originDeadhead'])
                    segment2.add('duration', segment2['distance']/inputs['avgSpeed']*3600) 
                    
                    segment3 = my_dictionary()
                     
                    segment3.add('distance', trip['itinerary'][0]['destinationDeadhead']*1.15)
                    segment3.add('duration', segment3['distance']/inputs['avgSpeed']*3600)
                    
                    
                    calcSegments = []
                    calcSegments.append(segment1)
                    calcSegments.append(segment2)
                    calcSegments.append(segment3)
                    
                    calcSummary = my_dictionary()
                    
                    calcSummary.add('distance', segment1['distance'] + segment2['distance']+segment3['distance'])
                    calcSummary.add('duration', segment1['duration'] + segment2['duration']+segment3['duration'])
                    
                    # calcSummary.add('distance', trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['destinationDeadhead'])
                    # calcSummary.add('duration', (trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['destinationDeadhead'])/inputs['avgSpeed']*3600)
            
                    # Main Function
                    route = my_dictionary()
                     
                    route.add('segments', calcSegments)
                    route.add('summary', calcSummary)
                else:
                    # Main Function
                    segment1 = my_dictionary()
                     
                    segment1.add('distance', trip['itinerary'][0]['originDeadhead'])
                    segment1.add('duration', segment1['distance']/inputs['avgSpeed']*3600)
                    
                    segment2 = my_dictionary()
                     
                    segment2.add('distance', trip['itinerary'][0]['tripDistance']*1.15)
                    segment2.add('duration', segment2['distance']/inputs['avgSpeed']*3600) 
                    
                    segment3 = my_dictionary()
                     
                    segment3.add('distance', trip['itinerary'][0]['destinationDeadhead']*1.15)
                    segment3.add('duration', segment3['distance']/inputs['avgSpeed']*3600)
                    
                    calcSegments = []
                    calcSegments.append(segment1)
                    calcSegments.append(segment2)
                    calcSegments.append(segment3)

                    
                    calcSummary = my_dictionary()
                    
                    calcSummary.add('distance', segment1['distance'] + segment2['distance']+segment3['distance'])
                    calcSummary.add('duration', segment1['duration'] + segment2['duration']+segment3['duration'])
                    
                    # calcSummary.add('distance', trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['destinationDeadhead'])
                    # calcSummary.add('duration', (trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['destinationDeadhead'])/inputs['avgSpeed']*3600)
            
                    # Main Function
                    route = my_dictionary()
                     
                    route.add('segments', calcSegments)
                    route.add('summary', calcSummary)
                
            elif defineRoute < 7:
                # Main Function
                if trip['itinerary'][1]['nextDayDelivery']==True:

                    segment1 = my_dictionary()
                     
                    segment1.add('distance', trip['itinerary'][0]['originalOriginDeadhead']*1.15)
                    segment1.add('duration', segment1['distance']/inputs['avgSpeed']*3600)
                    
                    segment2 = my_dictionary()
                     
                    segment2.add('distance', trip['itinerary'][0]['tripDistance']*1.15)
                    segment2.add('duration', segment2['distance']/inputs['avgSpeed']*3600) 
                    
                    segment3 = my_dictionary()
                     
                    segment3.add('distance', trip['itinerary'][1]['originDeadhead'])
                    segment3.add('duration', segment3['distance']/inputs['avgSpeed']*3600)
                    
                    segment4 = my_dictionary()
                     
                    segment4.add('distance', trip['itinerary'][1]['originalOriginDeadhead']*1.15)
                    segment4.add('duration', segment4['distance']/inputs['avgSpeed']*3600)
                    
                    segment5 = my_dictionary()
                     
                    segment5.add('distance', trip['itinerary'][1]['destinationDeadhead']*1.15)
                    segment5.add('duration', segment5['distance']/inputs['avgSpeed']*3600)
                    

                    
                    calcSegments = []
                    calcSegments.append(segment1)
                    calcSegments.append(segment2)
                    calcSegments.append(segment3)
                    calcSegments.append(segment4)
                    calcSegments.append(segment5)
    
                    
                    calcSummary = my_dictionary()
                    
                    calcSummary.add('distance', segment1['distance'] + segment2['distance']+segment3['distance']+segment4['distance']+segment5['distance'])
                    calcSummary.add('duration', segment1['duration'] + segment2['duration']+segment3['duration']+segment4['duration']+segment5['duration'])
                    
                    # calcSummary.add('distance', trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['tripDistance'] + trip['itinerary'][1]['originDeadhead'] + trip['itinerary'][1]['destinationDeadhead'] + trip['itinerary'][1]['originalOriginDeadhead'])
                    # calcSummary.add('duration', (trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['tripDistance'] + trip['itinerary'][1]['originDeadhead'] + trip['itinerary'][1]['destinationDeadhead'] + trip['itinerary'][1]['originalOriginDeadhead'])/inputs['avgSpeed']*3600)
            
                    # Main Function
                    route = my_dictionary()
                     
                    route.add('segments', calcSegments)
                    route.add('summary', calcSummary)
                else:
                    segment1 = my_dictionary()
                     
                    segment1.add('distance', trip['itinerary'][0]['originalOriginDeadhead']*1.15)
                    segment1.add('duration', segment1['distance']/inputs['avgSpeed']*3600)
                    
                    segment2 = my_dictionary()
                     
                    segment2.add('distance', trip['itinerary'][0]['tripDistance']*1.15)
                    segment2.add('duration', segment2['distance']/inputs['avgSpeed']*3600) 
                    
                    segment3 = my_dictionary()
                     
                    segment3.add('distance', trip['itinerary'][1]['originDeadhead'])
                    segment3.add('duration', segment3['distance']/inputs['avgSpeed']*3600)
                    
                    segment4 = my_dictionary()
                     
                    segment4.add('distance', trip['itinerary'][1]['tripDistance']*1.15)
                    segment4.add('duration', segment4['distance']/inputs['avgSpeed']*3600) 
                    
                    segment5 = my_dictionary()
                     
                    segment5.add('distance', trip['itinerary'][1]['destinationDeadhead']*1.15)
                    segment5.add('duration', segment5['distance']/inputs['avgSpeed']*3600)
                    
                

                
                    calcSegments = []
                    calcSegments.append(segment1)
                    calcSegments.append(segment2)
                    calcSegments.append(segment3)
                    calcSegments.append(segment4)
                    calcSegments.append(segment5)
    
                    
                    calcSummary = my_dictionary()
                    
                    calcSummary.add('distance', segment1['distance'] + segment2['distance']+segment3['distance']+segment4['distance']+segment5['distance'])
                    calcSummary.add('duration', segment1['duration'] + segment2['duration']+segment3['duration']+segment4['duration']+segment5['duration'])
                    
                    # calcSummary.add('distance', trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['tripDistance'] + trip['itinerary'][1]['originDeadhead'] + trip['itinerary'][1]['destinationDeadhead'] + trip['itinerary'][1]['originalOriginDeadhead'])
                    # calcSummary.add('duration', (trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['tripDistance'] + trip['itinerary'][1]['originDeadhead'] + trip['itinerary'][1]['destinationDeadhead'] + trip['itinerary'][1]['originalOriginDeadhead'])/inputs['avgSpeed']*3600)
            
                    # Main Function
                    route = my_dictionary()
                     
                    route.add('segments', calcSegments)
                    route.add('summary', calcSummary)


        
        tripDF = pd.DataFrame(trip['itinerary'])
        trip['totalRate'] = tripDF['postedRate'].sum()
        
        trip['totalTime'] = route['summary']['duration']/3600 + tripDF['loadTime'].sum()+tripDF['unloadTime'].sum()
        trip['calcTime'] = trip['totalTime'] - route['segments'][0]['duration']/3600 if inputs['startWithLoad'] else trip['totalTime']
        trip['nextDayDelivery'] = row['nextDayDelivery']
        trip['nextDayTime'] = (route['segments'][-1]['duration']/3600 + tripDF['unloadTime'].iloc[-1] if row['nextDayDelivery'] else 0)
        trip['thisDayTime'] = trip['totalTime'] - trip['calcTime']
        trip['startDayTime'] = inputs['date_start']
        trip['endDayTime'] = inputs['date_start'] + dt.timedelta(hours=trip['thisDayTime'])
        trip['timeSegments'] = route['segments']
        
        # update the start/end times with new ones
        seg = [item['duration']/3600 for item in route['segments']]
        # if not inputs['startWithLoad']: 

        segcount = 0
        if inputs['startWithLoad']:
            
            for ii in range(len(trip['itinerary'])):
                 
                path.append(row['originCoords'][::-1])
                if row['nextDayDelivery']:
                    path.append(inputs['endCoords'][::-1])
                    path.append(row['destinationCoords'][::-1])
                else:
                    path.append(row['destinationCoords'][::-1])
                
        if not row['nextDayDelivery']:
            path.append(inputs['endCoords'][::-1])
        
        trip['totalDistance'] = route['summary']['distance']
        trip['calcDistance'] = trip['totalDistance'] #(trip['totalDistance'] - route['segments'][1]['distance']) if inputs['startWithLoad'] else (trip['totalDistance'])
        trip['maintenanceCost'] = trip['calcDistance']*inputs['maintCostPerMile']
        
        loadedMilesList = route['segments'][::2] if inputs['startWithLoad'] else route['segments'][1::2]
        if row['nextDayDelivery']: loadedMilesList.append(route['segments'][-1])
        loadedMiles = sum([item['distance'] for item in loadedMilesList])
        calcLoadedMiles = (loadedMiles - loadedMilesList[0]['distance']) if inputs['startWithLoad'] else (loadedMiles)
        
        
        trip['gasCost'] = (calcLoadedMiles/inputs['MPG_load'] + (trip['calcDistance']-calcLoadedMiles)/inputs['MPG_empty'])*inputs['diesel']
        trip['netRate'] = trip['totalRate'] - trip['maintenanceCost'] - trip['gasCost']
        trip['netRatePerHour'] = trip['netRate']/trip['calcTime']
        
        # trip['itinerary'] = tripDF
        
        results.append(trip)
        
    return results

def getTripStatsFast2(extendedTripItinerary,inputs2):
    # loop through trip itineraries and get key values
    params = {'coordinates': [],
          'profile': 'driving-car',
          'instructions': 'true',
          'format_out': 'geojson',
          'units': 'mi',
          'radiuses':[5000]}
    
    results = []
    cc = 0
    for trip in extendedTripItinerary:
        cc += 1
        print('Processing {} out of {}'.format(cc,len(extendedTripItinerary)))
        path = []
        if not inputs2['startWithLoad']: 
            path.append(inputs2['startCoords'][::-1])
        for row in trip['itinerary']:
            path.append(row['originCoords'][::-1])
            if row['nextDayDelivery']:
                path.append(inputs2['endCoords'][::-1])
                path.append(row['destinationCoords'][::-1])
            else:
                path.append(row['destinationCoords'][::-1])
                
        if not row['nextDayDelivery']:
            path.append(inputs2['endCoords'][::-1])
                    
        params['coordinates'] = path
        #time.sleep(1.5)
        #route = client.directions(**params)['features'][0]['properties']
        
        defineRoute = len(path)
        # Create your dictionary class
        class my_dictionary(dict):
         
          # __init__ function
          def __init__(self):
            self = dict()
         
          # Function to add key:value
          def add(self, key, value):
            self[key] = value
        
        if inputs2['startWithLoad']:
            # Main Function
            segment1 = my_dictionary()
             
            segment1.add('distance', trip['itinerary'][0]['tripDistance'])
            segment1.add('duration', segment1['distance']/inputs2['avgSpeed']*3600) 
            
            segment2 = my_dictionary()
             
            segment2.add('distance', trip['itinerary'][1]['originDeadhead'])
            segment2.add('duration', segment2['distance']/inputs2['avgSpeed']*3600)
            
            segment3 = my_dictionary()
             
            segment3.add('distance', trip['itinerary'][1]['originalOriginDeadhead']*1.15)
            segment3.add('duration', segment3['distance']/inputs2['avgSpeed']*3600)
            
            segment4 = my_dictionary()
             
            segment4.add('distance', trip['itinerary'][1]['destinationDeadhead']*1.15)
            segment4.add('duration', segment4['distance']/inputs2['avgSpeed']*3600)
            
            calcSegments = []
            calcSegments.append(segment1)
            calcSegments.append(segment2)
            calcSegments.append(segment3)
            calcSegments.append(segment4)
            
            calcSummary = my_dictionary()
             
            calcSummary.add('distance', segment2['distance']+segment3['distance']+segment4['distance'])
            calcSummary.add('duration', segment1['duration'] + segment2['duration']+segment3['duration']+segment4['duration'])
                            
            # calcSummary.add('distance', trip['itinerary'][0]['tripDistance'] + trip['itinerary'][1]['originDeadhead'] + trip['itinerary'][1]['originalOriginDeadhead'] + trip['itinerary'][1]['destinationDeadhead'])
            # calcSummary.add('duration', (trip['itinerary'][0]['tripDistance'] + trip['itinerary'][1]['originDeadhead'] + trip['itinerary'][1]['originalOriginDeadhead'] + trip['itinerary'][1]['destinationDeadhead'])/inputs['avgSpeed']*3600)
    
            # Main Function
            route = my_dictionary()
             
            route.add('segments', calcSegments)
            route.add('summary', calcSummary)
        else:
            if defineRoute < 5:
                if path[0] == path[2]:
                    # Main Function
                    segment1 = my_dictionary()
                     
                    segment1.add('distance', trip['itinerary'][0]['originDeadhead'])
                    segment1.add('duration', segment1['distance']/inputs2['avgSpeed']*3600) 
                    
                    segment2 = my_dictionary()
                     
                    segment2.add('distance', trip['itinerary'][0]['originDeadhead'])
                    segment2.add('duration', segment2['distance']/inputs2['avgSpeed']*3600) 
                    
                    segment3 = my_dictionary()
                     
                    segment3.add('distance', trip['itinerary'][0]['destinationDeadhead']*1.15)
                    segment3.add('duration', segment3['distance']/inputs2['avgSpeed']*3600)
                    
                    
                    calcSegments = []
                    calcSegments.append(segment1)
                    calcSegments.append(segment2)
                    calcSegments.append(segment3)
                    
                    calcSummary = my_dictionary()
                    
                    calcSummary.add('distance', segment1['distance'] + segment2['distance']+segment3['distance'])
                    calcSummary.add('duration', segment1['duration'] + segment2['duration']+segment3['duration'])
                    
                    # calcSummary.add('distance', trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['destinationDeadhead'])
                    # calcSummary.add('duration', (trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['destinationDeadhead'])/inputs['avgSpeed']*3600)
            
                    # Main Function
                    route = my_dictionary()
                     
                    route.add('segments', calcSegments)
                    route.add('summary', calcSummary)
                else:
                    # Main Function
                    segment1 = my_dictionary()
                     
                    segment1.add('distance', trip['itinerary'][0]['originDeadhead'])
                    segment1.add('duration', segment1['distance']/inputs2['avgSpeed']*3600)
                    
                    segment2 = my_dictionary()
                     
                    segment2.add('distance', trip['itinerary'][0]['tripDistance']*1.15)
                    segment2.add('duration', segment2['distance']/inputs2['avgSpeed']*3600) 
                    
                    segment3 = my_dictionary()
                     
                    segment3.add('distance', trip['itinerary'][0]['destinationDeadhead']*1.15)
                    segment3.add('duration', segment3['distance']/inputs2['avgSpeed']*3600)
                    
                    calcSegments = []
                    calcSegments.append(segment1)
                    calcSegments.append(segment2)
                    calcSegments.append(segment3)

                    
                    calcSummary = my_dictionary()
                    
                    calcSummary.add('distance', segment1['distance'] + segment2['distance']+segment3['distance'])
                    calcSummary.add('duration', segment1['duration'] + segment2['duration']+segment3['duration'])
                    
                    # calcSummary.add('distance', trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['destinationDeadhead'])
                    # calcSummary.add('duration', (trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['destinationDeadhead'])/inputs['avgSpeed']*3600)
            
                    # Main Function
                    route = my_dictionary()
                     
                    route.add('segments', calcSegments)
                    route.add('summary', calcSummary)
                
            elif defineRoute < 7:
                # Main Function
                if path[0] == path[4]:

                    segment1 = my_dictionary()
                     
                    segment1.add('distance', trip['itinerary'][0]['originalOriginDeadhead']*1.15)
                    segment1.add('duration', segment1['distance']/inputs2['avgSpeed']*3600)
                    
                    segment2 = my_dictionary()
                     
                    segment2.add('distance', trip['itinerary'][0]['tripDistance']*1.15)
                    segment2.add('duration', segment2['distance']/inputs2['avgSpeed']*3600) 
                    
                    segment3 = my_dictionary()
                     
                    segment3.add('distance', trip['itinerary'][1]['originDeadhead'])
                    segment3.add('duration', segment3['distance']/inputs2['avgSpeed']*3600)
                    
                    segment4 = my_dictionary()
                     
                    segment4.add('distance', trip['itinerary'][1]['destinationDeadhead']*1.15)
                    segment4.add('duration', segment4['distance']/inputs2['avgSpeed']*3600)
                    
                    segment5 = my_dictionary()
                     
                    segment5.add('distance', trip['itinerary'][1]['originalOriginDeadhead']*1.15)
                    segment5.add('duration', segment5['distance']/inputs2['avgSpeed']*3600)
                    
                    calcSegments = []
                    calcSegments.append(segment1)
                    calcSegments.append(segment2)
                    calcSegments.append(segment3)
                    calcSegments.append(segment4)
                    calcSegments.append(segment5)
    
                    
                    calcSummary = my_dictionary()
                    
                    calcSummary.add('distance', segment1['distance'] + segment2['distance']+segment3['distance']+segment4['distance']+segment5['distance'])
                    calcSummary.add('duration', segment1['duration'] + segment2['duration']+segment3['duration']+segment4['duration']+segment5['duration'])
                    
                    # calcSummary.add('distance', trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['tripDistance'] + trip['itinerary'][1]['originDeadhead'] + trip['itinerary'][1]['destinationDeadhead'] + trip['itinerary'][1]['originalOriginDeadhead'])
                    # calcSummary.add('duration', (trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['tripDistance'] + trip['itinerary'][1]['originDeadhead'] + trip['itinerary'][1]['destinationDeadhead'] + trip['itinerary'][1]['originalOriginDeadhead'])/inputs['avgSpeed']*3600)
            
                    # Main Function
                    route = my_dictionary()
                     
                    route.add('segments', calcSegments)
                    route.add('summary', calcSummary)
                else:
                    segment1 = my_dictionary()
                     
                    segment1.add('distance', trip['itinerary'][0]['originalOriginDeadhead']*1.15)
                    segment1.add('duration', segment1['distance']/inputs2['avgSpeed']*3600)
                    
                    segment2 = my_dictionary()
                     
                    segment2.add('distance', trip['itinerary'][0]['tripDistance']*1.15)
                    segment2.add('duration', segment2['distance']/inputs2['avgSpeed']*3600) 
                    
                    segment3 = my_dictionary()
                     
                    segment3.add('distance', trip['itinerary'][1]['originDeadhead'])
                    segment3.add('duration', segment3['distance']/inputs2['avgSpeed']*3600)
                    
                    segment4 = my_dictionary()
                     
                    segment4.add('distance', trip['itinerary'][1]['tripDistance']*1.15)
                    segment4.add('duration', segment4['distance']/inputs2['avgSpeed']*3600) 
                    
                    segment5 = my_dictionary()
                     
                    segment5.add('distance', trip['itinerary'][1]['destinationDeadhead']*1.15)
                    segment5.add('duration', segment5['distance']/inputs2['avgSpeed']*3600)
                    
                

                
                    calcSegments = []
                    calcSegments.append(segment1)
                    calcSegments.append(segment2)
                    calcSegments.append(segment3)
                    calcSegments.append(segment4)
                    calcSegments.append(segment5)
    
                    
                    calcSummary = my_dictionary()
                    
                    calcSummary.add('distance', segment1['distance'] + segment2['distance']+segment3['distance']+segment4['distance']+segment5['distance'])
                    calcSummary.add('duration', segment1['duration'] + segment2['duration']+segment3['duration']+segment4['duration']+segment5['duration'])
                    
                    # calcSummary.add('distance', trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['tripDistance'] + trip['itinerary'][1]['originDeadhead'] + trip['itinerary'][1]['destinationDeadhead'] + trip['itinerary'][1]['originalOriginDeadhead'])
                    # calcSummary.add('duration', (trip['itinerary'][0]['originalOriginDeadhead'] + trip['itinerary'][0]['tripDistance'] + trip['itinerary'][1]['originDeadhead'] + trip['itinerary'][1]['destinationDeadhead'] + trip['itinerary'][1]['originalOriginDeadhead'])/inputs['avgSpeed']*3600)
            
                    # Main Function
                    route = my_dictionary()
                     
                    route.add('segments', calcSegments)
                    route.add('summary', calcSummary)


        

        
        tripDF = pd.DataFrame(trip['itinerary'])
        trip['totalRate'] = tripDF['postedRate'].sum()
        
        trip['totalTime'] = route['summary']['duration']/3600 + tripDF['loadTime'].sum()+tripDF['unloadTime'].sum()
        trip['calcTime'] = trip['totalTime'] - route['segments'][0]['duration']/3600 if inputs2['startWithLoad'] else trip['totalTime']
        trip['nextDayDelivery'] = row['nextDayDelivery']
        trip['nextDayTime'] = (route['segments'][-1]['duration']/3600 + tripDF['unloadTime'].iloc[-1] if row['nextDayDelivery'] else 0)
        trip['thisDayTime'] = trip['totalTime'] - trip['calcTime']
        trip['startDayTime'] = inputs2['date_start']
        trip['endDayTime'] = inputs2['date_start'] + dt.timedelta(hours=trip['thisDayTime'])
        trip['timeSegments'] = route['segments']
        
        # update the start/end times with new ones
        seg = [item['duration']/3600 for item in route['segments']]
        # if not inputs['startWithLoad']: 

        segcount = 0
        if inputs2['startWithLoad']:
            
            for ii in range(len(trip['itinerary'])):
                 
                path.append(row['originCoords'][::-1])
                if row['nextDayDelivery']:
                    path.append(inputs2['endCoords'][::-1])
                    path.append(row['destinationCoords'][::-1])
                else:
                    path.append(row['destinationCoords'][::-1])
                
        if not row['nextDayDelivery']:
            path.append(inputs2['endCoords'][::-1])
        
        trip['totalDistance'] = route['summary']['distance']
        trip['calcDistance'] = trip['totalDistance'] #(trip['totalDistance'] - route['segments'][1]['distance']) if inputs['startWithLoad'] else (trip['totalDistance'])
        trip['maintenanceCost'] = trip['calcDistance']*inputs2['maintCostPerMile']
        
        loadedMilesList = route['segments'][::2] if inputs2['startWithLoad'] else route['segments'][1::2]
        if row['nextDayDelivery']: loadedMilesList.append(route['segments'][-1])
        loadedMiles = sum([item['distance'] for item in loadedMilesList])
        calcLoadedMiles = (loadedMiles - loadedMilesList[0]['distance']) if inputs2['startWithLoad'] else (loadedMiles)
        
        
        trip['gasCost'] = (calcLoadedMiles/inputs2['MPG_load'] + (trip['calcDistance']-calcLoadedMiles)/inputs2['MPG_empty'])*inputs2['diesel']
        trip['netRate'] = trip['totalRate'] - trip['maintenanceCost'] - trip['gasCost']
        trip['netRatePerHour'] = trip['netRate']/trip['calcTime']
        
        # trip['itinerary'] = tripDF
        
        results.append(trip)
        
    return results

def dateToTime(date):
    return date.strftime("%I:%M %p")

def getTripItinerary(resultsDF,inputs,num=1):
    ii = num - 1
    view = resultsDF.iloc[ii]['itinerary']
    seg = [item['duration']/3600 for item in resultsDF.iloc[ii]['timeSegments']]
    viewDF = pd.DataFrame(resultsDF.iloc[ii]['itinerary'])
            
    # get times for each location
    times = []
    segcount = 0
    for ii in range(len(view)):
        if len(view) == 1:
            # start day at home
            times.append([view[ii]['startTime'],inputs['startDayCity'],'Drive Load to Destination'])
            # arrive at origin to pickup
            times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['origin'],'Arrive at Origin & Load'])
            # increment the segcount
            segcount += 1
            # finish loading and depart for trip
            times.append([times[-1][0]+dt.timedelta(hours=view[ii]['loadTime']),view[ii]['origin'],'Drive Load to Destination'])
            
            if view[ii]['nextDayDelivery']:
                # arrive at home for the evening
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),inputs['endDayCity'],'Done for Day, with Load'])
                # increment the segcount
                segcount += 1
                # next day load delivery
                times.append([inputs['next_date_start']+dt.timedelta(days=1,hours=seg[segcount])+dt.timedelta(hours=view[ii]['unloadTime']),view[ii]['destination'],'Next Day Delivery and Unload'])
                # increment the segcount
                segcount += 1
            else:
                # arrive at destination to unload
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['destination'],'Arrive at Destination & Unload'])
                # increment the segcount
                segcount += 1
                # finish unloading, leave for home
                times.append([times[-1][0]+dt.timedelta(hours=view[ii]['unloadTime']),view[ii]['destination'],'Head Home'])
                # arrive at home for the evening
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),inputs['endDayCity'],'Done for Day, Empty'])
                # increment the segcount
                segcount += 1
            
        elif ii == 0:
            if inputs['startWithLoad']:
                # start day at home
                times.append([view[ii]['startTime'],inputs['startDayCity'],'Drive Load to Destination'])
                # arrive at destination to unload
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['destination'],'Arrive at Destination & Unload'])
                # increment the segcount
                segcount += 1
                # finish unloading, leave for new load deadhead
                times.append([times[-1][0]+dt.timedelta(hours=view[ii]['unloadTime']),view[ii]['destination'],'Deadhead to Next Load'])
            else:
                # start day at home
                times.append([view[ii]['startTime'],inputs['startDayCity'],'Deadhead to First Load'])
                # arrive at origin to pickup
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['origin'],'Arrive at Origin & Load'])
                # increment the segcount
                segcount += 1
                # finish loading and depart for trip
                times.append([times[-1][0]+dt.timedelta(hours=view[ii]['loadTime']),view[ii]['origin'],'Drive Load to Destination'])
                # arrive at destination to unload
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['destination'],'Arrive at Destination & Unload'])
                # increment the segcount
                segcount += 1
                # finish unloading, leave for new load deadhead
                times.append([times[-1][0]+dt.timedelta(hours=view[ii]['unloadTime']),view[ii]['destination'],'Deadhead to Next Load'])
                
        elif ii == len(view)-1:
            # arrive at origin to pickup
            times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['origin'],'Arrive at Origin & Load'])
            # increment the segcount
            segcount += 1
            # finish loading and depart for trip
            times.append([times[-1][0]+dt.timedelta(hours=view[ii]['loadTime']),view[ii]['origin'],'Drive Load to Destination'])
            
            if view[ii]['nextDayDelivery']:
                # arrive at home for the evening
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),inputs['endDayCity'],'Done for Day, with Load'])
                # increment the segcount
                segcount += 1
                # next day load delivery
                times.append([inputs['next_date_start']+dt.timedelta(days=1,hours=seg[segcount])+dt.timedelta(hours=view[ii]['unloadTime']),view[ii]['destination'],'Next Day Delivery and Unload'])
                # increment the segcount
                segcount += 1
            else:
                # arrive at destination to unload
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['destination'],'Arrive at Destination & Unload'])
                # increment the segcount
                segcount += 1
                # finish unloading, leave for home
                times.append([times[-1][0]+dt.timedelta(hours=view[ii]['unloadTime']),view[ii]['destination'],'Head Home'])
                # arrive at home for the evening
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),inputs['endDayCity'],'Done for Day, Empty'])
                # increment the segcount
                segcount += 1
            
        else:
            # arrive at origin to pickup
            times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['origin'],'Arrive at Origin & Load'])
            # increment the segcount
            segcount += 1
            # finish loading and depart for trip
            times.append([times[-1][0]+dt.timedelta(hours=view[ii]['loadTime']),view[ii]['origin'],'Drive Load to Destination'])
            # arrive at destination to unload
            times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['destination'],'Arrive at Destination & Unload'])
            # increment the segcount
            segcount += 1
            # finish unloading, leave for new load deadhead
            times.append([times[-1][0]+dt.timedelta(hours=view[ii]['unloadTime']),view[ii]['destination'],'Deadhead to Next Load'])
        
    #print the itinerary
    print('\n*******************************************************************')
    print('Viewing itinerary for Trip #{} out of {}'.format(num,len(resultsDF)))
    print('')
    
    for row in times:
        print(dateToTime(row[0]),' - ',row[1],' - ',row[2])
    print('*******************************************************************')
        
    return viewDF

def getTripItinerary2(resultingTripsDF,inputs2,num=1):
    ii = num - 1
    view = resultingTripsDF.iloc[ii]['itinerary']
    seg = [item['duration']/3600 for item in resultingTripsDF.iloc[ii]['timeSegments']]
    viewDF = pd.DataFrame(resultingTripsDF.iloc[ii]['itinerary'])
            
    # get times for each location
    times = []
    segcount = 0
    for ii in range(len(view)):
        if len(view) == 1:
            # start day at home
            times.append([view[ii]['startTime'],inputs2['startDayCity'],'Drive Load to Destination'])
            # arrive at origin to pickup
            times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['origin'],'Arrive at Origin & Load'])
            # increment the segcount
            segcount += 1
            # finish loading and depart for trip
            times.append([times[-1][0]+dt.timedelta(hours=view[ii]['loadTime']),view[ii]['origin'],'Drive Load to Destination'])
            
            if view[ii]['nextDayDelivery']:
                # arrive at home for the evening
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),inputs2['endDayCity'],'Done for Day, with Load'])
                # increment the segcount
                segcount += 1
                # next day load delivery
                times.append([inputs2['next_date_start']+dt.timedelta(days=1,hours=seg[segcount])+dt.timedelta(hours=view[ii]['unloadTime']),view[ii]['destination'],'Next Day Delivery and Unload'])
                # increment the segcount
                segcount += 1
            else:
                # arrive at destination to unload
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['destination'],'Arrive at Destination & Unload'])
                # increment the segcount
                segcount += 1
                # finish unloading, leave for home
                times.append([times[-1][0]+dt.timedelta(hours=view[ii]['unloadTime']),view[ii]['destination'],'Head Home'])
                # arrive at home for the evening
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),inputs2['endDayCity'],'Done for Day, Empty'])
                # increment the segcount
                segcount += 1
            
        elif ii == 0:
            if inputs2['startWithLoad']:
                # start day at home
                times.append([view[ii]['startTime'],inputs2['startDayCity'],'Drive Load to Destination'])
                # arrive at destination to unload
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['destination'],'Arrive at Destination & Unload'])
                # increment the segcount
                segcount += 1
                # finish unloading, leave for new load deadhead
                times.append([times[-1][0]+dt.timedelta(hours=view[ii]['unloadTime']),view[ii]['destination'],'Deadhead to Next Load'])
            else:
                # start day at home
                times.append([view[ii]['startTime'],inputs2['startDayCity'],'Deadhead to First Load'])
                # arrive at origin to pickup
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['origin'],'Arrive at Origin & Load'])
                # increment the segcount
                segcount += 1
                # finish loading and depart for trip
                times.append([times[-1][0]+dt.timedelta(hours=view[ii]['loadTime']),view[ii]['origin'],'Drive Load to Destination'])
                # arrive at destination to unload
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['destination'],'Arrive at Destination & Unload'])
                # increment the segcount
                segcount += 1
                # finish unloading, leave for new load deadhead
                times.append([times[-1][0]+dt.timedelta(hours=view[ii]['unloadTime']),view[ii]['destination'],'Deadhead to Next Load'])
                
        elif ii == len(view)-1:
            # arrive at origin to pickup
            times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['origin'],'Arrive at Origin & Load'])
            # increment the segcount
            segcount += 1
            # finish loading and depart for trip
            times.append([times[-1][0]+dt.timedelta(hours=view[ii]['loadTime']),view[ii]['origin'],'Drive Load to Destination'])
            
            if view[ii]['nextDayDelivery']:
                # arrive at home for the evening
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),inputs2['endDayCity'],'Done for Day, with Load'])
                # increment the segcount
                segcount += 1
                # next day load delivery
                times.append([inputs2['next_date_start']+dt.timedelta(days=1,hours=seg[segcount])+dt.timedelta(hours=view[ii]['unloadTime']),view[ii]['destination'],'Next Day Delivery and Unload'])
                # increment the segcount
                segcount += 1
            else:
                # arrive at destination to unload
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['destination'],'Arrive at Destination & Unload'])
                # increment the segcount
                segcount += 1
                # finish unloading, leave for home
                times.append([times[-1][0]+dt.timedelta(hours=view[ii]['unloadTime']),view[ii]['destination'],'Head Home'])
                # arrive at home for the evening
                times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),inputs2['endDayCity'],'Done for Day, Empty'])
                # increment the segcount
                segcount += 1
            
        else:
            # arrive at origin to pickup
            times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['origin'],'Arrive at Origin & Load'])
            # increment the segcount
            segcount += 1
            # finish loading and depart for trip
            times.append([times[-1][0]+dt.timedelta(hours=view[ii]['loadTime']),view[ii]['origin'],'Drive Load to Destination'])
            # arrive at destination to unload
            times.append([times[-1][0]+dt.timedelta(hours=seg[segcount]),view[ii]['destination'],'Arrive at Destination & Unload'])
            # increment the segcount
            segcount += 1
            # finish unloading, leave for new load deadhead
            times.append([times[-1][0]+dt.timedelta(hours=view[ii]['unloadTime']),view[ii]['destination'],'Deadhead to Next Load'])
        
    #print the itinerary
    print('\n*******************************************************************')
    print('Viewing itinerary for Trip #{} out of {}'.format(num,len(resultingTripsDF)))
    print('')
    
    for row in times:
        print(dateToTime(row[0]),' - ',row[1],' - ',row[2])
    print('*******************************************************************')
        
    return viewDF

us_state_to_abbrev = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
    "District of Columbia": "DC",
    "American Samoa": "AS",
    "Guam": "GU",
    "Northern Mariana Islands": "MP",
    "Puerto Rico": "PR",
    "United States Minor Outlying Islands": "UM",
    "U.S. Virgin Islands": "VI",
}
    
# invert the dictionary
abbrev_to_us_state = dict(map(reversed, us_state_to_abbrev.items()))