7#===============================================================================
# imgur.py - provides access to imgur's API.
# Requires a client ID for for the API to be entered into CLIENT_ID_FILE.

import traceback    
import urllib
import urllib2
import json
import ssl

import util

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

def api_request(rel_url, **req_kwds):
    if not client_id: raise ImgurError('No client ID specified.')
    req = urllib2.Request(API_URL + rel_url, **req_kwds)
    req.add_header('Authorization', 'Client-ID %s' % client_id)
    return req

def api_result(rel_url, opener=None, **req_kwds):
    req = api_request(rel_url, **req_kwds)
    open = util.ext_urlopen if opener is None else opener.open
    res = json.load(open(req, context=ssl_context))
    if not res['success']:
        raise ImgurError(res['data'])
    return res['data']

def image_info(id, **kwds):
    return api_result('/image/%s' % id, **kwds)

def album_info(id, **kwds):
    return api_result('/album/%s' % id, **kwds)

def gallery_info(id, **kwds):
    return api_result('/gallery/%s' % id, **kwds)

def gallery_image_info(id, **kwds):
    return api_result('/gallery/image/%s' % id, **kwds)

def gallery_album_info(id, **kwds):
    return api_result('/gallery/album/%s' % id, **kwds)

def upload_url(img_url, **kwds):
    data = urllib.urlencode({'image':img_url, 'type':'URL'})
    return api_result('/image', data=data, **kwds)
