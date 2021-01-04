# coding=utf-8
# ------------------------------------------------------------------------------------------------------
# TDA596 - Lab 1
# server/server.py
# Input: Node_ID total_number_of_ID
# Student: Karl Svensson, Fawzi Aiboud Nygren
# ------------------------------------------------------------------------------------------------------
import traceback
import sys
import time
import json
import argparse
from threading import Thread
import random
from byzantine_behavior import *

from bottle import Bottle, run, request, template
import requests
# ------------------------------------------------------------------------------------------------------
try:
    app = Bottle()

    #board stores all message on the system 
    board = {0 : "Welcome to Distributed Systems Course"}
    #Init thhe first entry number
    id_number = 1

    
    result = "ATTACK"
    is_byzantine = False
    
    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    
    #This functions will add an new element
    def add_new_element_to_store(entry_sequence, element, is_propagated_call=False):
        global board, node_id
        success = False

        #If this is a propagated call, typecast the reveicedstring entry_sequence top an int.
        if is_propagated_call:
        	entry_sequence = int(entry_sequence)

        try:
           if entry_sequence not in board:
                board[entry_sequence] = element
                success = True
        except Exception as e:
            print e
        return success

    #This function will modify an element on the board
    def modify_element_in_store(entry_sequence, modified_element, is_propagated_call = False):
        global board, node_id
        success = False

        #If this is a propagated call, typecast the reveicedstring entry_sequence top an int.
        if is_propagated_call:
        	entry_sequence = int(entry_sequence)

        try:
            if entry_sequence in board:
            	board[entry_sequence] = modified_element
            	success = True
        except Exception as e:
            print e
        return success

    #This function will delete an element from the board
    def delete_element_from_store(entry_sequence, is_propagated_call = False):
        global board, node_id
        success = False

        #If this is a propagated call, typecast the reveicedstring entry_sequence top an int.
        if is_propagated_call:
        	entry_sequence = int(entry_sequence)

        try:
            if entry_sequence in board:
            	del board[entry_sequence]
            	success = True
        except Exception as e:
            print e
        return success

    # ------------------------------------------------------------------------------------------------------
    # ROUTES
    # ------------------------------------------------------------------------------------------------------
    # a single example (index) for get, and one for post
    # ------------------------------------------------------------------------------------------------------
    #No need to modify this
    @app.route('/')
    def index():
        global board, node_id
        return template('server/index.tpl', board_title='Vessel {}'.format(node_id),
                board_dict=sorted({"0":board,}.iteritems()), members_name_string='YOUR NAME')

    @app.get('/board')
    def get_board():
        global board, node_id
        print board
        return template('server/boardcontents_template.tpl',board_title='Vessel {}'.format(node_id), board_dict=sorted(board.iteritems()))
    
    @app.get('/vote/result')
    def vote_result():
        global result, result_vector
        print "RESULT GOES HERE"
        return template('server/result_template.tpl', result=result, result_vector=result_vector)
    #------------------------------------------------------------------------------------------------------
    
    @app.post('/vote/<vote_type>')
    def vote_type(vote_type):
        global result, result_vector, node_id, is_byzantine, args
        print "My vote is: " + str(vote_type)

        if ((vote_type == "attack" or vote_type == "retreat") and not is_byzantine):

            if vote_type == "attack":
            	vote_type = "True"
            else:
            	vote_type = "False"

            result_vector[str(node_id)] = vote_type
            print str(result_vector)
            thread = Thread(target=propagate_to_vessels, args=('/merge', {'node_id': node_id, 'vote_type': vote_type}))
            thread.daemon = True
            thread.start()

        elif vote_type == "byzantine" and is_byzantine:
        	
            local = compute_byzantine_vote_round1(3, 4 , True)
            print str(local)

            index = 0
            for i in range(0, args.nbv):

            	if i+1 != node_id:
            		ip = '10.1.0.{}'.format(str(i+1))
            		thread = Thread(target=contact_vessel, args=(ip, '/merge', {'node_id': node_id, 'vote_type': local[index]}))
            		thread.daemon = True
            		thread.start()
            		index += 1

            	




    @app.post('/merge')
    def merge_votes():
        global result_vector, node_id, vessel_list, is_byzantine, args
        result_vector[request.forms.get('node_id')] = request.forms.get('vote_type')
        count = 0
        for i in result_vector:
            if (i != node_id) and (result_vector[str(i)] != None):
                count += 1
        if count == len(vessel_list) and not is_byzantine:
        	thread = Thread(target=propagate_to_vessels, args=('/collect_results', {'node_id':  node_id, 'vector': json.dumps(result_vector)}))
        	thread.daemon = True
        	thread.start()
        
        elif count == len(vessel_list) - 1 and is_byzantine:
        	round2 = compute_byzantine_vote_round2(3, 4, True)
        	print str(round2)
        	index = 1
        	for i in range(0, args.nbv):
        		if i+1 != node_id:
        			thread = Thread(target=contact_vessel, args=('10.1.0.{}'.format(str(i+1)), '/collect_results', {'node_id': node_id, 'vector': json.dumps(round2[index])}))
        			thread.daemon = True
        			thread.start()
        			index += 1


    @app.post('/collect_results')
    def collect_results():
    	global node_id, received_results
    	sending_id = request.forms.get('node_id')
    	received_vector = json.loads(request.forms.get('vector'))
    	received_results[int(sending_id)] = received_vector
    	print str(received_results)
    	# Receive result_vector
    	# Add this to the received_results dict

    def final_result():
    	global received_results




    @app.post('/board')
    def client_add_received():
        '''Adds a new element to the board
        Called directly when a user is doing a POST request on /board'''
        global board, node_id, id_number

        try:
            new_entry = request.forms.get('entry')
            
            add_new_element_to_store(id_number, new_entry)
            
            # Propagate action to all other nodes:
            thread = Thread(target=propagate_to_vessels,
                            args=('/propagate/ADD/' + str(id_number), {'entry': new_entry}, 'POST'))
            thread.daemon = True
            thread.start()
            id_number = id_number +1
            return True
        except Exception as e:
            print e
        return False

    
    @app.post('/board/<element_id:int>/')
    def client_action_received(element_id):
        global board, node_id
        
        print "You receive an element"
        print "id is ", node_id
        # Get the entry from the HTTP body
        entry = request.forms.get('entry')
        
        delete_option = request.forms.get('delete') 
	    #0 = modify, 1 = delete
	    
        print "the delete option is ", delete_option
        
        #call either delete or modify
        if delete_option == "0":
        	modify_element_in_store(element_id, entry, False)
        elif delete_option == "1":
        	delete_element_from_store(element_id, False)
        
        #Propage action to all other nodes
        thread = Thread(target=propagate_to_vessels,
                            args=('/propagate/DELETEorMODIFY/' + str(element_id), {'entry': entry, 'delete': delete_option}, 'POST'))
        thread.daemon = True
        thread.start()

    #With this function you handle requests from other nodes like add modify or delete
    @app.post('/propagate/<action>/<element_id>')
    def propagation_received(action, element_id):
    	global id_number
	    #get entry from http body
        entry = request.forms.get('entry')

        # Handle requests:
        print "the action is", action
        
        # If propagation action received is ADD, add new element to board and increment id_number
        if action == "ADD":
      	 	add_new_element_to_store(element_id, entry, True)
        	id_number = int(element_id) +1


        # If propagation action received is MODIFYorDELETE
        # Get delete_option value and act accordingly
        else:
        	delete_option = request.forms.get('delete')
        	print "the delete option is ", delete_option

        	if delete_option == "0":
        		modify_element_in_store(element_id, entry, True)

        	elif delete_option == "1":
        		delete_element_from_store(element_id, True)
    
    # ------------------------------------------------------------------------------------------------------
    # BYZANTINE SELECTION
    # ------------------------------------------------------------------------------------------------------
    
    def byzantine_select_init(byzantine_id):
        global node_id, is_byzantine
        if byzantine_id == node_id:
            print "I am byzantine"
            is_byzantine = True

        else:
            propagate_to_vessels('/byzantine_select/' + str(byzantine_id))

    @app.post('/byzantine_select/<byzantine_id:int>')
    def byzantine_select(byzantine_id):
        global node_id, is_byzantine
    
        if node_id == byzantine_id:
            print "I am byzantine"
            is_byzantine = True



 
    # ------------------------------------------------------------------------------------------------------
    # DISTRIBUTED COMMUNICATIONS FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    def contact_vessel(vessel_ip, path, payload=None, req='POST'):
        # Try to contact another server (vessel) through a POST or GET, once
        success = False
        try:
            if 'POST' in req:
                res = requests.post('http://{}{}'.format(vessel_ip, path), data=payload)
            elif 'GET' in req:
                res = requests.get('http://{}{}'.format(vessel_ip, path))
            else:
                print 'Non implemented feature!'
            # result is in res.text or res.json()
            print(res.text)
            if res.status_code == 200:
                success = True
        except Exception as e:
            print e
        return success

    def propagate_to_vessels(path, payload = None, req = 'POST'):
        global vessel_list, node_id

        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != node_id: # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)

        
    # ------------------------------------------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------------------------------------------
    def main():
        global vessel_list, node_id, app, result_vector, args, received_results

        port = 80
        parser = argparse.ArgumentParser(description='Your own implementation of the distributed blackboard')
        parser.add_argument('--id', nargs='?', dest='nid', default=1, type=int, help='This server ID')
        parser.add_argument('--vessels', nargs='?', dest='nbv', default=1, type=int, help='The total number of vessels present in the system')
        args = parser.parse_args()
        node_id = args.nid
        vessel_list = dict()
        result_vector = dict()
        received_results = dict()
        # We need to write the other vessels IP, based on the knowledge of their number
        for i in range(1, args.nbv+1):
            vessel_list[str(i)] = '10.1.0.{}'.format(str(i))
            result_vector[str(i)] = None


        if node_id == 1:

            byzantine_id = random.randint(1, args.nbv)
            
            #thread = Thread(target = byzantine_select_init, args = byzantine_id)
            #thread.daemon = True
            #thread.start()
            byzantine_select_init(byzantine_id)
        

        try:
            run(app, host=vessel_list[str(node_id)], port=port)
        except Exception as e:
            print e
    # ------------------------------------------------------------------------------------------------------
    if __name__ == '__main__':
        main()
        
        
except Exception as e:
        traceback.print_exc()
        while True:
            time.sleep(60.)
