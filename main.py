from flask import Flask, render_template, request, redirect
app = Flask(__name__)

def findTrips(inputs,session,coords,token):
    import testTruckingFunctions as tf
    import datetime as dt
    import pandas as pd
    import numpy as np
    import openrouteservice

    
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
    df.drop(df[df['accountName'] == 'CJB FREIGHT LLC'].index, inplace = True)

    
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
    global cityOfInterest
    cityOfInterest = None
    df,coords = getNewCoordinates(df,coords,inputs)
    if cityOfInterest:
        return render_template("coordinates.html", variable = cityOfInterest)
    
      
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
    import testTruckingFunctions as tf
    import datetime as dt
    import pandas as pd
    import numpy as np
    import openrouteservice

    # get loads from Truckstop.com
            
    # create a dataframe for filtering
    df = pd.DataFrame(data)
    df.dropna(subset=['postedRate'],inplace=True)
    df.drop_duplicates(subset=(['phone','originCityState','originDeadhead','tripDistance','destinationCityState']),
                       inplace=True)
    df.drop(df[df['originCity'] == df['destinationCity']].index, inplace = True)

    # Remove any loads from unwanted brokers
    df.drop(df[df['accountName'] == 'ScrapGo LLC'].index, inplace = True)
    df.drop(df[df['accountName'] == 'CJB FREIGHT LLC'].index, inplace = True)


    # get coords of all locations
    df,coords = getNewCoordinates(df,coords,inputs2)
    if cityOfInterest:
        return(cityOfInterest)

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

def getNewCoordinates(df,coords,inputs):
    #print('Getting coordinates for all cities...')
    cities = list(set(list(df['originCityState']) + list(df['destinationCityState'])))
    from geopy.geocoders import Nominatim
    geolocator = Nominatim(user_agent='my_name')
    global cityOfInterest
    
    # if the coords for the startLoad city are not stored, get them
    if (inputs['startWithLoad']) and (inputs['startLoadCity'] not in coords.keys()):
        try:
            loc = geolocator.geocode(inputs['startLoadCity'])
            coords[inputs['startLoadCity']] = [loc.latitude,loc.longitude]
        except:
            cityOfInterest = inputs['startLoadCity']
            
            # strCoords = input('Please input coords for this city as "lat, lon": \n')
            # coords[inputs['startLoadCity']] = [float(strCoords.split(',')[0]),float(strCoords.split(',')[1])]
                
    for city in cities:
        if city not in coords.keys():
            try:
                loc = geolocator.geocode(city)
                coords[city] = [loc.latitude,loc.longitude]
            except:
                cityOfInterest = city
                
               #  strCoords = input('Please input coords for this city as "lat, lon": \n')
                
               #  try:
               #      coords[city] = [float(strCoords.split(',')[0]),float(strCoords.split(',')[1])]
               #  except:
               #      # remove the rows with this city
               #      df = df[df['originCityState'] != city]
               #      df = df[df['destinationCityState'] != city]
    
    df.reset_index(drop=True,inplace=True)    
    
    #save the new coords variable
    import pickle
    with open('./coords.pickle','wb') as f:
        pickle.dump(coords,f,protocol=pickle.HIGHEST_PROTOCOL)

    return df,coords


@app.route('/')
def inputs():
   import json
   with open('inputs.json','rb') as fp:
    global savedInputs
    savedInputs = json.load(fp)
   return render_template("inputs.html", savedInputs=list(savedInputs.values()))

@app.route('/status', methods = ['POST', 'GET'])
def status():
   global userInputs
   userInputs=(request.form)
   global progress
   progress = 'Starting Up...'
   return render_template("status.html", variable = progress)

@app.route('/getnewcoords')
def getnewcoords():
   return render_template("coordinates.html", variable = cityOfInterest)

@app.route('/savingcoords', methods = ['POST', 'GET'])
def savingcoords():
    global cityOfInterest
    strCoords = (request.form)
    newCoords = strCoords['newCoords']
    coords[cityOfInterest] = [float(newCoords.split(',')[0]),float(newCoords.split(',')[1])]
    import pickle
    with open('./coords.pickle','wb') as f:
        pickle.dump(coords,f,protocol=pickle.HIGHEST_PROTOCOL)
    cityOfInterest = None
    return redirect('/processing')


@app.route('/processing', methods = ['POST', 'GET'])
def processing():
   import testTruckingFunctions as tf
   import datetime as dt
   import pandas as pd
   import sys
   import requests
   import json
   username = 'contact@sweetwatertransportation.com'
   password = '#D@vis9063'

   with open("inputs.json", "w") as fp:
       json.dump(userInputs, fp)

   inputs={}
   inputs['date_start'] = dt.datetime(int(userInputs['startDateYear']),int(userInputs['startDateMonth']),int(userInputs['startDateDay']),int(userInputs['startDateHour']),0,0)
   inputs['date_end'] = dt.datetime(int(userInputs['endDateYear']),int(userInputs['endDateMonth']),int(userInputs['endDateDay']),int(userInputs['endDateHour']),0,0)
   # If starting at a later time today than next day, enter number of hours
   nextDayTimeCorrection = 0
   inputs['next_date_start'] = inputs['date_start']-dt.timedelta(hours=nextDayTimeCorrection)+dt.timedelta(days=1)


   inputs['loadTime'] = float(userInputs['loadTime'])
   inputs['unloadTime'] = float(userInputs['unloadTime'])
   inputs['avgSpeed'] = int(userInputs['avgSpeed'])

   inputs['excludeLoads'] = userInputs['excludeLoads']

   # Luke's house
   inputs['startCoords'] = [float(userInputs['startCoordsLat']), float(userInputs['startCoordsLong'])]
   inputs['startDayCity'] = userInputs['startDayCity'] + ", " + userInputs['startDayState']
   inputs['endCoords'] = [float(userInputs['endCoordsLat']), float(userInputs['endCoordsLong'])]
   inputs['endDayCity'] = userInputs['endDayCity'] + ", " + userInputs['endDayState']

   inputs['canDeliverNextDay'] = userInputs['canDeliverNextDay']
   inputs['startWithLoad'] = userInputs['startWithLoad']
   inputs['startLoadCity'] = userInputs['startLoadCity'] + ", " + userInputs['startLoadState']

   inputs['MPG_load'] = float(userInputs['MPG_load'])
   inputs['MPG_empty'] = float(userInputs['MPG_empty'])
   inputs['diesel'] = float(userInputs['diesel'])
   inputs['maintCostPerMile'] = float(userInputs['maintCostPerMile'])
   inputs['driverPayPerHour'] = float(userInputs['driverPayPerHour'])

   
   global inputs2
   inputs2 = inputs.copy()


   progress = 'Getting Coordinates...'

   # read in stored coordinates file
   global coords
   coords = tf.getCoordinates() # loads in stored coordinates - Do Not Remove


   global session
   session = requests.Session()
   # login and get webdriver
   session = tf.truckstopLogin(session,username,password)


   savedToken = open('token.txt','r')
   token = savedToken.read()
   savedToken.close()
   try:
      (resultingTrips, data) = findTrips(inputs,session,coords,token)
   except(ValueError):
       return redirect('/getnewcoords')
   except:
      # login and get token
      print('Token has Expired. Getting new token...')
      token = tf.getToken(username,password)
      savedToken = open('token.txt','w')
      savedToken.write(token)
      savedToken.close()
      (resultingTrips, data) = findTrips(inputs,session,coords,token)



      
   def myFunc(e):
      return e['netRate']
   resultingTrips.sort(key=myFunc,reverse=True)
   resultingTrips2=resultingTrips.copy()


   global resultsDF
   resultsDF = pd.DataFrame(resultingTrips2)
   original_stdout = sys.stdout # Save a reference to the original standard output
   import pandas
   resultsDF.to_csv('resultsDF.csv')

   try:
      resultsDF = resultsDF.sort_values(by=['netRate'],ascending=False)
      resultsDF.reset_index(drop=True,inplace=True) 
      
      netRate1 = round(resultsDF['netRate'])
      netRatePerHour1 = round(resultsDF['netRatePerHour'])
      totalRate1 = round(resultsDF['totalRate'])
      totalDistance1 = round(resultsDF['calcDistance'])
      driverPay1 = round(resultsDF['driverPay'])
      totalNet1 = driverPay1 + netRate1



      numberOfLoads=len(netRate1)

      # print itinerary for top 25 loads
      with open('results.txt', 'w') as f:
         

         sys.stdout = f # Change the standard output to the file we created.

         cc = 0
         while cc < numberOfLoads:
            cc += 1
            viewItinerary = tf.getTripItinerary(resultsDF,inputs,cc) # starts at 1
            print(' Business Net:   $' ,netRate1[cc-1])
            print(' Driver Pay:     $' ,driverPay1[cc-1])
            print(' Total Net:      $' ,totalNet1[cc-1])
            print(' Posted Rate:    $' ,totalRate1[cc-1])
            print(' Distance:        ' ,totalDistance1[cc-1], 'miles')
            print(' Net Rate/Hour:  $' ,netRatePerHour1[cc-1])
            print(' ***** Central Time Zones *****')
         
         sys.stdout = original_stdout # Reset the standard output to its original value


      inputs2['startWithLoad'] = True
      inputs2['date_start'] =inputs['next_date_start']
      inputs2['date_end'] =inputs['date_end']+dt.timedelta(days=1)
      global dataExtended
      dataExtended = tf.getTruckstopLoads2(session,inputs2,token)

      print('\nFinished calculating!  Please view the "results" file for the full results.')
   except:
       with open('results.txt', 'w') as f:
           sys.stdout = f # Change the standard output to the file we created.
           print('\n***No compatible loads. Return empty or extend end time.***')
   finally:
       sys.stdout = original_stdout # Reset the standard output to its original value
 
 
   return redirect('/results')
   
@app.route('/results', methods = ['POST', 'GET']) 
def content(): 
	with open('results.txt', 'r') as f: 
		return render_template('content.html', text=f.read())
    
@app.route('/extend', methods = ['POST', 'GET'])
def extend():
   import testTruckingFunctions as tf
   import pandas as pd
   import sys
   doYouWishToContinue = (request.form)
   extendedTripItinerarySelector = int(doYouWishToContinue['doYouWishToContinue'])-1
   ###############################################
   
   locater = resultsDF['itinerary'].loc[extendedTripItinerarySelector]
   extendedTripItinerary=[]
   extendedTripItinerary.append(locater[-1])

   inputs2['startLoadCity'] = extendedTripItinerary[0]['destination']


   (avgNetRatePerHour, extendedTrips) = findTripsExtended(inputs2,session,coords,extendedTripItinerary,dataExtended)
   
   ##############################################


   resultingTripsExt = tf.getTripStatsFast2(extendedTrips,inputs2)
   try:
      resultingTripsExt = resultingTripsExt[:5]
   finally:
      resultingTripsExtDF = pd.DataFrame(resultingTripsExt)
      original_stdout = sys.stdout # Save a reference to the original standard output

      # print itinerary for top 25 loads
      with open('extendResults.txt', 'w') as f:
            
         sys.stdout = f # Change the standard output to the file we created.
         try:
            resultingTripsExtDF = resultingTripsExtDF.sort_values(by=['netRate'],ascending=False)
            resultingTripsExtDF.reset_index(drop=True,inplace=True)
            
            netRate2 = round(resultingTripsExtDF['netRate'])
            netRatePerHour2 = round(resultingTripsExtDF['netRatePerHour'])
            totalRate2 = round(resultingTripsExtDF['totalRate'])
            totalDistance2 = round(resultingTripsExtDF['calcDistance'])
            driverPay2 = round(resultsDF['driverPay'])
            totalNet2 = driverPay2 + netRate2


            numberOfLoads=len(netRate2)
            

            
            # print itinerary for top 25 loads
            cc = 0
            while cc < numberOfLoads:
                  cc += 1
                  viewItinerary = tf.getTripItinerary2(resultingTripsExtDF,inputs2,cc) # starts at 1
                  print(' Business Net:   $' ,netRate2[cc-1])
                  print(' Driver Pay:     $' ,driverPay2[cc-1])
                  print(' Total Net:      $' ,totalNet2[cc-1])
                  print(' Posted Rate:    $' ,totalRate2[cc-1])
                  print(' Total Distance:  ' ,totalDistance2[cc-1], 'miles')
                  print(' Net Rate/Hour:  $' ,netRatePerHour2[cc-1])
                  print(' ***** Central Time Zones *****')
         except:
            print('\n***No compatible loads. Return empty or extend end time.***')

         sys.stdout = original_stdout # Reset the standard output to its original value

      return redirect('/extendResults')
   
@app.route('/extendResults', methods = ['POST', 'GET']) 
def extendContent(): 
	with open('ExtendResults.txt', 'r') as f: 
		return render_template('extend.html', text=f.read())
   

  
if __name__ == '__main__':
   app.run(debug = True)