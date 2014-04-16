#===============================================================================
# imgur.py - provides access to imgur's API.
# Requires a client ID for for the API to be entered into CLIENT_ID_FILE.

import urllib2
import json

CLIENT_ID_FILE = 'conf/imgur_client_id.txt'
API_URL = 'https://api.imgur.com/3'

class ImgurError(Exception): pass

def init_client_id():
    try:
        with open(CLIENT_ID_FILE) as file:
            return file.read().strip()
    except: pass
client_id = init_client_id()

def api_request(rel_url, *args, **kwds):
    if not client_id: raise ImgurError('No client ID specified.')
    req = urllib2.Request(API_URL+rel_url, *args, **kwds)
    req.add_header('Authorization', 'Client-ID %s' % client_id)
    return req

def api_result(*args, **kwds):
    res = json.load(urllib2.urlopen(api_request(*args, **kwds)))
    if not res['success']: raise ImgurError['data']
    return res['data']

def image_info(id):
    return api_result('/image/'+id)

