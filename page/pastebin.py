#===============================================================================
# pastebin.py - a client implementation of http://pastebin.com/api

import urllib

import util

P_PUBLIC     = 0
P_UNLISTED   = 1
P_PRIVATE    = 2

E_NEVER     = 'N'
E_10MIN     = '10M'
E_1HOUR     = '1H'
E_1DAY      = '1D'
E_1WEEK     = '1W'
E_2WEEKS    = '2W'
E_1MONTH    = '1M'


def post(
    paste_code,
    dev_key         = None,
    user_key        = None,
    paste_name      = None,
    paste_format    = None,
    paste_private   = None,
    paste_expire    = None
):
    if not dev_key:
        with open('conf/pastebin_dev_key.txt') as file:
            dev_key = file.read().strip()

    data = dict()
    data['api_option'] = 'paste'
    data['api_paste_code'] = paste_code
    data['api_dev_key'] = dev_key
    if user_key: data['api_user_key'] = user_key
    if paste_name: data['api_paste_name'] = paste_name
    if paste_format: data['api_paste_format'] = paste_form
    if paste_expire: data['api_paste_expire_date'] = paste_expire

    return util.ext_urlopen(
        'http://pastebin.com/api/api_post.php',
        urllib.urlencode(data)).read()
