"""Compare game data, independently of SQLite layout and import timestamps."""
import hashlib
import json
import sqlite3
from contextlib import closing

def fingerprint(path):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)) as db:
        result = {}
        for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='metadata' ORDER BY name"):
            quoted = '"'+name.replace('"','""')+'"'
            columns = [list(row) for row in db.execute('PRAGMA table_info('+quoted+')')]
            order = ','.join(str(i+1) for i in range(len(columns)))
            digest = hashlib.sha256()
            count = 0
            for row in db.execute('SELECT * FROM '+quoted+' ORDER BY '+order):
                digest.update(json.dumps(row,ensure_ascii=False,separators=(',',':')).encode('utf-8')+b'\n')
                count += 1
            result[name] = {'columns':columns,'count':count,'sha256':digest.hexdigest()}
        return result

def verify(path, reference):
    if fingerprint(path) != reference['tables']:
        raise ValueError('Les données reconstruites diffèrent de la base de référence. Installation annulée.')
