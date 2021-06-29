#!/usr/bin/env python3
import sys;
from pyproj import Transformer;
from os import listdir;
from os.path import isfile, join;
import json;
import requests;
import unidecode;
import argparse

# Parse arguments
parser = argparse.ArgumentParser();
parser.add_argument('-l', action='store_true', help="upload layers from a file")
parser.add_argument('-t', action='store_true', help="set default thumbnails on layers")
parser.add_argument('-d', action='store_true', help="remove all layers from geonode")
parser.add_argument("-u", "--url", dest="url",help="URL of the geonode website (https://example.com")
parser.add_argument("-c", "--csrf", dest="csrf",help="CSRF token cookie")
parser.add_argument("-s", "--session", dest="session",help="Session ID cookie")
parser.add_argument("-f", "--path-to-layers", dest="layers_path",help="Path to folder with layers to be uploaded")
args = parser.parse_args();
l = args.l;
t = args.t;
d = args.d;
url = args.url;
csrf_token= args.csrf;
session_id= args.session;
layers_path = args.layers_path;

if url and csrf_token and session_id and (l or t or d):
    if url[-1] == '/':
        url = url[:-1];
else:
    print('Invalid arguments');
    sys.exit()

# request cookies
cookies = {'csrftoken': csrf_token, 'sessionid':session_id};
# request headers
headers = {'Origin': url, 'Referer': url + '/layers/upload', 'X-CSRFToken': csrf_token, 'Host': url[8:], 'Cookie': 'csrftoken=' + csrf_token + '; sessionid=' + session_id};

def build_thumbnail_body(layer_name, json_layer):
    layer_info = json_layer["featureType"];
    bbox_4326 = layer_info["nativeBoundingBox"];

    type_espg = bbox_4326["crs"];
    if isinstance(type_espg, dict):
        type_espg = type_espg["$"].lower();
        transformer = Transformer.from_crs(type_espg, "epsg:4326");
        # parse min values (x and y) to 3857
        bbox_4326["minx"], bbox_4326["miny"] = transformer.transform(bbox_4326["miny"], bbox_4326["minx"]);
        bbox_4326["maxx"], bbox_4326["maxy"] = transformer.transform(bbox_4326["maxy"], bbox_4326["maxx"]);
        # parse max values (x and y) to 3857

    # parser for espg:4326 to espg:3857 
    transformer = Transformer.from_crs("espg:4326", "epsg:3857");

    # parse min values (x and y) to 3857
    minx, miny = bbox_4326["minx"], bbox_4326["miny"];
    minx, miny = transformer.transform(miny, minx);

    # parse max values (x and y) to 3857
    maxx, maxy= bbox_4326["maxx"], bbox_4326["maxy"];
    maxx, maxy= transformer.transform(maxy, maxx);

    # define a bbox keeping ration
    # TODO fix
    bbox = [minx + 120, maxx - 120, miny + 64, maxy - 64];

    # get center values 
    center_x = (bbox_4326["minx"] + bbox_4326["maxx"])/2.0;
    center_y = (bbox_4326["miny"] + bbox_4326["maxy"])/2.0;

    payload= {};

    # fill payload for the thumbnail request body
    payload["bbox"] = bbox;
    payload["center"] = {"crs": "espg:4326", "x": center_x, "y": center_y};
    payload["height"] = 400;
    payload["layers"] = layer_name;
    payload["srid"] = "EPSG:3857";
    payload["width"] = 750;
    payload["zoom"] = 19;

    return payload;

def upload_request(request, pid):
    # SRS request
    req = requests.Request(
        'GET', 
        url + '/upload/' + request + '?id=' + str(pid),
        cookies = cookies,
        headers={'Referer': url + '/layers/upload', 'Host': url[8:]}
    ).prepare();

    s = requests.Session()
    r = s.send(req);

    # print response
    print('\n\033[94m[!]\033[0m '+ request.upper() + ' REQUEST:');

    return r;

def upload_layers(thumbnails, headers, cookies): 
    # shape files extensions
    shp_extensions = ['qpj', 'cpg', 'cst', 'dbf', 'prj', 'shp', 'shx', 'xml'];

    # grab all files without extension within the folder given
    layers = [f.split('.')[0] for f in listdir(layers_path) if isfile(join(layers_path, f))];

    # remove duplicates
    layers = list(set(layers));

    layers_len = len(layers);
    print('\033[94m[!]\033[0m Number of layers to upload: ', layers_len);
    errors = [];
    i = 0;

    #foreach layer
    for layer in layers:
        try: 
            files = {};
            # fill default permissions
            files["permissions"] = (None, '{"users":{"AnonymousUser":["view_resourcebase","download_resourcebase"]},"groups":{}}'); 
            # charset required parameter, empty by default
            files["charset"] = (None, ''); 

            print('\n\n===================== ' + layer + ' =====================\n');
            # go through all shape files extensions
            for e in shp_extensions: 
                # concatenate layer name with each extension
                file_name = layers_path + '/' + layer + '.' + e;
                # if it exists fill the parameters for the request
                if isfile(file_name):
                    # if shp extension, then geonode requires a base_file parameter with its content too
                    if e == 'shp':
                        files["base_file"] = (unidecode.unidecode(layer) + '.' + e, open(file_name, 'rb'));
                    # each file extension is a separate parameter 
                    files[e + "_file"] = (unidecode.unidecode(layer) + '.' + e , open(file_name, 'rb'));

            # prepare the upload request 
            req = requests.Request('POST', url + '/upload/' , files = files, cookies = cookies, headers=headers).prepare();

            # send upload request
            s = requests.Session()
            r = s.send(req);

            print(r.text);
            # check if it was successful
            print('\n\033[92m[+]\033[0m UPLOAD REQUEST:');

            # get pid of upload process
            pid = json.loads(r.text)["id"];
            print('\033[94m[+]\033[0m Process ID: ', pid);

            # SRS request
            upload_request("srs", pid);
            # check request 
            upload_request("check", pid);
            # progress request
            upload_request("progress", pid);
            # print final request
            r = upload_request("final", pid);
            geonode_layer = json.loads(r.text)["url"].split("geonode_data:")[1];
            geonode_layer_name = geonode_layer.split("geonode:")[1]

            success = False;
            max_requests = 9;
            n_requests = 1;

            # progress request sequence, geonode normally does it more than 9 times even if the response status is COMPLETE, but its not required
            while not success: 
                # progress request
                r = upload_request("progress", pid, 'COMPLETE');
                # if success and response status is COMPLETE or NONE end sequence
                if 'NONE' in r.text or 'COMPLETE' in r.text:
                    success = True;
                if n_requests == max_requests: 
                    success=True
                n_requests+= 1;

            
            req = requests.Request('GET', url + '/geoserver/rest/layers/' + geonode_layer_name).prepare();

            s = requests.Session();
            r = s.send(req);
            if 'No such layer' in r.text:
                print('\033[91m[-]\033[0m Upload failed on: ' + layer);
                errors.append(layer);
            else: 
                i+=1;
                # print upload status
                print('\n\033[92m[+]\033[0m Layer ' + layer + ' uploaded successfuly ' + str(i) + '/' + str(layers_len));

            if thumbnails: 
                try: 
                    print('\033[94m[!]\033[0m Setting thumbnail for layer ' + layer);
                    headers = {'Origin': url, 'Referer': url + '/layers/' + geonode_layer_name + ':' + geonode_layer, 'X-CSRFToken': csrf_token, 'Host': url[8:]};
                    req = requests.Request('GET', url + '/geoserver/rest/workspaces/geonode/datastores/geonode_data/featuretypes/' + geonode_layer_name + '.json?access_token=bBnzSPHvTdmyGRsqPjrRdvSDx7BPwQ').prepare();

                    s = requests.Session();
                    r = s.send(req);

                    json_layer = json.loads(r.text);

                    if "featureType" in json_layer: 
                        payload = build_thumbnail_body(geonode_layer, json_layer);

                        req = requests.Request('POST', url + '/layers/' + geonode_layer + '/thumbnail', cookies=cookies, headers=headers, data=json.dumps(payload)).prepare();

                        s = requests.Session();
                        r = s.send(req);
                        if 'saved' in r.text:
                            print('\033[92m[+]\033[0m Thumbnail successfully set for ' +  geonode_layer_name + ' ' + r.text);
                        else:
                            print('\033[91m[-]\033[0m Thumbnail set failed for ' +  geonode_layer_name + ' ' + r.text);
                except: 
                    if sys.exc_info()[0] != KeyboardInterrupt:
                        print('\n\033[91m[-]\033[0m Error on setting thumbnail on ' + layer_name + ', reason: ' + str(sys.exc_info()[0]));
                        print('\033[94m[!]\033[0m: ' +  r.text + '\n');
                    else: 
                        sys.exit()

        except: 
            # to avoid CTRL-C problems
            if sys.exc_info()[0] != KeyboardInterrupt:
                print(sys.exc_info()[0]);
                print('\033[91m[-]\033[0m Error on: ' + layer);
                errors.append(layer);
            else: 
                sys.exit()

    print('\n\033[92m[+]\033[0m Layers upload finished');
    # print layers with error 
    print('\n\033[92m[!]\033[0m Layers with error: ', errors);

def remove_all_layers(): 
    # get all layers from geonode
    req = requests.Request('GET', url + '/geoserver/rest/layers').prepare();
    s = requests.Session();
    r = s.send(req);
    layers = json.loads(r.text)["layers"];

    print('\033[94m[!]\033[0m Number of layers to remove: ', len(layers["layer"]));

    # foreach layer
    for layer in layers["layer"]:
        layer_name = layer["name"];
        
        try: 
            # remove layer request
            headers = {'Origin': url, 'Referer': url + '/layers/geonode_data:' + layer_name, 'X-CSRFToken': csrf_token, 'Host': url[8:]};
            req = requests.Request('POST', url + '/layers/' + layer_name + '/remove', cookies=cookies, headers=headers).prepare();
            s = requests.Session();
            r = s.send(req);
            
            # print response
            if '200' in str(r): 
                print('\n\033[92m[+]\033[0m layer ' + layer_name[8:] + ' removed successfully');
            else:
                print('\033[91m[-]\033[0m ' +  layer_name[8:] + ' ' + r.text);
        except: 
            if sys.exc_info()[0] != KeyboardInterrupt:
                print('\n\033[91m[-]\033[0m Error on: ' + layer_name + ', reason: ' + str(sys.exc_info()[0]));
                print('\033[94m[!]\033[0m: ' +  r.text + '\n');
            else: 
                sys.exit()

def set_thumbnails(): 
    req = requests.Request('GET', url + '/geoserver/rest/layers').prepare();

    s = requests.Session();
    r = s.send(req);

    layers = json.loads(r.text)["layers"];

    print('\033[94m[!]\033[0m Number of layers to apply thumbnail: ', len(layers["layer"]));

    for layer in layers["layer"]:
        layer_name = layer["name"];
        headers = {'Origin': url, 'Referer': url + '/layers/' + layer_name[8:] + ':' + layer_name, 'X-CSRFToken': csrf_token, 'Host': url[8:]};
        req = requests.Request('GET', url + '/geoserver/rest/workspaces/geonode/datastores/geonode_data/featuretypes/' + layer_name[8:] + '.json?access_token=bBnzSPHvTdmyGRsqPjrRdvSDx7BPwQ').prepare();

        s = requests.Session();
        r = s.send(req);
        json_layer = json.loads(r.text);

        if "featureType" in json_layer: 
            payload = build_thumbnail_body(layer_name, json_layer);
            req = requests.Request('POST', url + '/layers/' + layer_name + '/thumbnail', cookies=cookies, headers=headers, data=json.dumps(payload)).prepare();

            s = requests.Session();
            r = s.send(req);
            if 'saved' in r.text:
                print('\033[92m[+]\033[0m ' +  layer_name[8:] + ' ' + r.text);
            else:
                print('\033[91m[-]\033[0m ' +  layer_name[8:] + ' ' + r.text);

if l and layers_path:
    upload_layers(t, headers, cookies);
if t and not l:
    set_thumbnails();
if d and not l and not t():
    i = input('\n\033[91m[!]\033[0m Are you sure you want to remove all layers? (y|n):'); 
    if i == 'y': 
        remove_all_layers();
