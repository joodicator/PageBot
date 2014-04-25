#===============================================================================
# Provides access to YouTube's data API version 3.
# Requires https://code.google.com/p/google-api-python-client/ to be installed.
# An API key may be entered into API_KEY_FILE.

API_KEY_FILE = 'conf/youtube_api_key.txt'

import apiclient.discovery

def get_key():
    try:
        with open(API_KEY_FILE) as file:
            return file.read().strip()
    except IOError:
        return None

youtube = apiclient.discovery.build('youtube', 'v3', developerKey=get_key())
