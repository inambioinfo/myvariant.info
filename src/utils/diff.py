'''
Utils to compare two list of variant documents
'''
from __future__ import print_function
import jsonpatch
import time
import os.path
from utils.common import dump, timesofar, get_timestamp
from utils.backend import GeneDocMongoDBBackend, GeneDocESBackend
from utils.mongo import get_src_db
from utils.es import ESIndexer
from utils import jsondiff
from biothings.utils.mongo import doc_feeder


def apply_patch(doc, patch):
    return jsonpatch.apply_patch(doc, patch)


def diff_doc(doc_1, doc_2, exclude_attrs=['_timestamp']):
    diff_d = {'update': {},
              'delete': [],
              'add': {}}
    for attr in set(doc_1) | set(doc_2):
        if exclude_attrs and attr in exclude_attrs:
            continue
        if attr in doc_1 and attr in doc_2:
            _v1 = doc_1[attr]
            _v2 = doc_2[attr]
            if _v1 != _v2:
                diff_d['update'][attr] = _v2
        elif attr in doc_1 and attr not in doc_2:
            diff_d['delete'].append(attr)
        else:
            diff_d['add'][attr] = doc_2[attr]
    if diff_d['update'] or diff_d['delete'] or diff_d['add']:
        return diff_d


def two_docs_iterator(b1, b2, id_list, step=10000):
    t0 = time.time()
    n = len(id_list)
    for i in range(0, n, step):
        t1 = time.time()
        print("Processing %d-%d documents..." % (i + 1, min(i + step, n)))
        _ids = id_list[i:i+step]
        iter1 = b1.mget_from_ids(_ids, asiter=True)
        iter2 = b2.mget_from_ids(_ids, asiter=True)
        for doc1, doc2 in zip(iter1, iter2):
            yield doc1, doc2
        print('Done.[%.1f%%,%s]' % (i*100./n, timesofar(t1)))
    print("="*20)
    print('Finished.[total time: %s]' % timesofar(t0))


def _diff_doc_worker(args):
    # b1_target_collection, b2_es_index, ids, _path = args
    _b1, _b2, ids, _path = args
    import sys
    if _path not in sys.path:
        sys.path.append(_path)
    import utils.diff
    reload(utils.diff)
    from utils.diff import _diff_doc_inner_worker, get_backend

    b1 = get_backend(*_b1)
    b2 = get_backend(*_b2)
    _updates = _diff_doc_inner_worker(b1, b2, ids)
    return _updates


def _diff_doc_inner_worker(b1, b2, ids, fastdiff=False):
    '''if fastdiff is True, only compare the whole doc,
       do not traverse into each attributes.
    '''
    _updates = []
    for doc1, doc2 in two_docs_iterator(b1, b2, ids):
        assert doc1['_id'] == doc2['_id'], repr((ids, len(ids)))
        if fastdiff:
            if doc1 != doc2:
                _updates.append({'_id': doc1['_id']})
        else:
            _diff = diff_doc(doc1, doc2)
            if _diff:
                _diff['_id'] = doc1['_id']
                _updates.append(_diff)
    return _updates


def _diff_doc_inner_worker2(b1, b2, ids, fastdiff=False):
    '''if fastdiff is True, only compare the whole doc,
       do not traverse into each attributes.
    '''
    _updates = []
    for doc1, doc2 in two_docs_iterator(b1, b2, ids):
        assert doc1['_id'] == doc2['_id'], repr((ids, len(ids)))
        if fastdiff:
            if doc1 != doc2:
                _updates.append({'_id': doc1['_id']})
        else:
            _patch = jsondiff.make(doc1, doc2)
            if _patch:
                _diff = {}
                _diff['patch'] = _patch
                _diff['_id'] = doc1['_id']
                _updates.append(_diff)
    return _updates


def diff_collections(b1, b2, use_parallel=True, step=10000):
    """
    b1, b2 are one of supported backend class in databuild.backend.
    e.g.,
        b1 = GeneDocMongoDBBackend(c1)
        b2 = GeneDocMongoDBBackend(c2)
    """

    id_s1 = set(b1.get_id_list())
    id_s2 = set(b2.get_id_list())
    print("Size of collection 1:\t", len(id_s1))
    print("Size of collection 2:\t", len(id_s2))

    id_in_1 = id_s1 - id_s2
    id_in_2 = id_s2 - id_s1
    id_common = id_s1 & id_s2
    print("# of docs found only in collection 1:\t", len(id_in_1))
    print("# of docs found only in collection 2:\t", len(id_in_2))
    print("# of docs found in both collections:\t", len(id_common))

    print("Comparing matching docs...")
    _updates = []
    if len(id_common) > 0:
        if not use_parallel:
            _updates = _diff_doc_inner_worker2(b1, b2, list(id_common))
        else:
            from utils.parallel import run_jobs_on_ipythoncluster
            _path = os.path.split(os.path.split(os.path.abspath(__file__))[0])[0]
            id_common = list(id_common)
            # b1_target_collection = b1.target_collection.name
            # b2_es_index = b2.target_esidxer.ES_INDEX_NAME
            _b1 = (b1.target_name, b1.name)
            _b2 = (b2.target_name, b2.name)
            task_li = [(_b1, _b2, id_common[i: i + step], _path) for i in range(0, len(id_common), step)]
            job_results = run_jobs_on_ipythoncluster(_diff_doc_inner_worker2, task_li)
            _updates = []
            if job_results:
                for res in job_results:
                    _updates.extend(res)
            else:
                print("Parallel jobs failed or were interrupted.")
                return None

        print("Done. [{} docs changed]".format(len(_updates)))

    _deletes = []
    if len(id_in_1) > 0:
        _deletes = sorted(id_in_1)

    _adds = []
    if len(id_in_2) > 0:
        _adds = sorted(id_in_2)

    changes = {'update': _updates,
               'delete': _deletes,
               'add': _adds,
               'source': b2.target_collection.name,
               'timestamp': get_timestamp()}
    return changes

 get_backend(target_name, bk_type, **kwargs):
ns2(b1, b2, result_dir, step=10000):
    '''
    b2 is new collection, b1 is old collection
    '''
    data_new = doc_feeder(b2.target_collection, step=step, inbatch=True, fields=[])
    data_old = doc_feeder(b1.target_collection, step=step, inbatch=True, fields=[])
    cnt= 0
    for _batch in data_new:
        cnt += 1
        id_list_new = [_doc['_id'] for _doc in _batch]
        docs_common = b1.target_collection.find({'_id': {'$in': id_list_new}}, projection=[])
        ids_common = [_doc['_id'] for _doc in docs_common]
        id_in_new = list(set(id_list_new) - set(ids_common))
        _updates = []
        if len(ids_common) > 0:
            _updates = _diff_doc_inner_worker2(b1, b2, list(ids_common))
        file_name = result_dir + '/' + str(cnt) + '.pyobj'
        _result = {
                   'add': id_in_new,
                   'update': _updates,
                   'delete': [],
                   'source': b2.target_collection.name,
                   'timestamp': get_timestamp()}
        dump(_result, file_name)
        print ("Updated: {}, added: {}".format(count(_updates), count(id_in_new)), end='')
    for _batch in data_old:
        cnt += 1
        id_list_old = [_doc['_id'] for _doc in _batch]
        docs_common = b2.target_collection.find({'_id': {'$in': id_list_old}}, projection=[])
        ids_common = [_doc['_id'] for _doc in docs_common]
        id_in_old = list(set(id_list_old)-set(ids_common)）
        file_name = result_dir + '/' + str(cnt) + '.pyobj'
        _result = {
                   'delete': id_in_old,
                   'add': [],
                   'update': [],
                   'source': b2.target_collection.name,
                   'timestamp': get_timestamp()}
        dump(_result, file_name)
        print("Deleted: {}".format(count(id_in_old)), end='')
    '''Return a backend instance for given target_name and backend type.
        currently support MongoDB and ES backend.
    '''
    if bk_type == 'mongodb':
        target_db = get_src_db()
        target_col = target_db[target_name]
        return GeneDocMongoDBBackend(target_col)
    elif bk_type == 'es':
        esi = ESIndexer(target_name, **kwargs)
        return GeneDocESBackend(esi)
