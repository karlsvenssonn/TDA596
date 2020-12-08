# coding=utf-8
# ------------------------------------------------------------------------------------------------------
# TDA596 - Lab 1
# server/server.py
# Input: Node_ID total_number_of_ID
# Students: Fawzi Aiboud Nygren, Karl Svensson
# ------------------------------------------------------------------------------------------------------
import traceback
import time
import argparse
from threading import Thread
from bottle import Bottle, run, request, template
import requests
import json

class Server:
    def __init__(self, host, port, node_list, node_id, vector_clock, roll_back):
        self._host = host
        self._port = port
        self._app = Bottle()
        self._route()
        self.board = {0: "Welcome to Distributed Systems Course"}
        self.node_list = node_list
        self.node_id = node_id
        self.vector_clock = vector_clock
        self.roll_back = roll_back
        
        

    def _route(self):
        self._app.route('/', method="GET", callback=self.index)
        self._app.route('/board', method="GET", callback=self.get_board)
        self._app.route('/board', method="POST", callback=self.client_add_received)
        self._app.route('/board/<element_id:int>/', method="POST", callback=self.client_action_received)
        self._app.route('/propagate/<action>/<element_id:int>', method="POST", callback=self.propagation_received)


    def start(self):
        self._app.run(host=self._host, port=self._port)


    # ------------------------------------------------------------------------------------------------------
    # ROOUTE FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    # GET '/'
    def index(self):
        return template('server/index.tpl', board_title='Node {}'.format(self.node_id),
                        board_dict={"0": self.board, }.iteritems(), members_name_string='Karl Svensson, '
                                                                                           'Fawzi Aiboud Nygren')

    # GET '/board'
    def get_board(self):
        print self.board
        return template('server/boardcontents_template.tpl', board_title='Node {}'.format(self.node_id),
                        board_dict=self.board.iteritems() )

    # POST '/board'
    def client_add_received(self):
        """Adds a new element to the board
        Called directly when a user is doing a POST request on /board"""
        # Increment vector clock by 1
        self.vector_clock[self.node_id] = self.vector_clock[self.node_id] + 1
        print self.vector_clock

        try:

            new_entry = request.forms.get('entry')
            element_id = len(self.board)  # you need to generate a entry number
            self.add_new_element_to_store(element_id, new_entry)

            thread = Thread(target=self.propagate_to_nodes,
                            args=('/propagate/ADD/' + str(element_id),
                                  {'entry': new_entry, 'VC': json.dumps(self.vector_clock),'sending_node':self.node_id},
                                  'POST'))

            thread.daemon = True
            thread.start()
            return '<h1>Successfully added entry</h1>'
        except Exception as e:
            print e
        return False


    # POST '/board/<element_id:int>/'
    def client_action_received(self, element_id):
        print "You receive an action"
        print "id is ", self.node_id
        # Increment vector clock by 1
        self.vector_clock[self.node_id] = self.vector_clock[self.node_id] + 1
        print "Clock incremented"

        try:
            # Get the entry from the HTTP body
            entry = request.forms.get('entry')

            delete_option = request.forms.get('delete')
            # 0 = modify, 1 = delete

            print "the delete option is ", delete_option

            # call either delete or modify
            if delete_option == '0':
                self.modify_element_in_store(element_id, entry)
                propagate_action = 'MODIFY'
            elif delete_option == '1':
                
                print 'Element id is: ', element_id

                self.delete_element_from_store(element_id)
                propagate_action = 'DELETE'
            else:
                raise Exception("Unaccepted delete option")

            print propagate_action

            # propage to other nodes
            thread = Thread(target=self.propagate_to_nodes,
                            args=('/propagate/' + propagate_action + '/' + str(element_id),
                                  {'entry': entry, 'VC':json.dumps(self.vector_clock), 'sending_node':self.node_id},
                                  'POST'))
            thread.daemon = True
            thread.start()
            return '<h1>Successfully ' + propagate_action + ' entry</h1>'
        except Exception as e:
            print e
        return False
    


    # With this function you handle requests from other nodes like add modify or delete
    # POST '/propagate/<action>/<element_id:int>'
    def propagation_received(self, action, element_id):
        
        # Get entry
        entry = request.forms.get('entry')

        # Get the senders node_id
        sending_node = request.forms.get('sending_node')
        print "Received message from: " + str(sending_node)

        # Get the senders veckor_clock list
        VC = json.loads(request.forms.get('VC'))

        res = self.compare_vector(self.vector_clock, VC, sending_node)
        print "Compare result: " + str(res)
        if res == -1:
        	print "CONCURRENT"

        # Merge local vector_clock with received vector_clock
        for i in self.vector_clock:
        	self.vector_clock[i] = max(self.vector_clock[i], VC[str(i)])

        print "My merged vector clock : " + str(self.vector_clock)

        # Increment local vector clock by 1
        self.vector_clock[self.node_id] = self.vector_clock[self.node_id] + 1
        print "Click incremented"
       
        print "the action is", action
        print "The Element id is" +str(element_id)

        # Handle requests
        if action == 'ADD':
            # Add the board entry
            self.add_new_element_to_store(element_id, entry)
            

        elif action == 'MODIFY':
            # Modify the board entry

            # Concurrent modifi:

			self.modify_element_in_store(element_id, entry)
            	

        elif action == 'DELETE':
            # Delete the entry from the board
            self.delete_element_from_store(element_id)

        
        


    def compare_vector(self, local_clock, received_clock, sending_node):
    	local_first = 0
    	received_first = 0

    	'''
    	Question:
   		When to compare the two vectors_lists?
   		Add when received prop and add this prop?
   		How to act after compare?
    	'''

    	print "My vector list: " + str(local_clock)
    	print "Received list: " + str(received_clock)

    	for value in local_clock:
    		if local_clock[value] >= received_clock[str(value)]:
    			local_first = local_first + 1
    				
    		if local_clock[value] <= received_clock[str(value)]:
    			received_first = received_first + 1

    	print ">=: " + str(local_first)
    	print "<=: " + str(received_first)

    	if local_first == len(local_clock):
    		return 1

    	elif received_first == len(local_clock):
    		return 0

    	else:

    		return -1

		
    # ------------------------------------------------------------------------------------------------------
    # COMMUNICATION FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    def contact_single_node(self, node_ip, path, payload=None, req='POST'):
        # Try to contact another server (node) through a POST or GET, once
        success = False
        try:
            if 'POST' in req:
                res = requests.post('http://{}{}'.format(node_ip, path), data=payload)
            elif 'GET' in req:
                res = requests.get('http://{}{}'.format(node_ip, path))
            else:
                raise Exception('Non implemented feature!')
                # print 'Non implemented feature!'
            # result is in res.text or res.json()
            print(res.text)
            if res.status_code == 200:
                success = True
        except Exception as e:
            print e
        return success


    def propagate_to_nodes(self, path, payload=None, req='POST'):
        # global vessel_list, node_id

        for node_id, node_ip in self.node_list.items():
            if int(node_id) != self.node_id:  # don't propagate to yourself
                success = self.contact_single_node(node_ip, path, payload, req)
                if not success:
                    print "\n\nCould not contact node {}\n\n".format(self.node_id)


    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # ------------------------------------------------------------------------------------------------------

    def add_new_element_to_store(self, entry_sequence, element):
        success = False
        
        # Increment vector clock by 1
        #self.vector_clock[self.node_id] = self.vector_clock[self.node_id] + 1

        try:
            if entry_sequence not in self.board:
            	self.board[entry_sequence] = element
                success = True
        except Exception as e:
            print e
        return success
    
    def modify_element_in_store(self, entry_sequence, modified_element):
        success = False

        # Increment vector clock by 1
        #self.vector_clock[self.node_id] = self.vector_clock[self.node_id] + 1

        try:
            if entry_sequence in self.board:
            	self.roll_back = self.board[entry_sequence]
                self.board[entry_sequence] = modified_element
            success = True
        except Exception as e:
            print e
        return success

    def delete_element_from_store(self, entry_sequence):
        success = False
        # Increment vector clock by 1
        #self.vector_clock[self.node_id] = self.vector_clock[self.node_id] + 1
        
        try:
            # If it does not exist we count it as a successful delete as well
            if entry_sequence in self.board:
                # Increment vector clock by 1
       	 		#self.vector_clock[self.node_id] = self.vector_clock[self.node_id] + 1
                del self.board[entry_sequence]
                '''
                for i in range(entry_sequence+1, len(self.board)+1):
                	new_key= i-1
                	old_key = i
                	self.board[i-1] = self.board.pop(i)
				'''
				
            success = True
        except Exception as e:
            print e
        return success



# ------------------------------------------------------------------------------------------------------
# EXECUTION
# ------------------------------------------------------------------------------------------------------
def main():

    parser = argparse.ArgumentParser(description='Your own implementation of the distributed blackboard')
    parser.add_argument('--id', nargs='?', dest='nid', default=1, type=int, help='This server ID')
    parser.add_argument('--vessels', nargs='?', dest='nbv', default=1, type=int,
                        help='The total number of nodes present in the system')
    args = parser.parse_args()
    node_id = args.nid
    node_list = {}
    vector_clock = dict()
    roll_back = ""
    
    # We need to write the other nodes IP, based on the knowledge of their number
    for i in range(1, args.nbv + 1):
        node_list[str(i)] = '10.1.0.{}'.format(str(i))
        vector_clock[i] = 0
        


    try:
        server = Server(host=node_list[str(node_id)], port=80, node_list = node_list, node_id = node_id, vector_clock = vector_clock, roll_back = roll_back)
        server.start()

    except Exception as e:
        print e
        traceback.print_exc() 
# ------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    main()
