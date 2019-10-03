"""
It is a simple torrent tracker. Simple tracker can:
    1. receive a request with compact or no_peer_id flags at /announce page
    2. store an info_hash and and its peers
    3. send a response (compact or full) for requested info_hash with peers list
    4. You can view brief status of the tracker on /status page
To run a tracker you have to call function :
    start_tracker(host='host', port=port)
Default host 127.0.0.1 default port 8080
"""

import asyncio
import jinja2
import aiohttp_jinja2

from time import monotonic
from simple_tracker import bencode
from socket import inet_aton
from struct import pack
from aiohttp import web


DEFAULT_INTERVAL = 120
STATUS_TEMPLATE = """
                    <html>
                        <head>
                            <title>{{title}}</title>
                        </head>
                        <body>
                            <div>
                                {% for hash_ in i_hashes.keys() %}
                                    <p> HASH: <strong>{{hash_}} </strong>    peers: 
                                        <strong>{{i_hashes[hash_].values()|length}} </strong></p>
                                    {% for peer in i_hashes[hash_].values() %}
                                        <p> peer id: <strong>{{peer['peer id']}}</strong> ### status: 
                                        {{peer['event']}} ### host: {{peer['ip']}}  ###  port: {{peer['port']}} </p>
                                    {% endfor %}
                                {% endfor %}
                            </div>
                        </body>
                    </html>
                """
TEMPLATES = {'status': STATUS_TEMPLATE}

hashes_table = {}


async def get_params_dict(query_url):
    params_dict = dict()
    tmp_string = str(query_url)
    query_itself = tmp_string[tmp_string.index('?') + 1:]

    for pair in query_itself.split('&'):
        key_name, key_val = pair.split('=')
        params_dict[key_name] = key_val

    return params_dict


async def add_info_hash_to_cache(i_h, params_dict, remote_ip, interval=120):
    peer_id = params_dict.get('peer_id', None)
    peer_port = params_dict.get('port', None)
    event = params_dict.get('event', None)
    uploaded = params_dict.get('uploaded', None)
    downloaded = params_dict.get('downloaded', None)
    left = params_dict.get('left', None)
    corrupt = params_dict.get('corrupt', None)

    curr_time = monotonic()

    if any([i_h, peer_id, remote_ip, peer_port]):
        peers = hashes_table.get(i_h, None)
        if peers is None:
            peers = {}
        else:
            if event is None:
                if peers.get(peer_id, None) is not None:
                    event = peers[peer_id].get('event', None)
        try:
            peers[peer_id] = {'peer id': peer_id,
                              'ip': remote_ip,
                              'port': int(peer_port),
                              'last_update': curr_time,
                              'event': event,
                              'uploaded': uploaded,
                              'downloaded': downloaded,
                              'left': left,
                              'interval': interval,
                              'corrupt': corrupt
                              }
        except Exception as e:
            return False

        hashes_table[i_h] = peers
        return True
    else:
        return False


async def create_peers_list(i_h, compact=1, no_peer_id=1):
    if compact:
        peers_string = b''
        for item in hashes_table[i_h].values():
            peer_ip = inet_aton(item.get('ip'))
            peer_port = pack('>H', item.get('port'))
            peers_string += (peer_ip + peer_port)
        return peers_string

    peers_list = []
    if no_peer_id:
        for peer_ in hashes_table[i_h].values():
            peers_list.append({'ip': peer_['ip'], 'port': peer_['port']})
    else:
        for peer_ in hashes_table[i_h].values():
            peers_list.append({'peer id': peer_['peer id'], 'ip': peer_['ip'], 'port': peer_['port']})
    return peers_list


async def announce_(request):
    interval = DEFAULT_INTERVAL
    params_dict = await get_params_dict(request.rel_url)

    i_h = params_dict.get('info_hash', None)
    compact = params_dict.get('compact', 1)
    no_peer_id = params_dict.get('no_peer_id', 0)

    response_dict = dict()

    if await add_info_hash_to_cache(i_h, params_dict, request.remote, interval):
        response_dict['interval'] = interval
        response_dict['peers'] = await create_peers_list(i_h,
                                                         compact=compact,
                                                         no_peer_id=no_peer_id)
    else:
        response_dict['failure reason'] = "Unwanted internal error or bad request"

    response = bencode.encode(response_dict)
    return web.Response(body=response, content_type='text/plain', status=200)


@aiohttp_jinja2.template('status')
async def status_(request):
    ctx = dict()
    ctx['title'] = 'Simple Tracker Status Page'
    ctx['i_hashes'] = hashes_table
    return ctx


async def cache_cleaner_task():
    try:
        while True:
            curr_time = monotonic()

            for i_h_ in list(hashes_table.keys()):

                for peer in list(hashes_table[i_h_].keys()):
                    last_update = hashes_table[i_h_][peer].get('last_update', 0)
                    interval = hashes_table[i_h_][peer].get('interval', 0)
                    if (curr_time - last_update) > interval * 2:
                        hashes_table[i_h_].pop(peer, None)

                if not hashes_table[i_h_]:
                    hashes_table.pop(i_h_)

            await asyncio.sleep(60)

    except asyncio.CancelledError:
        print('Cleaning Stopped')
    except Exception as e:
        print("Excaeption is ", e)


async def _cache_cleaner_task_starter(app):
    # app['my_task'] = app.loop.create_task(backgroud_task()) !!! deprecated
    app['cache_cleaner'] = asyncio.create_task(cache_cleaner_task())


def start_tracker(host='127.0.0.1', port=8080):

    try:
        inet_aton(host)
        if type(port) is not int:
            raise ValueError('Bad Port number')
    except Exception as e:
        print("Params Error:", repr(e))
        return -1

    try:
        # create aiohttp web application instance
        app = web.Application()
        # routes
        app.add_routes([web.get('/announce', announce_)])
        app.add_routes([web.get('/status', status_)])
        # start corutine which will care about cache within the same asyncio loop
        app.on_startup.append(_cache_cleaner_task_starter)
        # jinja2 template engine for status page
        aiohttp_jinja2.setup(app,
                             loader=jinja2.DictLoader(TEMPLATES))
        # aiohttp high level start
        web.run_app(app, host=host, port=port)
    except Exception as e:
        print("Internal Error:", e)
