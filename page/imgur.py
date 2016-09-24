7#===============================================================================
# imgur.py - provides access to imgur's API.
# Requires a client ID for for the API to be entered into CLIENT_ID_FILE.

import traceback    
import urllib
import urllib2
import json
import ssl

CLIENT_ID_FILE = 'conf/imgur_client_id.txt'
API_URL = 'https://api.imgur.com/3'

ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)

class ImgurError(Exception): pass

def init_client_id():
    try:
        with open(CLIENT_ID_FILE) as file:
            return file.read().strip()
    except:
        traceback.print_exc()
client_id = init_client_id()

def api_request(rel_url, *args, **kwds):
    if not client_id: raise ImgurError('No client ID specified.')
    req = urllib2.Request(API_URL+rel_url, *args, **kwds)
    req.add_header('Authorization', 'Client-ID %s' % client_id)
    return req

def api_result(*args, **kwds):
    req = api_request(*args, **kwds)
    res = json.load(urllib2.urlopen(req, context=ssl_context))
    if not res['success']:
        raise ImgurError(res['data'])
    return res['data']

def image_info(id):
    return api_result('/image/%s' % id)

def album_info(id):
    return api_result('/album/%s' % id)

def upload_url(img_url):
    data = urllib.urlencode({'image':img_url})
    return api_result('/image', data=data)
