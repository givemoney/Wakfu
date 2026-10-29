"""Independent rendering of reference-client BN/eUj/eVE formatting rules."""
import json
import math
import re
import struct

CONDITION=re.compile(r'\{((?:\[[^\[\]{}?:]*\])+)[ \t]*\?([^{}]*):([^{}]*)\}')
TEST=re.compile(r'\[([0-9]*)([~+\-><=!])([0-9]+)\]')
NUMBER=re.compile(r'\[(,?)([#£])([0-9]+)(?:\.([0-9]+))?\]')
ELEMENTS={0:'Neutre',1:'Feu',2:'Eau',3:'Terre',4:'Air',6:'Lumière'}

def f32(value):return struct.unpack('f',struct.pack('f',value))[0]

def values(params,level):
    result=[]
    for index in range(0,len(params)-1,2):
        slope=f32(params[index+1]);delta=f32(slope*f32(level))
        nearest=math.floor(delta+.5)
        if abs(delta-nearest)<1e-5:delta=nearest
        value=f32(f32(params[index])+delta)
        result.append((math.floor(value) if slope>=0 else math.ceil(value),value))
    return result

def render_template(template,args):
    def test(match):
        left,op,right=match.groups();index=int(right)-1
        if index<0:return False
        if op in '~!+-':
            exists=index<len(args) and args[index] is not None
            value=args[index][0] if exists else 0
            return {'~':exists and value not in (0,''),'!':not exists or value in (0,''),'+':exists and isinstance(value,(int,float)) and value>0,'-':exists and isinstance(value,(int,float)) and value<=0}[op]
        if index>=len(args):return True
        value=args[index][0];constant=int(left or 1)
        if not isinstance(value,(int,float)):return False
        value=math.ceil(value)
        return {'>':value>constant,'<':value<constant,'=':value==constant}[op]
    def conditional(match):
        checks=list(TEST.finditer(match[1]))
        return match[2] if checks and all(test(m) for m in checks) else match[3]
    for _ in range(40):
        updated=CONDITION.sub(conditional,template)
        if updated==template:break
        template=updated
    def number(match):
        index=int(match[3])-1
        if index>=len(args):return match[0]
        integer,raw=args[index];precision=int(match[4] or 0)
        value=raw if precision else integer
        if isinstance(value,str):return value
        if match[2]=='£':value=abs(value)
        return (f'{value:.{precision}f}' if precision else str(value)).replace('.',',')
    text=NUMBER.sub(number,template)
    text=re.sub(r'\[#charac[^\]]*\]','',text)
    text=re.sub(r'\[el([0-9])\]',lambda m:ELEMENTS.get(int(m[1]),'Élément '+m[1]),text)
    return re.sub(r'\s+',' ',text).strip()

def formatted_effects(db,effects,level):
    output=[]
    for effect in effects:
        payload=json.loads(effect['payload']);params=payload.get('params',[]);args=values(params,level or 0)
        template=effect.get('description') or '';action=effect['action_id']
        if action==304 and args:
            title=db.execute("SELECT text FROM translations WHERE entity IN ('states','client_states') AND entity_id=? AND language='fr' AND field='title' LIMIT 1",(args[0][0],)).fetchone()
            if title:args[0]=(title[0],title[0])
        text=render_template(template,args)
        if not text or re.search(r'\[[^\]]+\]|[{}]',text):
            row=db.execute('SELECT effect FROM actions WHERE id=?',(action,)).fetchone()
            label=row[0] if row else 'Effet '+str(action)
            text=label+' · valeurs : '+', '.join(str(value[0]) for value in args)
        output.append({'text':text,'kind':effect.get('kind','equipEffects'),'action_id':action})
    return output
