#!/opt/rh/rh-python36/root/usr/bin/python
 
 
import ssl
import sys
import asyncio
import json
import logging
from quart import Quart,request,Response,session
from queue import Queue
from prometheus_client import start_http_server, Summary
from prometheus_client import Counter
from prometheus_client import Gauge
import argparse
import time
 
 
app_with_storage = Quart("Store")
app_no_storage = Quart("No_Store")
MAXSIZE = 500
q = asyncio.Queue(maxsize=MAXSIZE)
response_q = asyncio.PriorityQueue(maxsize=MAXSIZE)
response_config = []
c = Counter('message_received','HTTP Messages Received')
count_status = Counter('http_requests_total','HTTP Messages Received with partitioned by Status Code Method and URI Path',['code', 'method'])
@app_with_storage.route('/',defaults={'path':''})
@app_with_storage.route('/<path:path>',methods=['GET','PUT','POST','DELETE','PATCH'])
async def index_store(path):
    c.inc()
    global response_config
    global response_q
    if 'prime' in path:
        if request.method == 'DELETE':
            response_config = []
            data = {'status':'cleanup done'}
            js = json.dumps(data)
            resp = Response(js,status=200)
            return resp
        else:
            data = await request.get_data()
            try:
                l = json.loads(data)
            except:
                data = {'status':'bad message'}
                js = json.dumps(data)
                resp = Response(js,status=400)
                return resp
            for i in ['path','method','payload']:
                if i not in l.keys():
                    data = {'status':'bad message'}
                    js = json.dumps(data)
                    resp = Response(js,status=400)
                    return resp
            l = json.loads(data)
            config_exists = False
            index = 0
            print("Response Config")
            print(response_config)
            for i in response_config:
                print(i)
                i_config_json = json.loads(i)
                if l['path'] == i_config_json['path'] and l['method'] == i_config_json['method']:
                    print("Configuration for same path and method exists")
                    config_exists = True
                    l_payload = l['payload']
                    status_code = l['status_code']
                    response_q = asyncio.PriorityQueue(maxsize=MAXSIZE)
                    if 'response_q' in i_config_json.keys():
                        print("Response_q present in existing configuration")
                        response_q_list = i_config_json['response_q']
                        print(response_q_list)
                        for x in response_q_list:
                            item = tuple(x)
                            response_q.put_nowait(item)
                        print(response_q)
                    if type(l_payload) is dict:
                      if (all(x in l_payload.keys() for x in ['response_priority','response_count','response_body'])):
                        print("Updating data for response config")
                        response_priority =  l_payload['response_priority']
                        response_count =  l_payload['response_count']
                        response_body = l_payload['response_body']
                        if 'query_params' in l.keys():
                         item =(response_priority,response_body,status_code,l['query_params'])
                        else:
                         item =(response_priority,response_body,status_code)
                        for i in range(response_count):
                            response_q.put_nowait(item)
                        l['response_q'] = response_q._queue
                        data = json.dumps(l)
                        print("Updated data")
                        print(data)
                        response_config.pop(index)
                        print("Removed old response config")
                        print(response_config)
                        break
                index+=1
                
            if(not config_exists):
                print("Config does not already exist")
                l_payload = l['payload']
                status_code = l['status_code']
                response_q = asyncio.PriorityQueue(maxsize=MAXSIZE)
                if type(l_payload) is dict:
                  if (all(x in l_payload.keys() for x in ['response_priority','response_count','response_body'])):
                    response_priority =  l_payload['response_priority']
                    response_count =  l_payload['response_count']
                    response_body = l_payload['response_body']
                    if 'query_params' in l.keys():
                         item =(response_priority,response_body,status_code,l['query_params'])
                    else:
                         item =(response_priority,response_body,status_code)
                    for i in range(response_count):
                        response_q.put_nowait(item)
                    l['response_q'] = response_q._queue
                    data = json.dumps(l)
                    print("Updated data")
                    print(data)

            #session['counter_gen'] = ''
            print("Appending new config in response_config")
            response_config.append(data)
            data = {'status':'prime successful'}
            js = json.dumps(data)
            resp = Response(js,status=200)
            return resp
    if 'get_all_payload' in path:
        if request.method == 'GET':
            data_to_send = []
            while not q.empty():
                data = await q.get()
                data_to_send.append(data)
            print("sending data")
            print(data_to_send)
            return Response(json.dumps(data_to_send),200,mimetype="application/json")
    if request.method in ['PUT','POST','GET','DELETE','PATCH']:
        storeInQueue=True
        data = await request.get_data()
        try:
            payload = json.loads(data)
        except:
            payload = ''
        header_dict = dict(request.headers)
        header_dict = {k.lower():v for k,v in header_dict.items()}
        query_params = {}
        for i in request.args.keys():
            query_params[i] = request.args.get(i)
        request_info = {'headers': header_dict,
                         'path': path,
                         'payload': payload,
                         'query_params' : query_params
                       }

        try:
            if not q.full():
                storeInQueue = True
                data = {'status':'saved'}
                status = 200
            else:
                status = 200
        except:
            count_status.labels('200',request.method).inc()
            resp = Response(json.dumps({'status':'queue full'}),status=200)
            return resp
        index = 0
        print("Response configuration")
        print(response_config)
        for i in response_config:
            print(i) 
            i_json = json.loads(i)
            if path == i_json['path'] and request.method == i_json['method']:
             if 'query_params' in i_json.keys():
              matching = True
              for i in i_json['query_params'].keys():
                 if i not in query_params.keys() or query_params[i] != i_json['query_params'][i]:
                    matching = False
              if matching:
                if "storeInQueue" in i_json.keys():
                  if i_json["storeInQueue"] == "false":
                   storeInQueue = False
                if i_json['payload'] is not None:
                    if 'response_q' in i_json.keys():
                        response_q = asyncio.PriorityQueue(maxsize=MAXSIZE)
                        for x in (i_json['response_q']):
                            response_q.put_nowait(tuple(x))
                        print("Fetched response_q")
                        print(response_q)
                        if response_q.qsize()==0:
                            matched_data = json.dumps(i_json['payload']['response_body'])
                            status_code = i_json['status_code']
                        else:
                            response = response_q.get_nowait()
                            matched_data = json.dumps(response[1])
                            status_code = response[2]
                            response_config.pop(index)
                            print("Response config after popping old data")
                            print(response_config)
                            i_json['response_q'] = response_q._queue
                            data = json.dumps(i_json)
                            print(data)
                            response_config.append(data)
                            print("Response config after updating data")
                            print(response_config)
                    else:
                        matched_data = json.dumps(i_json['payload'])
                        status_code = i_json['status_code']
                else:
                    matched_data = None
                    status_code = i_json['status_code']
                if 'headers' in i_json.keys():
                    headers = i_json['headers']
                    if 'response-delay' in headers.keys():
                        delay_time = int(headers.get('response-delay'))
                        time.sleep(delay_time)
                    if int(status_code) == 204:
                        headers['Content-Length'] = 0
                    count_status.labels(str(status_code),request.method).inc()
                    print('headers'+str(headers))
                    if 'Content-Type' in headers.keys():
                       mimetype = headers['Content-Type']
                       if headers['Content-Type'] == 'text/html':
                         matched_data = ''.join(e for e in matched_data if e.isalnum())
                    else:
                       mimetype = "application/json"
                    if matched_data is not None:
                      if int(status_code) == 204:
                        resp = Response('',status=int(status_code),mimetype=mimetype,headers=headers)
                        print("resp"+str(resp))
                      else:
                        resp = Response(matched_data,status=int(status_code),mimetype=mimetype,headers=headers)
                    else:
                        resp = Response('',status=int(status_code),mimetype=mimetype,headers=headers)
                else:
                    count_status.labels(str(status_code),request.method).inc()
                    if matched_data is not None:
                        resp = Response(matched_data,status=int(status_code),mimetype="application/json")
                    else:
                        resp = Response('',status=int(status_code),mimetype="application/json")
                if storeInQueue:
                   q.put_nowait(request_info)
                return resp
        index+=1
    js = json.dumps(data)
    count_status.labels("200",request.method).inc()
    resp = Response(js,status=status)
    if storeInQueue:
       q.put_nowait(request_info)
    return resp

 
@app_no_storage.route('/',defaults={'path':''})
@app_no_storage.route('/<path:path>',methods=['GET','PUT','POST','DELETE','PATCH'])
async def index(path):
    c.inc()
    global response_config
    global response_q
    if 'prime' in path:
        if request.method == 'DELETE':
            response_config = []
            data = {'status':'cleanup done'}
            js = json.dumps(data)
            resp = Response(js,status=200)
            return resp
        else:
            data = await request.get_data()
            try:
                l = json.loads(data)
            except:
                data = {'status':'bad message'}
                js = json.dumps(data)
                resp = Response(js,status=400)
                return resp
            for i in ['path','method','payload']:
                if i not in l.keys():
                    data = {'status':'bad message'}
                    js = json.dumps(data)
                    resp = Response(js,status=400)
                    return resp
            l = json.loads(data)
            config_exists = False
            index = 0
            print("Response Config")
            print(response_config)
            for i in response_config:
                print(i)
                i_config_json = json.loads(i)
                if l['path'] == i_config_json['path'] and l['method'] == i_config_json['method']:
                    print("Configuration for same path and method exists")
                    config_exists = True
                    l_payload = l['payload']
                    status_code = l['status_code']
                    response_q = asyncio.PriorityQueue(maxsize=MAXSIZE)
                    if 'response_q' in i_config_json.keys():
                        print("Response_q exists")
                        response_q_list = i_config_json['response_q']
                        print(response_q_list)
                        for x in response_q_list:
                            item = tuple(x)
                            response_q.put_nowait(item)
                        print(response_q)
                    if (all(x in l_payload.keys() for x in ['response_priority','response_count','response_body'])):
                        print("Updating data for response config")
                        response_priority =  l_payload['response_priority']
                        response_count =  l_payload['response_count']
                        response_body = l_payload['response_body']
                        item =(response_priority,response_body,status_code)
                        for i in range(response_count):
                            response_q.put_nowait(item)
                        l['response_q'] = response_q._queue
                        data = json.dumps(l)
                        print(data)
                        response_config.pop(index)
                        print("Removed old config from list")
                        print(response_config)
                        break
                index+=1
                        
            if(not config_exists):
                print("Config not present")
                l_payload = l['payload']
                status_code = l['status_code']
                response_q = asyncio.PriorityQueue(maxsize=MAXSIZE)
                if (all(x in l_payload.keys() for x in ['response_priority','response_count','response_body'])):
                    response_priority =  l_payload['response_priority']
                    response_count =  l_payload['response_count']
                    response_body = l_payload['response_body']
                    item =(response_priority,response_body,status_code)
                    for i in range(response_count):
                        response_q.put_nowait(item)
                    l['response_q'] = response_q._queue
                    data = json.dumps(l)
                    
            response_config.append(data)
            data = {'status':'prime successful'}
            js = json.dumps(data)
            resp = Response(js,status=200)
            return resp
    if request.method in ['PUT','POST','GET','DELETE','PATCH']:
        data = await request.get_data()
        if 'get_all_payload' in path:
            print("This is wrong")
        index = 0
        print(response_config)
        for i in response_config:
            print(i)
            i_json = json.loads(i)
            if path == i_json['path'] and request.method == i_json['method']:
                if 'response_q' in i_json.keys():
                    response_q = asyncio.PriorityQueue(maxsize=MAXSIZE)
                    for x in (i_json['response_q']):
                        response_q.put_nowait(tuple(x))
                    if response_q.qsize()==0:
                        matched_data = json.dumps(i_json['payload']['response_body'])
                        status_code = i_json['status_code']
                    else:
                        response = response_q.get_nowait()
                        matched_data = json.dumps(response[1])
                        status_code = response[2]
                        response_config.pop(index)
                        i_json['response_q'] = response_q._queue
                        data = json.dumps(i_json)
                        print(data)
                        response_config.append(data)
                else:
                    matched_data = json.dumps(i_json['payload'])
                    status_code = i_json['status_code']
                if 'headers' in i_json.keys():
                    headers = i_json['headers']
                    if 'response-delay' in headers.keys():
                        delay_time = int(headers.get('response-delay'))
                        time.sleep(delay_time)
                    if int(status_code) == 204:
                       headers['Content-Length'] = 0
                    count_status.labels(str(status_code),request.method).inc()
                    resp = Response(matched_data,status=int(status_code),mimetype="application/json",headers=headers)
                else:
                    count_status.labels(str(status_code),request.method).inc()
                    resp = Response(matched_data,status=int(status_code),mimetype="application/json")
                return resp
            index+=1
    data = {'status':'done'}
    js = json.dumps(data)
    resp = Response(js,status=200)
    return resp
            
 
"""
if __name__ == '__main__':
    #Disabling HTTPS as it is not supported yet"
    ssl_context = ssl.create_default_context(
        ssl.Purpose.CLIENT_AUTH,
    )
    ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
    ssl_context.set_ciphers('ECDHE+AESGCM')
    ssl_context.load_cert_chain(
        certfile='/src/domain.crt', keyfile='/src/domain.key',
    )
    ssl_context.set_alpn_protocols(['h2'])
    #app.run(host='127.0.0.1', port=80, ssl=ssl_context)
    start_http_server(8000)
    if len(sys.argv) > 1:
        if sys.argv[1] == 'store':
            app_with_storage.run(host='0.0.0.0', port=80)
            sys.exit(1)
    app_no_storage.run(host='0.0.0.0', port=80)
"""
 
 
if __name__ == '__main__':
    #Disabling HTTPS as it is not supported yet"
    ssl_context = ssl.create_default_context(
        ssl.Purpose.CLIENT_AUTH,
    )
    ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
    ssl_context.set_ciphers('ECDHE+AESGCM')
    ssl_context.load_cert_chain(
        certfile='/src/domain.crt', keyfile='/src/domain.key',
    )
    ssl_context.set_alpn_protocols(['h2'])
    #app.run(host='127.0.0.1', port=80, ssl=ssl_context)
    start_http_server(8000)
    if 'IPV6_SUPPORT' in os.environ.keys():
        hostName='::'
    else:
        hostName='0.0.0.0'
    if len(sys.argv) > 1:
        if sys.argv[1] == 'store':
            app_with_storage.run(host=hostName, port=8080)
            sys.exit(1)
    app_no_storage.run(host=hostName, port=8080)
