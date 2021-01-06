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
    result = None
    is_byzantine = False
    board = {0: ""}

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
                board_dict=sorted({"0":board,}.iteritems()), members_name_string='Fawzi Aiboud Nygren, Karl Svensson')

    @app.get('/vote/result')
    def vote_result():
        global result, result_vector
        return template('server/result_template.tpl', result=result, final_vector=final_vector)
    #------------------------------------------------------------------------------------------------------
    
    # if honest, get vote from html request and add to result vector. Then send vote to all other nodes.
    # if byzantine, run first round and send the generated votes to all other nodes.
    @app.post('/vote/<vote_type>')
    def vote_type(vote_type):
        global result, result_vector, node_id, is_byzantine, total_no
        print "My vote is: " + str(vote_type)

        if ((vote_type == "attack" or vote_type == "retreat") and not is_byzantine):

            if vote_type == "attack":
            	vote_type = "True"
            else:
            	vote_type = "False"

            result_vector[node_id - 1] = vote_type
            thread = Thread(target=propagate_to_vessels, args=('/merge', {'node_id': node_id, 'vote_type': vote_type}))
            thread.daemon = True
            thread.start()

        elif vote_type == "byzantine" and is_byzantine:
        	
            local = compute_byzantine_vote_round1(total_no-1, total_no , True)
            print str(local)

            index = 0
            for i in range(0, total_no):

            	if i+1 != node_id:
            		ip = '10.1.0.{}'.format(str(i+1))
            		thread = Thread(target=contact_vessel, args=(ip, '/merge', {'node_id': node_id, 'vote_type': local[index]}))
            		thread.daemon = True
            		thread.start()
            		index += 1

    # Add received votes to the local result vector
    # When all honest nodes has received all votes from others, send the result vector to other nodes
    # If byzantine, run round 2 to create different result vectors and send to honest nodes.
    @app.post('/merge')
    def merge_votes():
        global result_vector, node_id, vessel_list, is_byzantine, total_no
        result_vector[int(request.forms.get('node_id')) - 1] = request.forms.get('vote_type')
        count = 1
        for i in range(0, len(result_vector)):
            if (i + 1 != node_id) and (result_vector[i] != None):
                count += 1
                print "Count is incremented to:" + str(count)
        if count == total_no and not is_byzantine:
        	thread = Thread(target=propagate_to_vessels, args=('/collect_results', {'node_id':  node_id, 'vector': json.dumps(result_vector)}))
        	thread.daemon = True
        	thread.start()
        
        # Byzantine behavior
        elif count == total_no and is_byzantine:
        	round2 = compute_byzantine_vote_round2(total_no-1, total_no, True)
        	print str(round2)
        	index = 0
        	for i in range(0, total_no):
        		if i+1 != node_id:
        			thread = Thread(target=contact_vessel, args=('10.1.0.{}'.format(str(i+1)), '/collect_results', {'node_id': node_id, 'vector': json.dumps(round2[index])}))
        			thread.daemon = True
        			thread.start()
        			index += 1

    # Receive all result vectors and add them to a dict containing all result vectors.
    @app.post('/collect_results')
    def collect_results():
    	global node_id, received_results, total_no
    	sending_id = request.forms.get('node_id')
    	received_vector = json.loads(request.forms.get('vector'))
    	received_results[int(sending_id)] = received_vector
    	received_results[node_id] = result_vector
    	print str(received_results)
    	
    	# When all the are collected, calculate final vector
    	if len(received_results) == total_no:
    		final_result_vector()

    # Compare all collected vectors, check the i:th element on each vector and count attack or retreat.
    # Add majority yo final vector.
    def final_result_vector():
    	global received_results, final_vector, result, node_id, total_no
    	
    	for i in range(0, total_no):
    		count_attack = 0
    		count_retreat = 0
    		for node, vector in received_results.iteritems():
    			if vector[i] == "True" or vector[i] == True and i+1 != node_id:
    				count_attack += 1
    			if vector[i] == "False" or vector[i]== False and i+1 != node_id:
    				count_retreat += 1

    		if count_attack >= count_retreat:
    			final_vector[i+1] = "True"
    		else:
    			final_vector[i+1] = "False"

    	print "attack: " + str(count_attack)
    	print "retreat: " + str(count_retreat)
    	print "Final vector:" + str(final_vector)

    	result = final_agreement(final_vector)
    	
    # Check the final vector, count majority and decide final agreement.
    def final_agreement(vector):

    	attack = 0
    	retreat = 0

    	for i in vector:
    		if vector[i] == "True":
    			attack += 1
    		if vector[i] == "False":
    			retreat += 1

    	if attack >= retreat:
    		return "ATTACK!"
    	else:
    		return "RETREAT!"

    # ------------------------------------------------------------------------------------------------------
    # BYZANTINE SELECTION
    # ------------------------------------------------------------------------------------------------------
    # Function that init the byzantine selection, byzantine_id is a random number, if it matches to the node
    # it is selected as a byzantine.
    def byzantine_select_init(byzantine_id):
        global node_id, is_byzantine
        # If the node that inits the selection is selected byzantine
        if byzantine_id == node_id:
            print "I am byzantine"
            is_byzantine = True
        # If the node that inits the selection is not selected as byzantine
        # Contact other nodes with the byzantine id
        else:
            propagate_to_vessels('/byzantine_select/' + str(byzantine_id))

    # Set byzantine node
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
        global vessel_list, node_id, app, result_vector, args, received_results, final_vector, total_no

        port = 80
        parser = argparse.ArgumentParser(description='Your own implementation of the distributed blackboard')
        parser.add_argument('--id', nargs='?', dest='nid', default=1, type=int, help='This server ID')
        parser.add_argument('--vessels', nargs='?', dest='nbv', default=1, type=int, help='The total number of vessels present in the system')
        args = parser.parse_args()
        node_id = args.nid
        vessel_list = dict()
        result_vector = list()
        received_results = dict()
        final_vector = dict()
        # We need to write the other vessels IP, based on the knowledge of their number
        for i in range(1, args.nbv+1):
            vessel_list[str(i)] = '10.1.0.{}'.format(str(i))
            result_vector.append(None)

        total_no = len(vessel_list)
        print "Total nodes: " + str(total_no)
        if node_id == 1:

            byzantine_id = random.randint(1, args.nbv)
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
