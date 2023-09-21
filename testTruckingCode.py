# -*- coding: utf-8 -*-
"""
Created on Fri Jun  2 11:35:41 2023

@author: luke_
""" 

import testTruckingFunctions as tf
import datetime as dt
import pandas as pd
import numpy as np
import openrouteservice


def findTrips(inputs,session,coords,token):
    
    # get loads from Truckstop.com
    data = tf.getTruckstopLoads(session,inputs,token)
            
    # create a dataframe for filtering
    df = pd.DataFrame(data)
    df.dropna(subset=['postedRate'],inplace=True)
    df.drop_duplicates(subset=(['phone','originCityState','originDeadhead','tripDistance','destinationCityState']),
                       inplace=True)
    df.drop(df[df['originCity'] == df['destinationCity']].index, inplace = True)
    
    # Remove any loads from unwanted brokers
    df.drop(df[df['accountName'] == 'ScrapGo LLC'].index, inplace = True)
    
    # delete all rows with unavailable loads
    if inputs['excludeLoads']:
        numExcludedLoads = int(input('How many loads do you wish to exclude: '))
        c=0
        while c<numExcludedLoads:
            removeLoadsOrigin = input('Origin you wish to remove from results: ')
            removeLoadsDestination = input('Destination you wish to remove from results: ')
            badLoads = df[ (df['originCity'] == removeLoadsOrigin) | (df['destinationCity'] == removeLoadsDestination) ].index
            df.drop(badLoads , inplace=True)
            print('Load Removed')
            c=c+1
    

    
    # get coords of all locations
    df,coords = tf.getNewCoordinates(df,coords,inputs)
    
      
    # load in openrouteservice for distances & durations
    
    client = openrouteservice.Client(key='5b3ce3597851110001cf62482f18c49ea3164600be2f218e26d9edc4')
    
    routingServiceStatus = 0
    # if starting with a load, add it first
    itinerary = []
    if inputs['startWithLoad']:
        
# IF ERROR IS DUE TO SERVER BEING DOWN FOR OPENROUTESERVICE, SWITCH METHODS ---

        try:        
            initialTrip = client.directions([inputs['startCoords'][::-1],
                                          coords[inputs['startLoadCity']][::-1]],
                                          radiuses=[5000],units='mi')['routes'][0]['summary']
            routingServiceStatus = 1
        except:
            try:
                print('Routing Service Failed. Re-Trying with new key...')
                client = openrouteservice.Client(key='5b3ce3597851110001cf62483a6cbc54da474d589da29850b9470abf')
                initialTrip = client.directions([inputs['startCoords'][::-1],
                                              coords[inputs['startLoadCity']][::-1]],
                                              radiuses=[5000],units='mi')['routes'][0]['summary']
                routingServiceStatus = 2
            except:
                print('Routing Service Failed Again. Manual Mode Enabled.')
                initialTrip = []
                initialTrip.append(int(input('Enter distance to startWithLoad city in miles: ')))
                initialTrip.append((int(input('Enter time to startWithLoad city in minutes: ')))*60)
                routingServiceStatus = 3
                
        #______________________________________________________________________________

    
        if routingServiceStatus<3:
            itinerary.append({
                'id': np.nan,
                'phone': np.nan,
                'origin': inputs['startDayCity'],
                'destination': inputs['startLoadCity'],
                'originCoords': inputs['startCoords'],
                'destinationCoords': coords[inputs['startLoadCity']],
                'originDeadhead': np.nan,                            
                'tripDistance': initialTrip['distance'],         
                'postedRate': np.nan,
                'rpm': np.nan,
                'accountName': np.nan,
                'daysToPay': np.nan,
                'realRPM': np.nan,
                'startTime': inputs['date_start'],
                'endTime': (inputs['date_start'] +     
                            dt.timedelta(seconds=initialTrip['duration']) +
                            dt.timedelta(hours=inputs['unloadTime'])),
                'loadTime': np.nan,
                'unloadTime': inputs['unloadTime'],
                'nextDayDelivery': False
            })
        else:
            itinerary.append({
                'id': np.nan,
                'phone': np.nan,
                'origin': inputs['startDayCity'],
                'destination': inputs['startLoadCity'],
                'originCoords': inputs['startCoords'],
                'destinationCoords': coords[inputs['startLoadCity']],
                'originDeadhead': np.nan,            
                'tripDistance': initialTrip[0],                
                'postedRate': np.nan,
                'rpm': np.nan,
                'accountName': np.nan,
                'daysToPay': np.nan,
                'realRPM': np.nan,
                'startTime': inputs['date_start'],
                'endTime': (inputs['date_start'] + 
                            dt.timedelta(seconds=initialTrip[1]) +    
                            dt.timedelta(hours=inputs['unloadTime'])),
                'loadTime': np.nan,
                'unloadTime': inputs['unloadTime'],
                'nextDayDelivery': False
            })        
    
    # find all possible first loads from current location
    
    print('\nFinding initial list of possible loads...')
    firstLoads = tf.getNextPossibleLegs(df,coords,inputs,itinerary)
    
    # initialize the finalTrips variable
    finalTrips = []
    
    # loop through loads and find trip continuations
    cc = 0
    for row in firstLoads:
        cc += 1
        print('Processing {} out of {}'.format(cc,len(firstLoads)))
        newItinerary = itinerary + [tf.loadToItinerary(row)]
        finalTrips.append({
            'itinerary': newItinerary
        })
        if not row['nextDayDelivery']:
            possibleLoads = tf.getNextPossibleLegs(df,coords,inputs,newItinerary)
            if len(possibleLoads)>0:
                # call a recursive function to search until out of time
                finalTrips = tf.continueTripSearch(df,coords,inputs,newItinerary,finalTrips,possibleLoads)
    
    
    print('\nGetting final stats for each potential trip...')
    
    routingServiceStatus = 3 #int(input('Enter "0" to use Routing Service or "3" to use Fast Mode:'))

# IF ERROR IS DUE TO SERVER BEING DOWN FOR OPENROUTESERVICE, SWITCH METHODS ---
    if routingServiceStatus<3:
        try:
            resultingTrips = tf.getTripStats(client,finalTrips,inputs)
        except:
            print('***Error routing. Possible cause of incorrect coordinates on file.***\nSwapping to fast version:')
            resultingTrips = tf.getTripStatsFast(finalTrips,inputs)
    else:
        resultingTrips = tf.getTripStatsFast(finalTrips,inputs)

#______________________________________________________________________________

    return resultingTrips, data

def findTripsExtended(inputs2,session,coords,row,data):
    # get loads from Truckstop.com
            
    # create a dataframe for filtering
    df = pd.DataFrame(data)
    df.dropna(subset=['postedRate'],inplace=True)
    df.drop_duplicates(subset=(['phone','originCityState','originDeadhead','tripDistance','destinationCityState']),
                       inplace=True)
    df.drop(df[df['originCity'] == df['destinationCity']].index, inplace = True)

    # Remove any loads from unwanted brokers
    df.drop(df[df['accountName'] == 'ScrapGo LLC'].index, inplace = True)


    # get coords of all locations
    df,coords = tf.getNewCoordinates(df,coords,inputs2)
    

    # get start and end city name
    from geopy.geocoders import Nominatim
    geolocator = Nominatim(user_agent='my_name')
    import geopy.distance as gd


    # if starting with a load, add it first
    itinerary = []
    if inputs2['startWithLoad']:

        
        itinerary.append({
            'id': np.nan,
            'phone': np.nan,
            'origin': inputs2['startDayCity'],
            'destination': inputs2['startLoadCity'],
            'originCoords': inputs2['startCoords'],
            'destinationCoords': coords[inputs2['startLoadCity']],
            'originDeadhead': np.nan,
            'tripDistance': max((gd.geodesic(inputs2['startCoords'],coords[inputs2['startLoadCity']]).miles)*1.15,20),
            'postedRate': np.nan,
            'rpm': np.nan,
            'accountName': np.nan,
            'daysToPay': np.nan,
            'realRPM': np.nan,
            'startTime': inputs2['date_start'],
            'endTime': inputs2['date_start'] + 
                        dt.timedelta(hours=(max((gd.geodesic(inputs2['startCoords'],coords[inputs2['startLoadCity']]).miles)*1.15,20))/inputs2['avgSpeed']+inputs2['unloadTime']),
            'loadTime': np.nan,
            'unloadTime': inputs2['unloadTime'],
            'nextDayDelivery': False
        })
        
    
    # find all possible first loads from current location
    
    firstLoads = tf.getNextPossibleLegs2(df,coords,inputs2,itinerary)
    
    # initialize the finalTrips variable
    extendedTrips = []
    
    # loop through loads and find trip continuations
    cc = 0
    for row in firstLoads[:25]:
        cc += 1
        newItinerary = itinerary + [tf.loadToItinerary(row)]
        extendedTrips.append({
            'itinerary': newItinerary
        })
    # averageRatePerHour = []    
    # for row in firstLoads[:5]:
    #     averageRatePerHour.append(row['netRatePerHour'])
    # avgRatePerHour= sum(averageRatePerHour) / len(averageRatePerHour)
    averageNetRatePerHour = []    
    for row in firstLoads[:25]:
        averageNetRatePerHour.append(row['netRatePerHour'])
    if len(averageNetRatePerHour)>0:
        avgNetRatePerHour= sum(averageNetRatePerHour) / len(averageNetRatePerHour)
    else:
        avgNetRatePerHour=0
    
    #results = tf.getTripStats(client,finalTrips,inputs2)
    return avgNetRatePerHour, extendedTrips
    
    # resultsDF = pd.DataFrame(results)
    # resultsDF = resultsDF.sort_values(by=['netRatePerHour'],ascending=False)
    # resultsDF.reset_index(drop=True,inplace=True)
    # return resultsDF

