"""Read furniture learning actions from public client archives, never processes."""
import copy
import struct
from pathlib import Path
from client_binary import document
from java_schema import current_schemas


def learning_records(root, schemas=None):
    defs, types, mapping, classes = schemas or current_schemas(root)
    action_id = None
    for c in classes.values():
        if c.parent != 'java/lang/Enum':
            continue
        for index, value in enumerate(c.cp):
            if not value or value[0] != 8 or c.text(value[1]) != 'LEARN_FURNITURE':
                continue
            code = c.code(next(m for m in c.methods if m[1] == '<clinit>'))
            token = b'\x12' + bytes([index]) if index < 256 else b'\x13' + struct.pack('>H', index)
            position = code.index(token) + len(token)
            def integer():
                nonlocal position
                opcode = code[position]; position += 1
                if 2 <= opcode <= 8: return opcode - 3
                if opcode == 16:
                    v = struct.unpack_from('>b', code, position)[0]; position += 1; return v
                if opcode == 17:
                    v = struct.unpack_from('>h', code, position)[0]; position += 2; return v
                raise ValueError('Unsupported furniture action enum format')
            integer()  # enum ordinal
            action_id = integer()
    if action_id is None:
        raise ValueError('Furniture learning action not found')
    defs = copy.deepcopy(defs)
    item_type = mapping['ITEM']
    fields = defs[item_type]
    # These two structures are presence-prefixed in ITEM.a(reader), unlike
    # mandatory primitive fields. Full record-size validation detects drift.
    for index in (31, 32):
        name, typ = fields[index]
        if typ not in defs: raise ValueError('ITEM optional structure changed')
        fields[index] = (name, 'Option<' + typ + '>')
    rows = document(Path(root)/'contents/bdata'/f'{types["ITEM"]}.jar', item_type, defs, {item_type:types['ITEM']})
    records = []
    for row in rows:
        actions = [a for a in row['field_30'] if a['field_1'] == action_id]
        records.append({'id':row['field_0'], 'learn_furniture':bool(actions),
                        'action_id':action_id if actions else None,
                        'actions':actions})
    return records
