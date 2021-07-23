from flask import Flask,request
import json
app = Flask(__name__)


f = open('requests.json','w')
f.write('[]')
f.close()
f = open('config.json','w')
f.write('[]')
f.close()


@app.route('/<path:temp>',methods=['POST','GET','DELETE','PUT'])
def hello_world(temp):
   req = {}
   req['path'] = temp
   try:
    req['body'] = request.json
   except:
    req['body'] = ''
   f = open('requests.json')
   json_data = json.load(f)
   f.close()
   if len(json_data) > 0:
      json_data.append(req)
      json_data = json.dumps(json_data)
   else:
      json_data = []
      json_data.append(req)
      json_data = json.dumps(json_data)
   f = open('requests.json','w')
   f.write(str(json_data))
   f.close()
   f = open('config.json','r')
   checkData = json.load(f)
   f.close()
   for i in checkData:
       if i['path'] == temp:
         return i['payload'], i['resp_code']
   return '{"status":"Successfully received"}'

@app.route('/prime',methods=['POST','GET','DELETE'])
def config():
   if request.method == 'POST':
      conf = {}
      conf['path'] = request.json['path']
      conf['resp_code'] = request.json['resp_code']
      conf['payload'] = request.json['payload']
      f = open('config.json')
      json_data = json.load(f)
      f.close()
      if len(json_data) > 0:
         json_data.append(conf)
      else:
         json_data = []
         json_data.append(conf)
      f = open('config.json','w')
      f.write(str(json.dumps(json_data)))
      f.close()
      return '{"status":"successfully saved"}'
   elif request.method == 'GET':
      f = open('config.json','r')
      data = json.load(f)
      f.close()
      data = json.dumps(data)
      return data
   elif request.method == 'DELETE':
      f = open('config.json','w')
      f.write('[]')
      f.close()
      return '{"status":"configurations deleted."}'

@app.route('/get_all_payload',methods=['GET'])
def dump_requests():
    f = open('requests.json','r')
    to_send = json.load(f)
    f.close()
    f = open('requests.json','w')
    f.write('[]')
    f.close()
    return str(to_send)

if __name__ == '__main__':
    app.run(debug = True,port=8080)
