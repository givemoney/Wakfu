"""Verify actual SQLite relations, repeat import, failure preservation and update lock."""
import hashlib,json,pathlib,sqlite3,tempfile
import update
from import_data import build
ROOT=pathlib.Path(__file__).resolve().parent.parent
def digest():return hashlib.sha256((ROOT/'wakfu.sqlite').read_bytes()).hexdigest()
def main():
    before=digest()
    with sqlite3.connect(ROOT/'wakfu.sqlite') as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        original=json.loads(db.execute("SELECT value FROM metadata WHERE key='report'").fetchone()[0])
        with tempfile.TemporaryDirectory(prefix='.wakfu-test-',dir=ROOT) as tmp:
            tmp=pathlib.Path(tmp)
            for dataset, in db.execute('SELECT DISTINCT dataset FROM source_records'):
                rows=[json.loads(row[0]) for row in db.execute('SELECT payload FROM source_records WHERE dataset=? ORDER BY ordinal',(dataset,))]
                (tmp/(dataset+'.json')).write_text(json.dumps(rows),encoding='utf-8')
            manifest=json.loads(db.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()[0])
            (tmp/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            rebuilt=build(tmp,tmp/'rebuilt.sqlite')
            assert rebuilt['counts']==original['counts']
            assert rebuilt['audit']==original['audit']
            # A deliberate broken recipe relationship must fail validation.
            rows=json.loads((tmp/'recipeIngredients.json').read_text('utf-8'))
            rows[0]['recipeId']=-999999
            (tmp/'recipeIngredients.json').write_text(json.dumps(rows),encoding='utf-8')
            def bad_download(destination):
                import shutil
                for source in tmp.glob('*.json'):shutil.copyfile(source,pathlib.Path(destination)/source.name)
                return manifest
            saved=update.download;update.download=bad_download
            try:
                try:update.update(ROOT)
                except ValueError as e:assert 'ingredients_without_recipe' in str(e)
                else:raise AssertionError('Invalid candidate was accepted')
            finally:update.download=saved
    assert before==digest(),'Previous database changed on failure'
    assert not (ROOT/'.update.lock').exists()
    assert not list(ROOT.glob('.wakfu-build-*'))
    lock=ROOT/'.update.lock';lock.write_text('verification',encoding='utf-8')
    try:
        try:update.update(ROOT)
        except FileExistsError:pass
        else:raise AssertionError('Concurrent update was allowed')
    finally:lock.unlink()
    assert before==digest()
    print('PASS: integrity, foreign keys, deterministic reimport, rejected broken relation, preserved previous database, temporary cleanup, concurrent-update lock')
if __name__=='__main__':main()
