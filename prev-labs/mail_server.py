from typing import Dict, List, Optional
from flask import Flask, request, jsonify
import pathlib
import uuid
import json


app = Flask(__name__)
thisdir = pathlib.Path(__file__).parent.absolute() # path to directory of this file

# Function to load and save the mail to/from the json file

def load_mail() -> List[Dict[str, str]]:
    """
    Loads the mail from the json file

    Returns:
        list: A list of dictionaries representing the mail entries
    """
    try:
        return json.loads(thisdir.joinpath('mail_db.json').read_text())
    except FileNotFoundError:
        return []

def save_mail(mail: List[Dict[str, str]]) -> None:
    """TODO: fill out this docstring (using the load_mail docstring as a guide)
    Saves (writes) mail from the mail list into the json file

    Parameters:
        mail: List of dictionaries representing the mail entries

    Returns: None
    """
    thisdir.joinpath('mail_db.json').write_text(json.dumps(mail, indent=4))

def add_mail(mail_entry: Dict[str, str]) -> str:
    """TODO: fill out this docstring (using the load_mail docstring as a guide)
    Adds new mail to the mail list and the json file

    Parameters:
        mail_list: Dictionary representing a mail entry

    return:
        str: contains the unique id of the mail entry
    """
    mail = load_mail()
    mail.append(mail_entry)
    mail_entry['id'] = str(uuid.uuid4()) # generate a unique id for the mail entry
    save_mail(mail)
    return mail_entry['id']

def delete_mail(mail_id: str) -> bool:
    """TODO: fill out this docstring (using the load_mail docstring as a guide)
    Deletes mail from the mails list and json file according to the unique mail id

    Parameters: 
        mail_id: string representing the unique id of a mail

    Returns:
        bool: True if mail successfully found and deleted, False otherwise
    """
    mail = load_mail()
    for i, entry in enumerate(mail):
        if entry['id'] == mail_id:
            mail.pop(i)
            save_mail(mail)
            return True

    return False

def get_mail(mail_id: str) -> Optional[Dict[str, str]]:
    """TODO: fill out this docstring (using the load_mail docstring as a guide)
    Gets mail from the database accordign to the unique mail id

    Parameters:
        mail_id: string representing the unique id of a mail
    
    Returns:
        dict: mail entry that mail_id represents, None if nothing is found
    """
    mail = load_mail()
    for entry in mail:
        if entry['id'] == mail_id:
            return entry

    return None

def get_inbox(recipient: str) -> List[Dict[str, str]]:
    """TODO: fill out this docstring (using the load_mail docstring as a guide)
    Get all mail that was sent to the recipient name provided

    Parameters:
        recipient: string representing the name of the recipient whose inbox we want to extract
    
    Return:
        list: a list of dicts representing each email sent to recipient is returned
    """
    mail = load_mail()
    inbox = []
    for entry in mail:
        if entry['recipient'] == recipient:
            inbox.append(entry)

    return inbox

def get_sent(sender: str) -> List[Dict[str, str]]:
    """TODO: fill out this docstring (using the load_mail docstring as a guide)
    Get all mail that was sent from the sender name provided

    Parameters:
        sender: string representing the name of the sender whose 'sent' box we want to extract
    
    Return:
        list: a list of dicts representing each email sent from sender is returned
    """
    mail = load_mail()
    sent = []
    for entry in mail:
        if entry['sender'] == sender:
            sent.append(entry)

    return sent

# API routes - these are the endpoints that the client can use to interact with the server
@app.route('/mail', methods=['POST'])
def add_mail_route():
    """
    Summary: Adds a new mail entry to the json file

    Returns:
        str: The id of the new mail entry
    """
    mail_entry = request.get_json()
    mail_id = add_mail(mail_entry)
    res = jsonify({'id': mail_id})
    res.status_code = 201 # Status code for "created"
    return res

@app.route('/mail/<mail_id>', methods=['DELETE'])
def delete_mail_route(mail_id: str):
    """
    Summary: Deletes a mail entry from the json file

    Args:
        mail_id (str): The id of the mail entry to delete

    Returns:
        bool: True if the mail was deleted, False otherwise
    """
    # TODO: implement this function
    res = jsonify(delete_mail(mail_id))
    res.status_code = 200
    return res

@app.route('/mail/<mail_id>', methods=['GET'])
def get_mail_route(mail_id: str):
    """
    Summary: Gets a mail entry from the json file

    Args:
        mail_id (str): The id of the mail entry to get

    Returns:
        dict: A dictionary representing the mail entry if it exists, None otherwise
    """
    res = jsonify(get_mail(mail_id))
    res.status_code = 200 # Status code for "ok"
    return res

@app.route('/mail/inbox/<recipient>', methods=['GET'])
def get_inbox_route(recipient: str):
    """
    Summary: Gets all mail entries for a recipient from the json file

    Args:
        recipient (str): The recipient of the mail

    Returns:
        list: A list of dictionaries representing the mail entries
    """
    res = jsonify(get_inbox(recipient))
    res.status_code = 200
    return res

# TODO: implement a rout e to get all mail entries for a sender
# HINT: start with soemthing like this:
#   @app.route('/mail/sent/<sender>', ...)

@app.route('/mail/sent/<sender>', methods=['GET'])
def get_sent_route(sender: str):
    res = jsonify(get_sent(sender))
    res.status_code = 200
    return res



if __name__ == '__main__':
    app.run(port=5000, debug=True)