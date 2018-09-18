from hashlib import sha256;
import json;
from time import time;
from uuid import uuid4;
from flask import Flask, jsonify,request;
import hashlib;
#from hashlib import sha256;
import urlparse;
import requests;

class Blockchain(object):
    def __init__(self):
        self.chain=[];
        self.current_transactions=[];
        self.new_block(previous_hash=1,proof=100);
        self.nodes = set();
    def new_block(self, proof, previous_hash=None):
        """
        �����¿�
        param proof: <int> The proof given by the Proof of work algorithm
        param previous_hash: (Optional) <str> Hash of previous block
        return: <dict> New Block
        """
        block = {
            'index':len(self.chain) + 1,
            'timestamp':time(),
            'transactions':self.current_transactions,
            'proof':proof,
            'previous_hash':previous_hash or self.hash(self.chain[-1]),
        }
        self.current_transactions = [];
        self.chain.append(block);
        return block;
    def new_transaction(self, sender, recipient, amount):
        """
        �����½�����Ϣ����Ϣ�����뵽��һ�������������
        :param sender: <str> Address of the sender
        :param recipient: <str> Address of the recipient
        :param amount: <int> Amount
        :return: <int> The index of the block that will hold this transaction
        """
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,            
        })
        return self.last_block['index']+1;
    @staticmethod
    def hash(block):
        """
        ���ɿ��SHA-256 hash ֵ
        :param block: <dict> block
        :return: <str>
        """
        block_string = json.dumps(block, sort_keys=True).encode();
        return hashlib.sha256(block_string).hexdigest();

    @property
    def last_block(self):
        return self.chain[-1];
        
    def proof_of_work(self,last_proof):
        """
        �򵥵Ĺ�����֤��������p��ʹ��hash(pp`)��4��0��ͷ,p����һ�����֤����p`�ǵ�ǰ��֤��
        :param last_proof: <int>
        :return: <int>
        """
        proof = 0;
        while self.valid_proof(last_proof,proof) is False:
            proof += 1;
        return proof;
        
    @staticmethod
    def valid_proof(last_proof, proof):
        """
        ��֤֤�����Ƿ�hash(last_proof, proof)��4��0��ͷ
        """
        #guess = f'{last_proof}{proof}'.encode();
        tmp = str(last_proof) + str(proof);
        guess = tmp.encode();
        guess_hash = hashlib.sha256(guess).hexdigest();
        return guess_hash[:4] == "0000";

    def register_node(self, address):
        """
        add a new node to the list of nodes
        :param self:
        :param address: <str> address of node. eg.'http://192.168.0.1:5000'
        :return: None
        """
        parsed_url = urlparse(address);
        self.nodes.add(parsed_url.netloc);

    def valid_chain(self, chain):
        """
        Determine if a given blockchain is vilid
        :param chain: <list> A blockchain
        :return: <bool> True if valid, False if not
        """
        last_block = chain[0];
        current_index = 1;
        while current_index < len(chain):
            block = chain[current_index];
            print(str(last_block));
            print(str(block));
            print("\n--------\n");
            #check that the hash of the block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False;
            #check that the proof of work is correct
            if not self.valid_proof(last_block['proof'],block['proof']):
                return False;
            last_block = block;
            current_index += 1;
        return True;

    def resolve_conflicts(self):
        """

        :return:<boolen> True if chain being replace, otherwise False
        """
        neighbours = self.nodes;
        new_chain = None;
        #we're only looking for chains longer than ours
        max_length = len(self.chain);
        #Grab and verify the chains from all the nodes in our network
        for node in neighbours:
            response = requests.get('http://' + node + '/chain');
            if response.status_code == 200:
                length = response.json()['length'];
                chain = response.json()['chain'];
                #check if the length is longer and the chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length;
                    new_chain = chain;
        #replace our chain if we discovered a new, valid chain longer than ours
        if new_chain:
            self.chain = new_chain;
            return True;
        return False;


#Instantiate our Node
app = Flask(__name__);
#Generate a globally unique address for this code
node_identifier = str(uuid4()).replace('-','');
#Instantiate the Blockchain
blockchain = Blockchain();
@app.route('/mine',methods=['GET'])
def mine():
    #we run the proof of work algorithm to get the next proof
    last_block = blockchain.last_block;
    last_proof = last_block['proof'];
    proof = blockchain.proof_of_work(last_proof);
    #provide the prize to the proofed node
    #number 0 sender mine a new coin
    blockchain.new_transaction(
        sender = "0",
        recipient=node_identifier,
        amount=1,
    );
    block = blockchain.new_block(proof);
    response = {
        'message':"New blcok forged",
        'index':block['index'],
        'transactions':block['transactions'],
        'proof':block['proof'],
        'previous_hash':block['previous_hash'],
    }
    return jsonify(response),200;
@app.route('/transactions/new',methods=['POST'])
def new_transaction():
    values = request.get_json();
    #check that the required fields are in the post data
    required = ['sender','recipient', 'amount'];
    if not all(k in values for k in required):
        return "Missing values", 400;
    #create a new transaction
    index = blockchain.new_transaction(values['sender'],values['recipient'],values['amount']);
    response = {'message':'transaction will be added to block' + index};
    return jsonify(response),201;
@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain':blockchain.chain,
        'length':len(blockchain.chain)
    }
    return jsonify(response),200;

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json();
    nodes = values.get('nodes');
    if nodes is None:
        return "Errors: Please supply a valid list of nodes", 400;
    for node in nodes:
        blockchain.register_node(node);
    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201

#used for nodes consensus/

@app.route('/nodes/resolve',methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts();
    if replaced:
        response = {
            'message':'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message':'Our chain is authoritative',
            'chain':blockchain.chain
        }

    return jsonify(response), 200

if __name__ == '__main__':
    app.run(host='localhost', port=5002);
