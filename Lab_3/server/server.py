# coding=utf-8
# ------------------------------------------------------------------------------------------------------
# TDA596 - Lab 1
# server/server.py
# Input: Node_ID total_number_of_ID
# Students: Socrates, Plato, Aristotle
# ------------------------------------------------------------------------------------------------------
import traceback
import time
import argparse
from threading import Thread
from bottle import Bottle, run, request, template
import requests
import json
from operator import itemgetter


class Server:
    def __init__(self, host, port, node_list, node_id, LC, queue):
        self._host = host
        self._port = port
        self._app = Bottle()
        self._route()
        self.board = {0: "Welcome"}
        self.node_list = node_list
        self.node_id = node_id
        self.LC = LC
        self.queue = queue
        

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
                        board_dict=sorted({"0": self.board, }.iteritems()), members_name_string='Fawzi Aiboud Nygren, ''Karl Svensson')

    # GET '/board'
    def get_board(self):
        print self.board
        return template('server/boardcontents_template.tpl', board_title='Node {}'.format(self.node_id),
                        board_dict=sorted(self.board.iteritems()))

    # POST '/board'
    def client_add_received(self):
        """Adds a new element to the board
        Called directly when a user is doing a POST request on /board"""
        try:
            # Increment logical clock because new event
            self.LC = self.LC + 1
            # Get entry from the HTTP body
            new_entry = request.forms.get('entry')
            element_id = len(self.board)  # you need to generate a entry number
            
            # Create message to send in propagation
            msg = {'entry': new_entry, 'LC': self.LC, 'node_id': self.node_id, 'action': "ADD"}
            # Add the new entry to the queue
            self.queue.append(msg)
            # Update the board according to the queue
            self.handle_queue()

            # Propagate to other nodes
            thread = Thread(target=self.propagate_to_nodes,
                            args=('/propagate/ADD/' + str(element_id), json.dumps(msg), 'POST'))

            thread.daemon = True
            thread.start()
            return '<h1>Successfully added entry</h1>'
        except Exception as e:
            print e
        return False


    # POST '/board/<element_id:int>/'
    def client_action_received(self, element_id):
        print "You receive an element"
        print "id is ", self.node_id
        try:
            # Increment logical clock because new event
            self.LC = self.LC + 1
            # Get the entry from the HTTP body
            entry = request.forms.get('entry')
            # Get option from HTTP body
            delete_option = request.forms.get('delete')
            # 0 = modify, 1 = delete
            print "the delete option is ", delete_option

            # Call either delete or modify
            if delete_option == '0':
                # Add the modify action to the queue
                self.queue[element_id]['entry'] = entry
                # Update board according to the queue
            	self.handle_queue()
                propagate_action = 'MODIFY'

            elif delete_option == '1':
                print 'Element id is: ', element_id
                # Add delete action to queue
                self.queue[element_id]['entry'] = "deleted_element"
                # Update board according to the queue
            	self.handle_queue()
                propagate_action = 'DELETE'

            else:
                raise Exception("Unaccepted delete option")

            print propagate_action

            # Create message for propagation
            msg = {'entry': entry, 'LC': self.LC, 'node_id': self.node_id, 'action': delete_option}
            # Propage to other nodes
            thread = Thread(target=self.propagate_to_nodes,
                            args=('/propagate/' + propagate_action + '/' + str(element_id), json.dumps(msg),'POST'))
            thread.daemon = True
            thread.start()
            return '<h1>Successfully ' + propagate_action + ' entry</h1>'
        except Exception as e:
            print e
        return False


    # With this function you handle requests from other nodes like add modify or delete
    # POST '/propagate/<action>/<element_id:int>'
    def propagation_received(self, action, element_id):
        
        print "The action received is: ", action

        # Get data from propagation msg
        received = json.loads(request.body.read())
        # Assign received data
        entry = received['entry']
        sending_node = received['node_id']
        RC = int(received['LC'])
        
        # Print information
        print "Message received from: " + str(sending_node) + " with entry: " + str(entry)

        # Update logical clock with max value of local clock and received clock
        self.LC = max(self.LC, RC)
        # Increment logical clock because new event
        self.LC = self.LC + 1

        # Handle requests
        if action == 'ADD':
        	# Add received entry to queue
        	self.queue.append(received)
        	# Update board acording to queue
        	self.handle_queue()

        elif action == 'MODIFY':
            # Add received modify to queue
            self.queue[element_id]['entry'] = entry
            # Update board acording to queue
            self.handle_queue()

        elif action == 'DELETE':
            # Mark received delete in queue
            self.queue[element_id]['entry'] = "deleted_element"
            # Update board acording to queue
            self.handle_queue()

    # ------------------------------------------------------------------------------------------------------
    # QUEUE OPERATIONS
    # ------------------------------------------------------------------------------------------------------
    
    # This function updates the local board according to the queue
    def handle_queue(self):
    	
        to_delete = []

        # Sort the queue by logical clock value for each entry.
        # If entries have equal logical clocl value, prioritize by node id (lowest first).
    	self.queue.sort(key=lambda k:(k['LC'], k['node_id']))
        # Print the current queue
    	print "My queue: " + json.dumps(self.queue, indent=4)
        # Add all elements in the queue to the local board
    	for i in range(len(self.queue)):
    		self.add_new_element_to_store(i, self.queue[i]['entry'])

    	# Add elements marked for deletion to a list.
    	for i in self.board:
    		if self.board[i] is "deleted_element":
    			to_delete.append(i)
    	# Print element id's that are marked for deletion
    	print "Elements marked as deleted:" + str(to_delete)
        # If there is element id's marked for deletion.
        # Delete these elements from the local board.
    	if to_delete:
    		for i in range(len(to_delete)):
    			self.delete_element_from_store(to_delete[i])

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

    # Adds a element to the local board
    def add_new_element_to_store(self, entry_sequence, element):
        success = False
        try:
            print "Adding: " + element + " with ID: " + str(entry_sequence)
            self.board[entry_sequence] = element
            success = True
        except Exception as e:
            print e
        return success
    
    # Deletes a element from the local board
    def delete_element_from_store(self, entry_sequence):
        success = False
        try:
            # If it does not exist we count it as a successful delete as well
            if entry_sequence in self.board:
                del self.board[entry_sequence]
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
    # Create queue
    queue = []
    # Init logical clock
    LC = 0
    
    # We need to write the other nodes IP, based on the knowledge of their number
    for i in range(1, args.nbv + 1):
        node_list[str(i)] = '10.1.0.{}'.format(str(i))
        
    try:
        server = Server(host=node_list[str(node_id)], port=80, node_list = node_list,
        	node_id = node_id, LC = LC, queue = queue)
        server.start()

    except Exception as e:
        print e
        traceback.print_exc() 
# ------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    main()
