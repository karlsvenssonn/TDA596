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
from random import randint
from threading import Thread

from bottle import Bottle, run, request, template
import requests
# ------------------------------------------------------------------------------------------------------
try:
    app = Bottle()

    #board stores all message on the system 
    board = {0 : "Welcome to Distributed Systems Course"}
    #Init thhe first entry number
    id_number = 1

    leader_found = 0

    leader_node = 0

    node_id_random = 0

    random_id_list = dict()

    neighbour = 0

    neighbour_address = ''

    leader_node_ip = ''

    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    
    #This functions will add an new element
    def add_new_element_to_store(entry_sequence, element, is_propagated_call=False):
        global board, node_id
        success = False

        #If this is a propagated call, typecast the reveiced string 'entry_sequence' to an int.
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

        #If this is a propagated call, typecast the reveiced'string 'entry_sequence' to an int.
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

        #If this is a propagated call, typecast the reveiced string 'entry_sequence' to an int.
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
        global board, node_id, id_random_list
        print board

        return template('server/boardcontents_template.tpl',board_title='Vessel {}'.format(node_id), board_dict=sorted(board.iteritems()))
    
    #------------------------------------------------------------------------------------------------------
        
    # You NEED to change the follow functions
    @app.post('/board')
    def client_add_received():
        '''Adds a new element to the board
        Called directly when a user is doing a POST request on /board'''
        global board, node_id, id_number, leader_node_ip, leader_node

        try:
            new_entry = request.forms.get('entry')

            print "leader:" + str(leader_node)

            print "My ID:" + str(node_id)

            # Leader should add directly to board and propagate to others
            if str(leader_node) == str(node_id):

            	add_new_element_to_store(id_number, new_entry)

            	thread = Thread(target=propagate_to_vessels,
            					args=("/propagate/ADD/" + str(id_number), {'entry': new_entry}))
            	thread.daemon = True
            	thread.start()
            	id_number = id_number + 1

            	return True

            # Send add request to leader
            else:
                
	            thread = Thread(target=contact_vessel,
	            				args=(str(leader_node_ip), "/leader/add", {'entry': new_entry}))
	            thread.daemon = True
	            thread.start()

	            return True

        except Exception as e:
            print e
        return False

    
    @app.post('/board/<element_id:int>/')
    def client_action_received(element_id):
        global board, node_id, leader_node_ip, leader_node

        print "Modify or Delete"
        print "id is ", node_id

        # Get the entry from the HTTP body
        entry = request.forms.get('entry')
        
        delete_option = request.forms.get('delete') 
	    #0 = modify, 1 = delete
	    
        print "the delete option is ", delete_option
        # Leader should modify or delete directly to board and propagate the change to others.
        if str(leader_node) == str(node_id):

        	if delete_option == "0":

        		# Modify in leader board
        		modify_element_in_store(element_id, entry)

        	elif delete_option == "1":

        		# Delete in leader board
        		delete_element_from_store(element_id)
        		

        	# Propagate to all other nodes
        	thread = Thread(target=propagate_to_vessels,
        					args=("/propagate/DELETEorMODIFY/" + str(element_id), {'entry': entry, 'delete': delete_option}))
        	thread.daemon = True
        	thread.start()

        # Send modify or delete request to leader
        else:
        
	        #call either delete or modify
	        if delete_option == "0":

	        	thread = Thread(target=contact_vessel,
	        					args=(leader_node_ip, "/leader/modify/" + str(element_id), {'entry': entry}))
	        	thread.daemon = True
	        	thread.start()

	        elif delete_option == "1":

	        	thread = Thread(target=contact_vessel,
	        					args=(leader_node_ip, "/leader/delete/" + str(element_id), {'entry': entry}))
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
    # Leader functions
    # ------------------------------------------------------------------------------------------------------

 	# Leader receives an add request from a node.
 	# Leader adds this entry to the board, then propagates this to all other nodes
    @app.post('/leader/add')
    def leader_add():
        global id_number
        print "Leader received add"
        
        try:
            new_entry = request.forms.get('entry')
            
            add_new_element_to_store(id_number, new_entry, True)
            
            # Prapagate the added entry to other nodes
            thread = Thread(target=propagate_to_vessels,
                            args=("/propagate/ADD/" + str(id_number), {'entry': new_entry}))
            thread.daemon = True
            thread.start()

            # Increment ID for the next entry
            id_number = id_number + 1

            return True

        except Exception as e:
            print e
        return False
        
    # Leader receives a modify request from a node.
    # Leader deletes this from the board and then propagates this to all other nodes
    @app.post('/leader/modify/<element_id>')
    def leader_modify(element_id):
    	print "Leader received modify"

    	try:
    		entry = request.forms.get('entry')
    		delete_option = 0

    		modify_element_in_store(element_id, entry, True)

    		# Progagate modified entry to other nodes
    		thread = Thread(target=propagate_to_vessels,
    						args=("/propagate/DELETEorMODIFY/" + str(element_id), {'entry': entry, 'delete': delete_option}))
        	thread.daemon = True
        	thread.start()

        	return True

        except Exception as e:
        	print e
        return False

    # Leader receives a delete request from a node.
    # Leader deletes this from the board and then propragates this to all other nodes
    @app.post('/leader/delete/<element_id>')
    def leader_delete(element_id):
        print "Leader received delete"

        try:
        	entry = request.forms.get('entry')
        	delete_option = 1

        	delete_element_from_store(element_id, True)

        	# Propagate deleted entry to other nodes
        	thread = Thread(target=propagate_to_vessels,
        					args=("/propagate/DELETEorMODIFY/" + str(element_id), {'entry': entry, 'delete': delete_option}))
       		thread.daemon = True
        	thread.start()

        	return True

        except Exception as e:
        	print e
        return False
	
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
    # LEADER ELECTION
    # ------------------------------------------------------------------------------------------------------
    # This leader election assumes a ring topology and that all nodes knows it's right side neighbour.
    # A node starts a new election by calling "start_election". We wait for all nodes to become available.
    # The node that started the election will contact it's neighbour and send a dictionary that contains the nodes random id.
    # In the "leader_elect" funtion, the neighour receives the list from its neighbour.
    # It checks if it's node_id is present in this dictionary.
    # If the node doesn't exist id att itself with node_id as key and it's random id as value. Then sends the dictionary to it's neighbour.
    # 
    # If node_id exists in the received list, it means tat the dictionarty has made one round in the ring and all nodes have added
    # it's random id. Now we are ready to elect a leader!
    # We check the dictionart and picks the key(node_id) that is associated with the highest random id.
    # This node is elected leader. We then start a propagation to all nodes, to tell them who the new leader is.
    # All nodes saves the IP address to the leader.
	# ------------------------------------------------------------------------------------------------------
    def start_election():
		global neighbour_address, random_id_list

		path = "/election"
		# Should allow node 1 to wake up first, then node 2,3,4,5,6 etc.
		time.sleep(node_id)
		# Contact neighbour to start the election.
		thread = Thread(target=contact_vessel, args=(neighbour_address, path, random_id_list))
		thread.daemon = True
		thread.start()

	# This function is only run by the node that starts the election
    @app.post('/election')
    def leader_elect():
    	global node_id, node_id_random, neighbour_address, leader_node, leader_node_ip
    	
    	received = dict(request.forms)
    	path = "/election"

    	if str(node_id) not in received:
    		received[str(node_id)] = str(node_id_random)

    		print "Added:" + str(node_id) + "Sent to:" + str(neighbour_address)
    		print "My list of currently received ID's: \n" + str(received)

    		requests.post('http://{}{}'.format(neighbour_address, path), data=received)
    	
    	# If node_id is in the received list, one rounde in the ring is completed and a leader can be elected.
    	elif str(node_id) in received:
    		
    		print "My list of currently received ID's: \n" + str(received)
    		# Elect leader with the highest random ID
    		leader_node = max(received, key = received.get)

    		print "Leader node is: " + (leader_node) + " and value is " + (received[leader_node])
    		# Save IP address to leader node
    		leader_node_ip = '10.1.0.{}'.format(leader_node)

    		thread = Thread(target = propagate_to_vessels, args=('/leader_prop/leader', {'leader':leader_node}))
    		thread.daemon = True
    		thread.start()
    
    # Propagate the elected leader to other nodes			
    @app.post('/leader_prop/leader')
    def leader_propagation():
    	global leader_node_ip, leader_node
    	# Get the elected leader
    	leader_node = request.forms.get('leader')
    	# Save the IP address to leader node
    	leader_node_ip = '10.1.0.{}'.format(leader_node)
    	print 'Leader IP:' + str(leader_node_ip)


    # ------------------------------------------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------------------------------------------
    def main():
        global vessel_list, node_id, app, node_id_random, id_random_list, neighbour_address

        port = 80
        parser = argparse.ArgumentParser(description='Your own implementation of the distributed blackboard')
        parser.add_argument('--id', nargs='?', dest='nid', default=1, type=int, help='This server ID')
        parser.add_argument('--vessels', nargs='?', dest='nbv', default=1, type=int, help='The total number of vessels present in the system')
        args = parser.parse_args()
        node_id = args.nid
        vessel_list = dict()

        # We need to write the other vessels IP, based on the knowledge of their number
        for i in range(1, args.nbv+1):
            vessel_list[str(i)] = '10.1.0.{}'.format(str(i))
        
        # Assign a random number and this to a list random_id list.
        node_id_random = randint(0, 1000)
        random_id_list[str(node_id)] = str(node_id_random)
        print "Current node ID, random ID: " + str(random_id_list)
        
        # Create ring topology by assigning its right side neighbour.
   		# Save the neighbours address.
        neighbour = node_id % len(vessel_list)+1
        neighbour_address = '10.1.0.{}'.format(str(neighbour))

        print "Neighbour node ID, IP: " + str(neighbour) + ", " + neighbour_address

        # Give all nodes sufficient time to wake up, stops working 100% around 2-3 seconds on VM
        #time.sleep(node_id)
        # Init leader election
        if node_id == 1:
        	thread = Thread(target=start_election)
        	thread.daemon=True
        	thread.start()

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
