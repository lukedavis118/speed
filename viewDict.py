# -*- coding: utf-8 -*-
"""
Created on Thu Oct 26 13:54:30 2023

@author: luke_
"""
import pickle 

        
with open('possibleLoads.pkl', 'wb') as f:
    pickle.dump(possibleLoads, f)
    
with open('possibleLoads.pkl', 'rb') as f:
    loaded_dict = pickle.load(f)