from flask import Flask, render_template, request, redirect
app = Flask(__name__)
@app.route('/')
def inputs():
   return render_template("inputs.html")

@app.route('/status', methods = ['POST', 'GET'])
def status():
   global userInputs
   userInputs=(request.form)
   global progress
   progress = 'Starting Up...'
   return render_template("status.html", variable = progress)

@app.route('/processing', methods = ['POST', 'GET'])
def processing():
   import testTruckingFunctions as tf
   import testTruckingCode as tfData
   import datetime as dt
   import pandas as pd
   import sys
   import requests
   username = 'contact@sweetwatertransportation.com'
   password = '#D@vis9063'

   

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
   inputs['startDayCity'] = userInputs['startDayCity']
   inputs['endCoords'] = [float(userInputs['endCoordsLat']), float(userInputs['endCoordsLong'])]
   inputs['endDayCity'] = userInputs['endDayCity']

   inputs['canDeliverNextDay'] = userInputs['canDeliverNextDay']
   inputs['startWithLoad'] = userInputs['startWithLoad']
   inputs['startLoadCity'] = userInputs['startLoadCity']

   inputs['MPG_load'] = float(userInputs['MPG_load'])
   inputs['MPG_empty'] = float(userInputs['MPG_empty'])
   inputs['diesel'] = float(userInputs['diesel'])
   inputs['maintCostPerMile'] = float(userInputs['maintCostPerMile'])
   
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
      (resultingTrips, data) = tfData.findTrips(inputs,session,coords,token)
   except:
      # login and get token
      print('Token has Expired. Getting new token...')
      token = tf.getToken(username,password)
      savedToken = open('token.txt','w')
      savedToken.write(token)
      savedToken.close()
      (resultingTrips, data) = tfData.findTrips(inputs,session,coords,token)



      
   def myFunc(e):
      return e['netRatePerHour']
   resultingTrips.sort(key=myFunc,reverse=True)
   resultingTrips2=resultingTrips.copy()

   global resultsDF
   resultsDF = pd.DataFrame(resultingTrips2)
   try:
      resultsDF = resultsDF.sort_values(by=['netRate'],ascending=False)
      resultsDF.reset_index(drop=True,inplace=True) 
      
      netRate1 = round(resultsDF['netRate'])
      netRatePerHour1 = round(resultsDF['netRatePerHour'])
      totalRate1 = round(resultsDF['totalRate'])
      totalDistance1 = round(resultsDF['calcDistance'])



      numberOfLoads=len(netRate1)
      original_stdout = sys.stdout # Save a reference to the original standard output

      # print itinerary for top 25 loads
      with open('results.txt', 'w') as f:
         

         sys.stdout = f # Change the standard output to the file we created.

         cc = 0
         while cc < numberOfLoads:
            cc += 1
            viewItinerary = tf.getTripItinerary(resultsDF,inputs,cc) # starts at 1
            print(' Net Rate:       $' ,netRate1[cc-1])
            print(' Total Rate:     $' ,totalRate1[cc-1])
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
         original_stdout = sys.stdout
         sys.stdout = f # Change the standard output to the file we created.
         print('\n***No compatible loads. Return empty or extend end time.***')
         sys.stdout = original_stdout
      print('\n***No compatible loads. Return empty or extend end time.***')
      
 
 
   return redirect('/results')
   
@app.route('/results', methods = ['POST', 'GET']) 
def content(): 
	with open('results.txt', 'r') as f: 
		return render_template('content.html', text=f.read())
    
@app.route('/extend', methods = ['POST', 'GET'])
def extend():
   import testTruckingFunctions as tf
   import testTruckingCode as tfData
   import pandas as pd
   import sys


   doYouWishToContinue = (request.form)
   extendedTripItinerarySelector = int(doYouWishToContinue['doYouWishToContinue'])-1
   ###############################################
   
   locater = resultsDF['itinerary'].loc[extendedTripItinerarySelector]
   extendedTripItinerary=[]
   extendedTripItinerary.append(locater[-1])

   inputs2['startLoadCity'] = extendedTripItinerary[0]['destination']


   (avgNetRatePerHour, extendedTrips) = tfData.findTripsExtended(inputs2,session,coords,extendedTripItinerary,dataExtended)
   
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

            numberOfLoads=len(netRate2)
            

            
            # print itinerary for top 25 loads
            cc = 0
            while cc < numberOfLoads:
                  cc += 1
                  viewItinerary = tf.getTripItinerary2(resultingTripsExtDF,inputs2,cc) # starts at 1
                  print(' Net Rate:       $' ,netRate2[cc-1])
                  print(' Total Rate:     $' ,totalRate2[cc-1])
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