# Geo-Automate

Script to automate the following Geonode layers operations:

- **Layers upload**: Upload multiple layers by providing a path to the file containing the layers files.
- **Set default Thumbnail**: Set the default thumbnail to all layers on the Geonode.
- **Remove all layers**: Remove all layers from the Geonode.

## Installation 

This script requires python3 and uses the following libraries:

- sys
- os
- pyproj
- json
- requests
- unidecode
- argparse


To install all requirements at once:

```
pip3 install -r requirements.txt
```

This script can be executed by giving execution permissions or by passing it to python3 as argument:

```
chmod +x geo_automate.py
./geo_automate.py -h
```

OR

```
python3 geo_automate.py -h
```

## Arguments 

- **`-u` or `--url`**: Domain of the geonode website (https://example.com/).
- **`-c` or `--csrf`**: CSRF token for the session of a user with layers upload/manage permissions.
- **`-s` or `--session`**: Session ID of the same session as CSRF token.
- **`-f` or `--path-to-layers`**: Path for the layers files to upload.
- **`-l`**: Flag to upload layers, path must be specified (`-f`).
- **`-t`**: Flag to set default Thumbnails on all layers on Geonode.
- **`-d`**: Flag to delete all layers on Geonode.


## Examples

### Upload layers

```
./geo_automate.py -u https://example.com/ -c 1234 -s 12 -f layers/ -l
```

### Upload layers and set thumbnails

```
./geo_automate.py -u https://example.com/ -c 1234 -s 12 -f layers/ -l -t
```

### Set thumbnails

```
./geo_automate.py -u https://example.com/ -c 1234 -s 12 -t
```

### Delete all layers

```
./geo_automate.py -u https://example.com/ -c 1234 -s 12 -d
```

## NOTE 

This script hasn't been tested yet.
