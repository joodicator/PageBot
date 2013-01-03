event_count = 0

def get_event():
    global event_count

    event_count = event_count + 1
    return event_count

READ   = get_event()
WRITE  = get_event()
EXC    = get_event()
CLOSE  = get_event()
ACCEPT = get_event()
FOUND  = get_event()
DATA   = get_event()
LOAD   = get_event()
DATA   = get_event()
BUFFER = get_event()
DUMPED = get_event()
RECV_ERR = get_event()
SEND_ERR = get_event()

__all__ = [
            'get_event',
            'READ', 
            'WRITE',
            'EXC', 
            'CLOSE',
            'FOUND',
            'LOAD', 
            'BUFFER', 
            'DATA',
            'CLOSE',
            'RECV_ERR',
            'SEND_ERR',
            'ACCEPT',
            'DUMPED'
          ]


